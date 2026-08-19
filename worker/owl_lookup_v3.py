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


def canon(value: Any) -> str:
    return re.sub(r'[^A-Z0-9]+', ' ', clean(value).upper()).strip()


def launch_context(playwright):
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    kwargs = dict(user_data_dir=str(PROFILE_DIR), headless=False, viewport={'width': 1500, 'height': 900}, accept_downloads=True)
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
        return frame.locator('body').inner_text(timeout=1200)
    except Exception:
        return ''


def main_signature(frame, vin: str = '') -> str:
    try:
        return str(frame.evaluate("""({minX,vin}) => {
          const norm=s=>(s||'').replace(/\s+/g,' ').trim();
          const pieces=[];
          for(const el of document.querySelectorAll('td,th,input,select,textarea')){
            const r=el.getBoundingClientRect();
            if(!r.width || !r.height || r.left<minX) continue;
            let value='';
            if(el.tagName==='INPUT' || el.tagName==='TEXTAREA') value=el.value||'';
            else if(el.tagName==='SELECT') value=el.options[el.selectedIndex]?.text||el.value||'';
            else value=el.innerText||el.textContent||'';
            value=norm(value);
            if(!value || value.toUpperCase()===vin.toUpperCase()) continue;
            pieces.push(value);
          }
          return pieces.join('|');
        }""", {'minX': MIN_MAIN_X, 'vin': vin}))
    except Exception:
        return ''


def wait_logged_in(context, timeout: int = 240) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        for _page, frame in iter_frames(context):
            text = body_text(frame)
            url = (frame.url or '').lower()
            if re.search(r'OWL\s+Home|Coverage\s+Info|Major\s+Components|Online\s+Warranty', text, re.I) or ('/iwarranty/' in url and 'signon' not in url):
                return
        time.sleep(.2)
    raise RuntimeError('OWL login did not become ready within 4 minutes.')


def open_url(context, url: str, label: str):
    page = context.pages[0] if context.pages else context.new_page()
    log(f'Opening OWL {label}')
    page.goto(url, wait_until='domcontentloaded', timeout=120_000)
    return page


def _assign_main_product_sn_id(frame) -> str:
    try:
        return frame.evaluate("""(minX) => {
          const norm=s=>(s||'').replace(/\s+/g,' ').trim();
          const usable=input=>{
            if(!input || input.disabled) return false;
            if((input.getAttribute('type')||'text').toLowerCase()!=='text') return false;
            const r=input.getBoundingClientRect();
            if(!r.width || !r.height || r.left<minX) return false;
            let n=input;
            while(n&&n!==document.body){
              const sig=((n.id||'')+' '+(n.className||'')+' '+(n.getAttribute?.('name')||'')).toLowerCase();
              if(/quick.?search|left.?nav|left.?menu|side.?nav|sidebar/.test(sig)) return false;
              n=n.parentElement;
            }
            return true;
          };
          const found=[];
          for(const el of document.querySelectorAll('td,th,label,span,b,font')){
            if(!/^Product\s+S\/N\s*:?$/i.test(norm(el.innerText||el.textContent))) continue;
            const cell=el.closest('td,th'); const row=el.closest('tr');
            if(cell?.nextElementSibling){for(const input of cell.nextElementSibling.querySelectorAll('input'))if(usable(input))found.push({input,score:300});}
            if(row){for(const input of row.querySelectorAll('input'))if(usable(input))found.push({input,score:200});}
          }
          if(!found.length) return '';
          found.sort((a,b)=>b.score-a.score);
          const input=found[0].input;
          if(!input.id) input.id='diehl-main-product-sn-'+Math.random().toString(36).slice(2);
          return input.id;
        }""", MIN_MAIN_X)
    except Exception:
        return ''


def find_main_product_sn(context, timeout: float = 12.0):
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
            box = item.bounding_box()
            if box and box['x'] >= MIN_MAIN_X:
                return page, frame, item
        time.sleep(.08)
    raise RuntimeError('Could not find the main Product S/N box. Left Quick Search is intentionally ignored.')


def exact_label_value(frame, labels: list[str]) -> str:
    wanted = [canon(x) for x in labels]
    try:
        return clean(frame.evaluate("""wanted => {
          const canon=s=>(s||'').replace(/[^A-Za-z0-9]+/g,' ').trim().toUpperCase();
          const valueOf=cell=>{
            if(!cell) return '';
            const form=cell.querySelector('input,select,textarea');
            if(form){
              if(form.tagName==='SELECT') return (form.options[form.selectedIndex]?.text||form.value||'').trim();
              return (form.value||'').trim();
            }
            return (cell.innerText||cell.textContent||'').replace(/\s+/g,' ').trim();
          };
          for(const cell of document.querySelectorAll('td,th')){
            const label=canon(cell.innerText||cell.textContent);
            if(!wanted.includes(label)) continue;
            const next=cell.nextElementSibling;
            const v=valueOf(next);
            if(v) return v;
            const row=cell.closest('tr');
            if(row){
              const cells=Array.from(row.children);
              const idx=cells.indexOf(cell);
              if(idx>=0&&idx+1<cells.length){const rv=valueOf(cells[idx+1]);if(rv)return rv;}
            }
          }
          return '';
        }""", wanted))
    except Exception:
        return ''


def exact_table(frame, required_headers: list[str]) -> list[dict[str, str]]:
    wanted = [canon(x) for x in required_headers]
    try:
        rows = frame.evaluate("""wanted => {
          const norm=s=>(s||'').replace(/\s+/g,' ').trim();
          const canon=s=>norm(s).replace(/[^A-Za-z0-9]+/g,' ').trim().toUpperCase();
          for(const table of document.querySelectorAll('table')){
            const trs=Array.from(table.querySelectorAll('tr'));
            let headerIndex=-1, headers=[];
            for(let i=0;i<trs.length;i++){
              const cells=Array.from(trs[i].querySelectorAll(':scope > th,:scope > td')).map(c=>norm(c.innerText||c.textContent));
              const cc=cells.map(canon);
              if(wanted.every(h=>cc.includes(h))){headerIndex=i;headers=cells;break;}
            }
            if(headerIndex<0) continue;
            const out=[];
            for(let i=headerIndex+1;i<trs.length;i++){
              const cells=Array.from(trs[i].querySelectorAll(':scope > td,:scope > th')).map(c=>norm(c.innerText||c.textContent));
              if(!cells.some(Boolean)) continue;
              const rec={};
              headers.forEach((h,j)=>{if(h&&j<cells.length)rec[h]=cells[j];});
              if(Object.keys(rec).length)out.push(rec);
            }
            return out;
          }
          return [];
        }""", wanted)
        return [{clean(k): clean(v) for k, v in row.items()} for row in (rows or [])]
    except Exception:
        return []


def record_value(record: dict[str, str], exact_header: str) -> str:
    target = canon(exact_header)
    for key, value in record.items():
        if canon(key) == target:
            return clean(value)
    return ''


def submit_vin(context, vin: str):
    page, frame, field = find_main_product_sn(context)
    if 'quicksearch' in (page.url or '').lower():
        raise RuntimeError('OWL is on Quick Search; refusing to type there.')
    box = field.bounding_box()
    if not box or box['x'] < MIN_MAIN_X:
        raise RuntimeError('Product S/N candidate is inside the left sidebar.')

    field.click()
    field.fill(vin)
    actual = clean(field.input_value()).upper()
    if actual != vin:
        field.fill('')
        field.type(vin, delay=8)
        actual = clean(field.input_value()).upper()
    if actual != vin:
        raise RuntimeError(f'Product S/N did not contain VIN {vin}.')

    before = main_signature(frame, vin)
    field.press('Tab')
    log(f'OWL {vin}: VIN verified in main Product S/N and Tab sent immediately.')
    return page, frame, before


def wait_for_result(context, vin: str, page, before_signature: str, timeout: float = 15.0):
    deadline = time.time() + timeout
    last_signature = before_signature
    stable_since = None
    while time.time() < deadline:
        if 'quicksearch' in (page.url or '').lower():
            raise RuntimeError('OWL navigated to Quick Search; result rejected.')
        for _page, frame in iter_frames(context):
            text = body_text(frame)
            if re.search(r'not\s+found|invalid\s+(vin|serial)|no\s+matching', text, re.I):
                return frame
            sig = main_signature(frame, vin)
            if sig and sig != before_signature:
                if sig == last_signature:
                    if stable_since is None:
                        stable_since = time.time()
                    elif time.time() - stable_since >= .15:
                        return frame
                else:
                    last_signature = sig
                    stable_since = time.time()
        time.sleep(.08)
    raise RuntimeError(f'OWL did not populate new data for VIN {vin} within {timeout:g} seconds.')


def coverage_lookup(context, vin: str) -> dict[str, Any]:
    page = open_url(context, OWL_COVERAGE_URL, 'Coverage Info')
    page, _frame, before = submit_vin(context, vin)
    frame = wait_for_result(context, vin, page, before)
    text = body_text(frame)
    if re.search(r'not\s+found|invalid\s+(vin|serial)|no\s+matching', text, re.I):
        return {'vin': vin, 'verificationStatus': 'Not Found', 'customerResult': 'VIN not found in OWL', 'source': 'OWL Coverage Info'}

    in_service_date = exact_label_value(frame, ['In Service Date', 'In-Service Date'])
    mileage = exact_label_value(frame, ['Mileage', 'In Service Mileage', 'In-Service Mileage', 'In Service Distance', 'In-Service Distance'])
    customer_name = exact_label_value(frame, ['Registered Customer Name', 'Customer Name', 'Registered Customer'])
    customer_account = exact_label_value(frame, ['Registered Customer Account', 'Customer Account', 'Customer Number'])
    warranty_status = exact_label_value(frame, ['Warranty Status', 'Coverage Status'])
    build_date = exact_label_value(frame, ['Build Date', 'Manufacture Date', 'Manufactured Date'])

    coverage_rows = exact_table(frame, ['Coverage'])
    if not coverage_rows:
        coverage_rows = exact_table(frame, ['Description'])

    return {
        'vin': vin,
        'verificationStatus': 'Verified',
        'productSerialNumber': vin,
        'buildDate': build_date,
        'inServiceStatus': 'In Service' if in_service_date else '',
        'inServiceDate': in_service_date,
        'mileage': mileage,
        'customerResult': customer_name,
        'customerName': customer_name,
        'registeredCustomerName': customer_name,
        'registeredCustomerAccount': customer_account,
        'warrantyStatus': warranty_status,
        'warrantyCoverage': '\n'.join(' | '.join(f'{k}: {v}' for k, v in row.items() if v) for row in coverage_rows),
        'coverageRecordsJson': json.dumps(coverage_rows, ensure_ascii=False),
        'coverageFieldsJson': json.dumps({
            'In Service Date': in_service_date,
            'Mileage': mileage,
            'Registered Customer Name': customer_name,
            'Registered Customer Account': customer_account,
            'Warranty Status': warranty_status,
            'Build Date': build_date,
        }, ensure_ascii=False),
        'source': 'OWL Coverage Info + Major Components',
    }


def major_lookup(context, vin: str) -> dict[str, Any]:
    page = open_url(context, OWL_MAJOR_URL, 'Major Components')
    page, _frame, before = submit_vin(context, vin)
    frame = wait_for_result(context, vin, page, before)

    chassis_sn = exact_label_value(frame, ['Chassis S/N'])
    vehicle_model = exact_label_value(frame, ['Make/Base/Model'])
    in_service_date = exact_label_value(frame, ['In Service Date'])
    vocation = exact_label_value(frame, ['Vocation'])
    unit_number = exact_label_value(frame, ['Unit #'])
    wheelbase = exact_label_value(frame, ['Wheelbase'])
    gvwr = exact_label_value(frame, ['GVW'])

    rows = exact_table(frame, ['Component', 'MFG', 'Model', 'Component S/N'])
    engine_row = None
    allison_row = None
    for row in rows:
        component = canon(record_value(row, 'Component'))
        mfg = canon(record_value(row, 'MFG'))
        if engine_row is None and component == 'ENGINE':
            engine_row = row
        if allison_row is None and ('ALLISON' in component or 'TRANSMISSION' in component or 'ALLISON' in mfg):
            allison_row = row

    def row_field(row: dict[str, str] | None, header: str) -> str:
        return record_value(row or {}, header)

    engine_serial = row_field(engine_row, 'Component S/N')
    engine_model = row_field(engine_row, 'Model')
    engine_mfg = row_field(engine_row, 'MFG')
    allison_serial = row_field(allison_row, 'Component S/N')
    transmission_model = row_field(allison_row, 'Model')
    transmission_mfg = row_field(allison_row, 'MFG')

    return {
        'vehicleModel': vehicle_model,
        'inServiceDateFromMajorComponents': in_service_date,
        'chassisSerialNumber': chassis_sn or vin,
        'unitNumber': unit_number,
        'vocation': vocation,
        'wheelbase': wheelbase,
        'gvwr': gvwr,
        'engineSerialNumber': engine_serial,
        'engineModel': engine_model,
        'engineManufacturer': engine_mfg,
        'allisonTransmissionSerialNumber': allison_serial,
        'transmissionModel': transmission_model,
        'transmissionManufacturer': transmission_mfg,
        'majorComponentsText': '\n'.join(' | '.join(f'{k}: {v}' for k, v in row.items() if v) for row in rows),
        'majorComponentsJson': json.dumps(rows, ensure_ascii=False),
        'majorComponentFieldsJson': json.dumps({
            'Chassis S/N': chassis_sn,
            'Make/Base/Model': vehicle_model,
            'In Service Date': in_service_date,
            'Unit #': unit_number,
            'Vocation': vocation,
            'Wheelbase': wheelbase,
            'GVW': gvwr,
        }, ensure_ascii=False),
    }


def lookup_one(context, vin: str) -> dict[str, Any]:
    coverage = coverage_lookup(context, vin)
    if coverage.get('verificationStatus') == 'Not Found':
        return coverage
    major = major_lookup(context, vin)
    result = {**coverage, **major}
    if major.get('inServiceDateFromMajorComponents'):
        result['inServiceDate'] = major['inServiceDateFromMajorComponents']
        result['inServiceStatus'] = 'In Service'
    result.pop('inServiceDateFromMajorComponents', None)
    result['verificationStatus'] = 'Verified'
    log(
        f'OWL COMPLETE {vin}: date={result.get("inServiceDate") or "blank"}; '
        f'customer={result.get("customerName") or "blank"}; '
        f'engineSN={result.get("engineSerialNumber") or "blank"}; '
        f'allisonSN={result.get("allisonTransmissionSerialNumber") or "blank"}'
    )
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
        log(f'FATAL OWL ERROR: {exc}')
        RESULT.write_text(json.dumps({'_error': str(exc)}), encoding='utf-8')
        raise
