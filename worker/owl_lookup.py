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
OWL_STATE_DIR = LOCAL_APPDATA / 'DiehlVINWorker' / 'owl'
LOG_FILE = OWL_STATE_DIR / 'owl_lookup.log'
RESULT = Path(os.environ.get('DIEHL_RESULT_FILE', str(ROOT / 'vin-results.json')))
VINS = [x.strip().upper() for x in os.environ.get('DIEHL_VINS', '').splitlines() if x.strip()]

OWL_SIGNON_URL = 'https://secure.freightliner.com/iwarranty/signOn'
OWL_COVERAGE_URL = 'https://secure.freightliner.com/iwarranty/servlet/com.fourcs.clm.iwarranty.eclaims.dataview.servlets.WarrantyDetailsGoToServlet?FromInd=Home'
OWL_MAJOR_COMPONENTS_URL = 'https://secure.freightliner.com/iwarranty/servlet/com.fourcs.clm.iwarranty.wc.dataview.servlets.ProductMaintenanceServlet?ActionType=AddNewSideNav&FromInd=SideNav'


def log(message: str) -> None:
    OWL_STATE_DIR.mkdir(parents=True, exist_ok=True)
    line = f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] {message}'
    print(line, flush=True)
    with LOG_FILE.open('a', encoding='utf-8') as f:
        f.write(line + '\n')


def launch_context(playwright):
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    args = dict(user_data_dir=str(PROFILE_DIR), headless=False, viewport={'width': 1500, 'height': 900}, accept_downloads=True)
    try:
        return playwright.chromium.launch_persistent_context(channel='msedge', **args)
    except PlaywrightError:
        return playwright.chromium.launch_persistent_context(**args)


def frames(context):
    for page in list(context.pages):
        try:
            for frame in page.frames:
                yield page, frame
        except Exception:
            yield page, page


def clean(value: Any) -> str:
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def body_text(frame) -> str:
    try:
        return frame.locator('body').inner_text(timeout=3000)
    except Exception:
        return ''


def inject_hint(page, message: str) -> None:
    try:
        page.evaluate("""msg => {
            let el=document.getElementById('diehl-owl-hint');
            if(!el){el=document.createElement('div');el.id='diehl-owl-hint';Object.assign(el.style,{position:'fixed',top:'12px',left:'50%',transform:'translateX(-50%)',zIndex:'2147483647',background:'#102a43',color:'white',padding:'12px 18px',borderRadius:'8px',fontFamily:'Arial',fontSize:'14px',boxShadow:'0 2px 10px rgba(0,0,0,.3)'});document.body.appendChild(el);}el.textContent=msg;
        }""", message)
    except Exception:
        pass


def find_vin_input(frame):
    """Find main OWL Product S/N input, never the left Quick Search input."""
    xpaths = [
        "//td[contains(translate(normalize-space(.),'abcdefghijklmnopqrstuvwxyz','ABCDEFGHIJKLMNOPQRSTUVWXYZ'),'PRODUCT S/N')]/following-sibling::td[1]//input[not(@type) or @type='text']",
        "//*[contains(translate(normalize-space(.),'abcdefghijklmnopqrstuvwxyz','ABCDEFGHIJKLMNOPQRSTUVWXYZ'),'PRODUCT S/N')]/ancestor::tr[1]//input[not(@type) or @type='text']",
    ]
    for xp in xpaths:
        try:
            loc = frame.locator('xpath=' + xp)
            for i in range(loc.count()):
                item = loc.nth(i)
                if item.is_visible() and item.is_enabled():
                    return item
        except Exception:
            pass

    try:
        rows = frame.locator('tr')
        count = rows.count()
    except Exception:
        count = 0
    for i in range(count):
        try:
            row = rows.nth(i)
            text = clean(row.text_content(timeout=200))
            if not re.search(r'Product\s+S/N\s*:?', text, re.I):
                continue
            inputs = row.locator('input[type="text"],input:not([type])')
            for j in range(inputs.count()):
                item = inputs.nth(j)
                if item.is_visible() and item.is_enabled():
                    return item
        except Exception:
            continue
    return None


def wait_logged_in(context, timeout: int = 240) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        for page, frame in frames(context):
            text = body_text(frame)
            url = (getattr(frame, 'url', '') or '').lower()
            if re.search(r'Coverage\s+Info|Major\s+Components|Online\s+Warranty|OWL\s+Home', text, re.I) or ('/iwarranty/' in url and 'signon' not in url):
                log('OWL authenticated session is ready.')
                return
            inject_hint(page, 'Diehl VIN: complete your Freightliner/OWL login and MFA. The worker will continue automatically.')
        time.sleep(1)
    raise RuntimeError('OWL login did not become ready within 4 minutes. Complete login/MFA and retry.')


def open_owl_url(context, url: str, label: str):
    page = context.pages[0] if context.pages else context.new_page()
    log(f'Opening OWL {label}: {url}')
    page.goto(url, wait_until='domcontentloaded', timeout=120_000)
    page.wait_for_timeout(1000)
    return page


def wait_for_search_page(context, timeout: int = 30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        for page, frame in frames(context):
            vin_input = find_vin_input(frame)
            if vin_input is not None:
                log(f'Found OWL Product S/N field in frame: {getattr(frame, "url", "") or "[same page]"}')
                return page, frame, vin_input
        time.sleep(.35)
    raise RuntimeError('OWL page opened, but the main Product S/N field could not be found.')


def page_has_explicit_not_found(text: str) -> bool:
    return bool(re.search(r'not\s+found|no\s+(vehicle|record|coverage|results?)|invalid\s+(vin|serial)|no\s+matching', text, re.I))


def submit_vin(context, vin: str):
    page, frame, vin_input = wait_for_search_page(context)
    for attempt in range(1, 4):
        try:
            vin_input.click()
            vin_input.fill('')
            vin_input.type(vin, delay=35)
            page.wait_for_timeout(250)
            actual = clean(vin_input.input_value()).upper()
            log(f'OWL {vin}: Product S/N fill attempt {attempt}; field contains {actual or "[blank]"}.')
            if actual == vin:
                break
        except Exception:
            actual = ''
        if attempt == 3:
            raise RuntimeError(f'OWL Product S/N field did not contain VIN {vin}; refusing to continue.')
        page, frame, vin_input = wait_for_search_page(context, 10)

    log(f'OWL {vin}: Product S/N verified; waiting 1 full second before Tab.')
    page.wait_for_timeout(1000)
    actual = clean(vin_input.input_value()).upper()
    if actual != vin:
        raise RuntimeError(f'OWL Product S/N changed before Tab. Expected {vin}, found {actual or "[blank]"}.')
    vin_input.press('Tab')
    log(f'OWL {vin}: Tab sent after verified 1-second delay.')
    page.wait_for_timeout(1200)

    if 'QuickSearch' in (page.url or ''):
        raise RuntimeError('OWL navigated to Quick Search after Product S/N Tab; refusing to use that page as a VIN result.')

    previous = ''
    stable = 0
    deadline = time.time() + 45
    while time.time() < deadline:
        page.wait_for_timeout(500)
        current = body_text(frame)
        if current == previous and len(current) > 40:
            stable += 1
        else:
            stable = 0
        previous = current
        normalized = re.sub(r'[^A-Z0-9]', '', current.upper())
        if vin in normalized and stable >= 1:
            break
        if page_has_explicit_not_found(current) and stable >= 1:
            break
        if stable >= 5:
            break
    return page, frame


def harvest(frame) -> dict[str, Any]:
    """Capture OWL legacy table structure without depending on one label spelling."""
    data: dict[str, Any] = {'fields': {}, 'rows': [], 'text': body_text(frame)}
    try:
        payload = frame.evaluate("""() => {
          const norm=s=>(s||'').replace(/\s+/g,' ').trim();
          const fields={};
          const rows=[];
          for(const tr of document.querySelectorAll('tr')){
            const cells=Array.from(tr.querySelectorAll(':scope > td,:scope > th')).map(td=>norm(td.innerText||td.textContent));
            if(cells.some(Boolean)) rows.push(cells);
            const direct=Array.from(tr.querySelectorAll('input,select,textarea'));
            for(const input of direct){
              let label='';
              const cell=input.closest('td,th');
              if(cell){
                const prev=cell.previousElementSibling;
                if(prev) label=norm(prev.innerText||prev.textContent);
              }
              if(!label){
                const id=input.id;
                if(id){const l=document.querySelector(`label[for="${CSS.escape(id)}"]`);if(l)label=norm(l.innerText||l.textContent);}
              }
              let value='';
              if(input.tagName==='SELECT') value=norm(input.options[input.selectedIndex]?.text||input.value);
              else value=norm(input.value);
              if(label && value) fields[label]=value;
            }
            if(cells.length===2 && cells[0] && cells[1] && cells[0].length<80) fields[cells[0]]=cells[1];
          }
          return {fields,rows};
        }""")
        if isinstance(payload, dict):
            data['fields'] = payload.get('fields') or {}
            data['rows'] = payload.get('rows') or []
    except Exception:
        pass
    return data


def field_value(fields: dict[str, Any], aliases: list[str]) -> str:
    for alias in aliases:
        rx = re.compile(alias, re.I)
        for key, value in fields.items():
            if rx.search(clean(key)):
                v = clean(value)
                if v:
                    return v
    return ''


def labeled(text: str, aliases: list[str]) -> str:
    for alias in aliases:
        for pattern in (rf'{alias}\s*[:#\-]?\s*([^\n\r|]{{1,180}})', rf'{alias}\s*[\n\r]+\s*([^\n\r]{{1,180}})'):
            m = re.search(pattern, text, re.I)
            if m:
                v = clean(m.group(1))
                if v:
                    return v
    return ''


def pick(harvested: dict[str, Any], aliases: list[str]) -> str:
    return field_value(harvested.get('fields') or {}, aliases) or labeled(harvested.get('text') or '', aliases)


def page_confirms_vin(harvested: dict[str, Any], vin: str) -> bool:
    text = harvested.get('text') or ''
    if vin in re.sub(r'[^A-Z0-9]', '', text.upper()):
        return True
    for value in (harvested.get('fields') or {}).values():
        if vin == re.sub(r'[^A-Z0-9]', '', clean(value).upper()):
            return True
    return False


def coverage_rows(harvested: dict[str, Any]) -> list[list[str]]:
    out: list[list[str]] = []
    for row in harvested.get('rows') or []:
        cleaned = [clean(x) for x in row if clean(x)]
        if len(cleaned) < 2:
            continue
        joined = ' | '.join(cleaned)
        if re.search(r'coverage|warranty|start|expire|expiration|term|miles|months|component|description', joined, re.I):
            out.append(cleaned)
    return out[:250]


def component_records(harvested: dict[str, Any]) -> list[dict[str, str]]:
    rows = harvested.get('rows') or []
    records: list[dict[str, str]] = []
    headers: list[str] | None = None
    for row in rows:
        cells = [clean(x) for x in row]
        if len(cells) < 2:
            continue
        joined = ' '.join(cells)
        if headers is None and re.search(r'component|description|make|manufacturer|model|serial', joined, re.I):
            headers = cells
            continue
        if headers and len(cells) >= 2:
            record = {headers[i] if i < len(headers) and headers[i] else f'Column {i+1}': cells[i] for i in range(len(cells)) if cells[i]}
            if record and any(re.search(r'engine|allison|transmission|axle|component', v, re.I) for v in record.values()):
                records.append(record)
        elif re.search(r'engine|allison|transmission|axle', joined, re.I):
            records.append({f'Column {i+1}': v for i, v in enumerate(cells) if v})
    return records[:200]


def serial_from_records(records: list[dict[str, str]], kind: str) -> str:
    target = re.compile(kind, re.I)
    for record in records:
        joined = ' | '.join(clean(v) for v in record.values())
        if not target.search(joined):
            continue
        for key, value in record.items():
            if re.search(r'serial|s/n', key, re.I):
                v = clean(value).upper()
                if re.fullmatch(r'[A-Z0-9][A-Z0-9\-]{4,30}', v):
                    return v
        m = re.search(r'(?:Serial(?:\s+Number|\s+No\.?)?|S/N)\s*[:#\-]?\s*([A-Z0-9][A-Z0-9\-]{4,30})', joined, re.I)
        if m:
            return m.group(1).upper()
    return ''


def model_from_records(records: list[dict[str, str]], kind: str) -> str:
    target = re.compile(kind, re.I)
    for record in records:
        joined = ' | '.join(clean(v) for v in record.values())
        if not target.search(joined):
            continue
        for key, value in record.items():
            if re.search(r'model|description', key, re.I) and clean(value):
                return clean(value)
    return ''


def coverage_lookup(context, vin: str) -> dict[str, Any]:
    open_owl_url(context, OWL_COVERAGE_URL, 'Coverage Info / Check Coverage')
    page, frame = submit_vin(context, vin)
    inject_hint(page, f'Diehl VIN: validating Coverage Info for {vin}')
    h = harvest(frame)
    text = h.get('text') or ''
    if page_has_explicit_not_found(text):
        return {'vin': vin, 'verificationStatus': 'Not Found', 'source': 'OWL Coverage Info', 'customerResult': 'VIN not found in OWL Coverage Info'}
    if not page_confirms_vin(h, vin):
        raise RuntimeError(f'OWL Coverage Info did not show VIN {vin} after lookup; refusing to attach another vehicle\'s data.')

    in_service_date = pick(h, [r'In[- ]?Service\s+Date', r'Inservice\s+Date', r'Warranty\s+Start\s+Date'])
    in_service_status = pick(h, [r'In[- ]?Service\s+Status', r'Inservice\s+Status'])
    mileage = pick(h, [r'Mileage', r'Odometer', r'In[- ]?Service\s+Miles'])
    customer = pick(h, [r'Registered\s+Customer\s+Name', r'Customer\s+Name', r'Owner\s+Name'])
    account = pick(h, [r'Registered\s+Customer\s+Account', r'Customer\s+Account', r'Account\s+Number'])
    model = pick(h, [r'Base\s+Model', r'Product\s+Model', r'Vehicle\s+Model', r'Model'])
    serial = pick(h, [r'Product\s+S/N', r'Product\s+Serial', r'VIN'])
    build_date = pick(h, [r'Build\s+Date', r'Manufactur(?:e|ed)\s+Date'])
    warranty_status = pick(h, [r'Warranty\s+Status', r'Coverage\s+Status'])
    cov_rows = coverage_rows(h)
    summary = '\n'.join(' | '.join(row) for row in cov_rows)

    if not in_service_status:
        if in_service_date:
            in_service_status = 'In Service'
        elif re.search(r'not\s+in\s+service|not\s+registered', text, re.I):
            in_service_status = 'Not In Service'

    result = {
        'vin': vin,
        'verificationStatus': 'Verified',
        'productSerialNumber': serial or vin,
        'vehicleModel': model,
        'buildDate': build_date,
        'inServiceStatus': in_service_status,
        'inServiceDate': in_service_date,
        'mileage': mileage,
        'customerResult': customer,
        'customerName': customer,
        'registeredCustomerName': customer,
        'registeredCustomerAccount': account,
        'warrantyStatus': warranty_status,
        'warrantyCoverage': summary,
        'coverageRecordsJson': json.dumps(cov_rows, ensure_ascii=False),
        'coverageFieldsJson': json.dumps(h.get('fields') or {}, ensure_ascii=False),
        'source': 'OWL Coverage Info + Major Components',
    }
    log(f'OWL Coverage {vin}: in-service={in_service_date or "blank"}; status={in_service_status or "blank"}; customer={customer or "blank"}; coverage rows={len(cov_rows)}')
    return result


def major_components_lookup(context, vin: str) -> dict[str, Any]:
    open_owl_url(context, OWL_MAJOR_COMPONENTS_URL, 'Major Components')
    page, frame = submit_vin(context, vin)
    inject_hint(page, f'Diehl VIN: validating Major Components for {vin}')
    h = harvest(frame)
    if page_has_explicit_not_found(h.get('text') or ''):
        raise RuntimeError(f'OWL Major Components reported VIN {vin} was not found after Coverage Info had verified it.')
    if not page_confirms_vin(h, vin):
        raise RuntimeError(f'OWL Major Components did not show VIN {vin}; refusing to attach component data to the wrong vehicle.')

    records = component_records(h)
    engine_serial = serial_from_records(records, r'engine') or pick(h, [r'Engine\s+Serial(?:\s+Number|\s+No\.?)?', r'Engine\s+S/N'])
    allison_serial = serial_from_records(records, r'allison|transmission') or pick(h, [r'Allison(?:\s+Transmission)?\s+Serial(?:\s+Number|\s+No\.?)?', r'Transmission\s+Serial', r'Allison\s+S/N'])
    engine_model = model_from_records(records, r'engine') or pick(h, [r'Engine\s+Model'])
    transmission_model = model_from_records(records, r'allison|transmission') or pick(h, [r'Transmission\s+Model', r'Allison\s+Model'])
    summary = '\n'.join(' | '.join(clean(v) for v in rec.values()) for rec in records)
    log(f'OWL Components {vin}: engine={engine_serial or "blank"}; Allison={allison_serial or "blank"}; component rows={len(records)}')
    return {
        'engineSerialNumber': engine_serial,
        'engineModel': engine_model,
        'allisonTransmissionSerialNumber': allison_serial,
        'transmissionModel': transmission_model,
        'majorComponentsText': summary,
        'majorComponentsJson': json.dumps(records, ensure_ascii=False),
        'majorComponentFieldsJson': json.dumps(h.get('fields') or {}, ensure_ascii=False),
    }


def lookup_one(context, vin: str) -> dict[str, Any]:
    coverage = coverage_lookup(context, vin)
    if coverage.get('verificationStatus') == 'Not Found':
        return coverage
    components = major_components_lookup(context, vin)
    result = {**coverage, **components}
    result['verificationStatus'] = 'Verified'
    result['source'] = 'OWL Coverage Info + Major Components'
    log(f'OWL COMPLETE {vin}: in-service={result.get("inServiceDate") or "blank"}; engine={result.get("engineSerialNumber") or "blank"}; Allison={result.get("allisonTransmissionSerialNumber") or "blank"}')
    return result


def main() -> int:
    if not VINS:
        RESULT.write_text('{}', encoding='utf-8')
        return 0
    out: dict[str, Any] = {}
    with sync_playwright() as p:
        context = launch_context(p)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(OWL_SIGNON_URL, wait_until='domcontentloaded', timeout=120_000)
            inject_hint(page, 'Diehl VIN: OWL opened. Complete Freightliner login/MFA if requested.')
            wait_logged_in(context)
            for vin in VINS:
                try:
                    out[vin] = lookup_one(context, vin)
                except Exception as exc:
                    log(f'OWL lookup failed for {vin}: {exc}')
                    out[vin] = {'vin': vin, '_error': str(exc), 'source': 'OWL'}
        finally:
            try:
                context.close()
            except Exception:
                pass
    RESULT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        log(f'FATAL OWL LOOKUP ERROR: {exc}')
        RESULT.write_text(json.dumps({'_error': str(exc)}), encoding='utf-8')
        raise
