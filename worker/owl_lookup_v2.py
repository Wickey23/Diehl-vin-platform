from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
LOCAL_APPDATA = Path(os.environ.get('LOCALAPPDATA', str(ROOT)))
PROFILE_DIR = LOCAL_APPDATA / 'DiehlDTNAManual' / 'browser_profile'
STATE_DIR = LOCAL_APPDATA / 'DiehlVINWorker' / 'owl'
LOG_FILE = STATE_DIR / 'owl_lookup.log'
RESULT = Path(os.environ.get('DIEHL_RESULT_FILE', str(ROOT / 'vin-results.json')))
VINS = [v.strip().upper() for v in os.environ.get('DIEHL_VINS', '').splitlines() if v.strip()]

OWL_SIGNON_URL = 'https://secure.freightliner.com/iwarranty/signOn'
OWL_COVERAGE_URL = 'https://secure.freightliner.com/iwarranty/servlet/com.fourcs.clm.iwarranty.eclaims.dataview.servlets.WarrantyDetailsGoToServlet?FromInd=Home'
OWL_MAJOR_URL = 'https://secure.freightliner.com/iwarranty/servlet/com.fourcs.clm.iwarranty.wc.dataview.servlets.ProductMaintenanceServlet?ActionType=AddNewSideNav&FromInd=SideNav'
MIN_MAIN_X = 220


def log(message: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    line = f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] {message}'
    print(line, flush=True)
    with LOG_FILE.open('a', encoding='utf-8') as f:
        f.write(line + '\n')


def clean(value: Any) -> str:
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def launch_context(playwright):
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    kwargs = dict(
        user_data_dir=str(PROFILE_DIR),
        headless=False,
        viewport={'width': 1500, 'height': 900},
        accept_downloads=True,
    )
    try:
        return playwright.chromium.launch_persistent_context(channel='msedge', **kwargs)
    except PlaywrightError:
        return playwright.chromium.launch_persistent_context(**kwargs)


def iter_frames(context):
    for page in list(context.pages):
        for frame in page.frames:
            yield page, frame


def body_text(frame) -> str:
    try:
        return frame.locator('body').inner_text(timeout=2500)
    except Exception:
        return ''


def inject_hint(page, message: str) -> None:
    try:
        page.evaluate("""msg => {
          let el=document.getElementById('diehl-owl-hint');
          if(!el){
            el=document.createElement('div'); el.id='diehl-owl-hint';
            Object.assign(el.style,{position:'fixed',top:'10px',left:'50%',transform:'translateX(-50%)',zIndex:'2147483647',background:'#163a5f',color:'#fff',padding:'11px 16px',borderRadius:'8px',font:'14px Arial',boxShadow:'0 2px 10px rgba(0,0,0,.35)'});
            document.body.appendChild(el);
          }
          el.textContent=msg;
        }""", message)
    except Exception:
        pass


def wait_logged_in(context, timeout: int = 240) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        for page, frame in iter_frames(context):
            text = body_text(frame)
            url = (frame.url or '').lower()
            if re.search(r'OWL\s+Home|Coverage\s+Info|Major\s+Components|Online\s+Warranty', text, re.I) or ('/iwarranty/' in url and 'signon' not in url):
                return
            inject_hint(page, 'Diehl VIN: complete Freightliner/OWL login and MFA. The worker is waiting.')
        time.sleep(1)
    raise RuntimeError('OWL login did not become ready within 4 minutes.')


def open_url(context, url: str, label: str):
    page = context.pages[0] if context.pages else context.new_page()
    log(f'Opening OWL {label}: {url}')
    page.goto(url, wait_until='domcontentloaded', timeout=120_000)
    page.wait_for_timeout(1200)
    return page


def _assign_main_product_sn_id(frame) -> str:
    """Return an id for the Product S/N input in the main content area only.

    The OWL left sidebar Quick Search input is physically left of the main content.
    We explicitly reject it by screen position and by sidebar/quick-search ancestry.
    """
    try:
        return frame.evaluate("""(minX) => {
          const norm=s=>(s||'').replace(/\s+/g,' ').trim();
          const badAncestor = el => {
            let n=el;
            while(n && n!==document.body){
              const sig=((n.id||'')+' '+(n.className||'')+' '+(n.getAttribute?.('name')||'')).toLowerCase();
              if(/quick.?search|left.?nav|left.?menu|side.?nav|sidebar/.test(sig)) return true;
              n=n.parentElement;
            }
            return false;
          };
          const usable = input => {
            if(!input || input.disabled) return false;
            const type=(input.getAttribute('type')||'text').toLowerCase();
            if(type!=='text') return false;
            const r=input.getBoundingClientRect();
            if(!r.width || !r.height || r.left < minX) return false;
            if(badAncestor(input)) return false;
            return true;
          };
          const candidates=[];
          for(const row of document.querySelectorAll('tr')){
            const text=norm(row.innerText||row.textContent);
            if(!/Product\s+S\/N\s*:?/i.test(text)) continue;
            for(const input of row.querySelectorAll('input')){
              if(usable(input)) candidates.push({input,score:100});
            }
          }
          for(const el of document.querySelectorAll('td,th,label,span,b,font')){
            const text=norm(el.innerText||el.textContent);
            if(!/^Product\s+S\/N\s*:?$/i.test(text)) continue;
            const cell=el.closest('td,th');
            const row=el.closest('tr');
            if(cell?.nextElementSibling){
              for(const input of cell.nextElementSibling.querySelectorAll('input')) if(usable(input)) candidates.push({input,score:200});
            }
            if(row){
              for(const input of row.querySelectorAll('input')) if(usable(input)) candidates.push({input,score:150});
            }
          }
          if(!candidates.length) return '';
          candidates.sort((a,b)=>b.score-a.score || a.input.getBoundingClientRect().left-b.input.getBoundingClientRect().left);
          const chosen=candidates[0].input;
          if(!chosen.id) chosen.id='diehl-main-product-sn-'+Math.random().toString(36).slice(2);
          return chosen.id;
        }""", MIN_MAIN_X)
    except Exception:
        return ''


def find_main_product_sn(context, timeout: int = 30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        for page, frame in iter_frames(context):
            temp_id = _assign_main_product_sn_id(frame)
            if not temp_id:
                continue
            loc = frame.locator('#' + temp_id)
            if not loc.count():
                continue
            item = loc.first
            try:
                box = item.bounding_box()
                if not box or box['x'] < MIN_MAIN_X:
                    log(f'Rejected Product S/N candidate at x={box["x"] if box else "none"}; left sidebar is forbidden.')
                    continue
                log(f'Confirmed MAIN Product S/N field at x={round(box["x"])} y={round(box["y"])} frame={frame.url}')
                return page, frame, item
            except Exception:
                continue
        time.sleep(.35)
    raise RuntimeError('Could not find the main-content Product S/N input. The left Quick Search input is intentionally ignored.')


def submit_vin(context, vin: str):
    page, frame, field = find_main_product_sn(context)
    if 'QuickSearch' in (page.url or ''):
        raise RuntimeError('OWL is already on Quick Search; refusing to type the VIN there.')

    for attempt in range(1, 4):
        box = field.bounding_box()
        if not box or box['x'] < MIN_MAIN_X:
            raise RuntimeError('The selected VIN field moved into the left sidebar. Refusing to type.')
        field.click()
        field.fill('')
        field.type(vin, delay=40)
        page.wait_for_timeout(300)
        actual = clean(field.input_value()).upper()
        log(f'OWL {vin}: main Product S/N attempt {attempt}; value={actual or "[blank]"}; x={round(box["x"])}')
        if actual == vin:
            break
        if attempt == 3:
            raise RuntimeError(f'Main Product S/N did not contain {vin}; refusing to Tab.')
        page, frame, field = find_main_product_sn(context, 10)

    inject_hint(page, f'Diehl VIN: {vin} entered in main Product S/N. Waiting 1 second before Tab.')
    page.wait_for_timeout(1000)
    if clean(field.input_value()).upper() != vin:
        raise RuntimeError('VIN changed or disappeared from main Product S/N before Tab.')
    box = field.bounding_box()
    if not box or box['x'] < MIN_MAIN_X:
        raise RuntimeError('Main Product S/N position changed before Tab; refusing to continue.')
    field.press('Tab')
    log(f'OWL {vin}: Tab pressed from main Product S/N at x={round(box["x"])}.')
    page.wait_for_timeout(1500)
    if 'QuickSearch' in (page.url or ''):
        raise RuntimeError('OWL navigated to Quick Search after Tab. This result is rejected.')
    return page, frame


def harvest(frame) -> dict[str, Any]:
    text = body_text(frame)
    fields: dict[str, str] = {}
    rows: list[list[str]] = []
    try:
        payload = frame.evaluate("""() => {
          const n=s=>(s||'').replace(/\s+/g,' ').trim();
          const fields={}; const rows=[];
          for(const tr of document.querySelectorAll('tr')){
            const cells=Array.from(tr.querySelectorAll(':scope > td,:scope > th')).map(c=>n(c.innerText||c.textContent));
            if(cells.some(Boolean)) rows.push(cells);
            for(const input of tr.querySelectorAll('input,select,textarea')){
              const cell=input.closest('td,th'); const prev=cell?.previousElementSibling;
              let label=prev?n(prev.innerText||prev.textContent):'';
              let value=input.tagName==='SELECT'?n(input.options[input.selectedIndex]?.text||input.value):n(input.value);
              if(label&&value) fields[label]=value;
            }
            if(cells.length===2&&cells[0]&&cells[1]&&cells[0].length<90) fields[cells[0]]=cells[1];
          }
          return {fields,rows};
        }""")
        fields = payload.get('fields') or {}
        rows = payload.get('rows') or []
    except Exception:
        pass
    return {'text': text, 'fields': fields, 'rows': rows}


def pick(h: dict[str, Any], aliases: list[str]) -> str:
    for alias in aliases:
        rx = re.compile(alias, re.I)
        for k, v in (h.get('fields') or {}).items():
            if rx.search(clean(k)) and clean(v):
                return clean(v)
    text = h.get('text') or ''
    for alias in aliases:
        m = re.search(rf'{alias}\s*[:#\-]?\s*([^\n\r|]{{1,180}})', text, re.I)
        if m:
            return clean(m.group(1))
    return ''


def confirms_vin(h: dict[str, Any], vin: str) -> bool:
    normalized = re.sub(r'[^A-Z0-9]', '', (h.get('text') or '').upper())
    if vin in normalized:
        return True
    for value in (h.get('fields') or {}).values():
        if re.sub(r'[^A-Z0-9]', '', clean(value).upper()) == vin:
            return True
    return False


def explicit_not_found(text: str) -> bool:
    return bool(re.search(r'not\s+found|no\s+(vehicle|record|coverage|results?)|invalid\s+(vin|serial)|no\s+matching', text, re.I))


def coverage_records(h: dict[str, Any]) -> list[list[str]]:
    out=[]
    for row in h.get('rows') or []:
        cells=[clean(c) for c in row if clean(c)]
        if len(cells)>=2 and re.search(r'coverage|warranty|start|expire|expiration|term|miles|months|description', ' | '.join(cells), re.I):
            out.append(cells)
    return out[:250]


def component_records(h: dict[str, Any]) -> list[dict[str, str]]:
    rows=h.get('rows') or []
    header=None
    out=[]
    for row in rows:
        cells=[clean(c) for c in row]
        joined=' | '.join(cells)
        if header is None and re.search(r'component|description|make|model|serial', joined, re.I):
            header=cells
            continue
        if not re.search(r'engine|allison|transmission|axle', joined, re.I):
            continue
        if header:
            out.append({header[i] if i<len(header) and header[i] else f'Column {i+1}': cells[i] for i in range(len(cells)) if cells[i]})
        else:
            out.append({f'Column {i+1}': c for i,c in enumerate(cells) if c})
    return out[:200]


def serial_from_records(records: list[dict[str, str]], kind: str) -> str:
    rx=re.compile(kind,re.I)
    for rec in records:
        joined=' | '.join(clean(v) for v in rec.values())
        if not rx.search(joined):
            continue
        for k,v in rec.items():
            if re.search(r'serial|s/n',k,re.I):
                s=clean(v).upper()
                if re.fullmatch(r'[A-Z0-9][A-Z0-9\-]{4,30}',s): return s
        m=re.search(r'(?:Serial(?:\s+Number|\s+No\.?)?|S/N)\s*[:#\-]?\s*([A-Z0-9][A-Z0-9\-]{4,30})',joined,re.I)
        if m:return m.group(1).upper()
    return ''


def model_from_records(records: list[dict[str, str]], kind: str) -> str:
    rx=re.compile(kind,re.I)
    for rec in records:
        if not rx.search(' | '.join(clean(v) for v in rec.values())): continue
        for k,v in rec.items():
            if re.search(r'model|description',k,re.I) and clean(v): return clean(v)
    return ''


def coverage_lookup(context, vin: str) -> dict[str, Any]:
    open_url(context, OWL_COVERAGE_URL, 'Coverage Info')
    page, frame = submit_vin(context, vin)
    page.wait_for_timeout(1000)
    h=harvest(frame)
    if explicit_not_found(h['text']):
        return {'vin':vin,'verificationStatus':'Not Found','customerResult':'VIN not found in OWL','source':'OWL Coverage Info'}
    if not confirms_vin(h,vin):
        raise RuntimeError(f'Coverage Info did not confirm VIN {vin}; rejecting the result.')
    cov=coverage_records(h)
    result={
        'vin':vin,
        'verificationStatus':'Verified',
        'productSerialNumber':pick(h,[r'Product\s+S/N',r'VIN']) or vin,
        'vehicleModel':pick(h,[r'Base\s+Model',r'Product\s+Model',r'Vehicle\s+Model']),
        'buildDate':pick(h,[r'Build\s+Date',r'Manufactur(?:e|ed)\s+Date']),
        'inServiceStatus':pick(h,[r'In[- ]?Service\s+Status',r'Inservice\s+Status']),
        'inServiceDate':pick(h,[r'In[- ]?Service\s+Date',r'Inservice\s+Date',r'Warranty\s+Start\s+Date']),
        'mileage':pick(h,[r'Mileage',r'Odometer',r'In[- ]?Service\s+Miles']),
        'customerName':pick(h,[r'Registered\s+Customer\s+Name',r'Customer\s+Name',r'Owner\s+Name']),
        'registeredCustomerName':pick(h,[r'Registered\s+Customer\s+Name',r'Customer\s+Name']),
        'registeredCustomerAccount':pick(h,[r'Registered\s+Customer\s+Account',r'Customer\s+Account',r'Account\s+Number']),
        'warrantyStatus':pick(h,[r'Warranty\s+Status',r'Coverage\s+Status']),
        'warrantyCoverage':'\n'.join(' | '.join(r) for r in cov),
        'coverageRecordsJson':json.dumps(cov,ensure_ascii=False),
        'coverageFieldsJson':json.dumps(h['fields'],ensure_ascii=False),
        'source':'OWL Coverage Info + Major Components',
    }
    result['customerResult']=result['customerName']
    if not result['inServiceStatus']:
        result['inServiceStatus']='In Service' if result['inServiceDate'] else ''
    return result


def major_lookup(context, vin: str) -> dict[str, Any]:
    open_url(context, OWL_MAJOR_URL, 'Major Components')
    page, frame = submit_vin(context, vin)
    page.wait_for_timeout(1000)
    h=harvest(frame)
    if explicit_not_found(h['text']) or not confirms_vin(h,vin):
        raise RuntimeError(f'Major Components did not confirm VIN {vin}; rejecting component data.')
    recs=component_records(h)
    return {
        'engineSerialNumber':serial_from_records(recs,r'engine') or pick(h,[r'Engine\s+Serial(?:\s+Number)?',r'Engine\s+S/N']),
        'engineModel':model_from_records(recs,r'engine') or pick(h,[r'Engine\s+Model']),
        'allisonTransmissionSerialNumber':serial_from_records(recs,r'allison|transmission') or pick(h,[r'Allison.*Serial',r'Transmission\s+Serial']),
        'transmissionModel':model_from_records(recs,r'allison|transmission') or pick(h,[r'Allison\s+Model',r'Transmission\s+Model']),
        'majorComponentsText':'\n'.join(' | '.join(clean(v) for v in r.values()) for r in recs),
        'majorComponentsJson':json.dumps(recs,ensure_ascii=False),
        'majorComponentFieldsJson':json.dumps(h['fields'],ensure_ascii=False),
    }


def lookup_one(context, vin: str) -> dict[str, Any]:
    coverage=coverage_lookup(context,vin)
    if coverage.get('verificationStatus')=='Not Found': return coverage
    result={**coverage,**major_lookup(context,vin)}
    result['verificationStatus']='Verified'
    log(f'OWL COMPLETE {vin}: in-service={result.get("inServiceDate") or "blank"}; engine={result.get("engineSerialNumber") or "blank"}; Allison={result.get("allisonTransmissionSerialNumber") or "blank"}')
    return result


def main() -> int:
    if not VINS:
        RESULT.write_text('{}',encoding='utf-8')
        return 0
    out: dict[str,Any]={}
    with sync_playwright() as p:
        context=launch_context(p)
        try:
            page=context.pages[0] if context.pages else context.new_page()
            page.goto(OWL_SIGNON_URL,wait_until='domcontentloaded',timeout=120_000)
            wait_logged_in(context)
            for vin in VINS:
                try: out[vin]=lookup_one(context,vin)
                except Exception as exc:
                    log(f'OWL lookup failed for {vin}: {exc}')
                    out[vin]={'vin':vin,'_error':str(exc),'source':'OWL'}
        finally:
            try: context.close()
            except Exception: pass
    RESULT.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
    return 0


if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as exc:
        log(f'FATAL OWL ERROR: {exc}')
        RESULT.write_text(json.dumps({'_error':str(exc)}),encoding='utf-8')
        raise
