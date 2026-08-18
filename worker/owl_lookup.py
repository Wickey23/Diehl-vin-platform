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
    """Find the main OWL Product S/N field, never the left-side Quick Search box."""
    try:
        rows = frame.locator('tr')
        for i in range(rows.count()):
            row = rows.nth(i)
            text = re.sub(r'\s+', ' ', row.inner_text(timeout=500) or '').strip()
            if re.search(r'\bProduct\s+S/N\s*:', text, re.I):
                inputs = row.locator('input[type="text"], input:not([type])')
                for j in range(inputs.count()):
                    item = inputs.nth(j)
                    if item.is_visible() and item.is_enabled():
                        return item
    except Exception:
        pass

    try:
        labels = frame.get_by_text(re.compile(r'^\s*Product\s+S/N\s*:\s*$', re.I), exact=True)
        for i in range(labels.count()):
            label = labels.nth(i)
            if not label.is_visible():
                continue
            row = label.locator('xpath=ancestor::tr[1]')
            inputs = row.locator('input[type="text"], input:not([type])')
            for j in range(inputs.count()):
                item = inputs.nth(j)
                if item.is_visible() and item.is_enabled():
                    return item
    except Exception:
        pass

    return None


def wait_logged_in(context, timeout: int = 240) -> None:
    deadline=time.time()+timeout
    while time.time()<deadline:
        for page,frame in frames(context):
            text=body_text(frame)
            url=(getattr(frame,'url','') or '').lower()
            if re.search(r'Coverage\s+Info|Major\s+Components|Online\s+Warranty|OWL\s+Home',text,re.I) or '/iwarranty/' in url and 'signon' not in url:
                log('OWL authenticated session is ready.')
                return
            inject_hint(page,'Diehl VIN: complete your Freightliner/OWL login and MFA. The worker will continue automatically.')
        time.sleep(1)
    raise RuntimeError('OWL login did not become ready within 4 minutes. Complete login/MFA and retry.')


def open_owl_url(context, url: str, label: str):
    page = context.pages[0] if context.pages else context.new_page()
    log(f'Opening OWL {label}: {url}')
    page.goto(url, wait_until='domcontentloaded', timeout=120_000)
    page.wait_for_timeout(700)
    return page


def wait_for_search_page(context, timeout: int = 30):
    deadline=time.time()+timeout
    while time.time()<deadline:
        for page,frame in frames(context):
            vin_input=find_vin_input(frame)
            if vin_input is not None: return page,frame,vin_input
        time.sleep(.4)
    raise RuntimeError('OWL page opened, but the main Product S/N field could not be found.')


def submit_vin(context, vin: str):
    page,frame,vin_input=wait_for_search_page(context)

    for attempt in range(1, 4):
        try:
            vin_input.click()
            vin_input.fill('')
            vin_input.type(vin, delay=35)
            page.wait_for_timeout(250)
            actual = (vin_input.input_value() or '').strip().upper()
            log(f'OWL {vin}: Product S/N fill attempt {attempt}; field contains {actual or "[blank]"}.')
            if actual == vin:
                break
        except Exception:
            actual = ''
        if attempt == 3:
            raise RuntimeError(f'OWL Product S/N field did not contain VIN {vin}; refusing to press Tab.')
        page,frame,vin_input=wait_for_search_page(context,10)

    log(f'OWL {vin}: Product S/N verified; waiting 1 full second before Tab.')
    page.wait_for_timeout(1000)
    actual = (vin_input.input_value() or '').strip().upper()
    if actual != vin:
        raise RuntimeError(f'OWL Product S/N changed before Tab. Expected {vin}, found {actual or "[blank]"}.')
    log(f'OWL {vin}: 1 second elapsed and Product S/N still verified; pressing Tab now.')
    vin_input.press('Tab')
    page.wait_for_timeout(1200)

    if 'QuickSearch' in (page.url or '') or re.search(r'Quick\s+Search', body_text(frame), re.I):
        raise RuntimeError('OWL navigated to Quick Search after Tab; Product S/N focus was not retained.')

    previous=''; stable=0; deadline=time.time()+45
    while time.time()<deadline:
        page.wait_for_timeout(650); current=body_text(frame)
        if current==previous and len(current)>40: stable+=1
        else: stable=0
        previous=current; normalized=re.sub(r'[^A-Z0-9]','',current.upper())
        if vin in normalized and stable>=1: break
        if re.search(r'not\s+found|no\s+(vehicle|record|coverage|results?)|invalid\s+(vin|serial)',current,re.I) and stable>=1: break
        if stable>=3: break
    return page,frame


def norm(value: str) -> str:
    return re.sub(r'\s+',' ',value or '').strip()


def labeled(text: str, labels: list[str]) -> str:
    for label in labels:
        for pattern in (rf'{label}\s*[:\-]?\s*([^\n\r|]{{1,160}})',rf'{label}\s*[\n\r]+\s*([^\n\r]{{1,160}})'):
            m=re.search(pattern,text,re.I)
            if m:
                value=norm(m.group(1))
                if value and not re.fullmatch(label,value,re.I): return value
    return ''


def table_rows(frame) -> list[str]:
    try: return frame.locator('tr').all_inner_texts()
    except Exception: return []


def extract_serial_from_rows(rows: list[str], words: list[str]) -> str:
    for row in rows:
        compact=norm(row)
        if not all(re.search(word,compact,re.I) for word in words): continue
        m=re.search(r'(?:Serial(?:\s+Number|\s+No\.?)?|S/N)\s*[:#\-]?\s*([A-Z0-9][A-Z0-9\-]{4,30})',compact,re.I)
        if m: return m.group(1).upper()
        tokens=re.findall(r'\b[A-Z0-9][A-Z0-9\-]{5,30}\b',compact.upper())
        ignored={'ALLISON','ENGINE','TRANSMISSION','COMPONENT','SERIAL','NUMBER'}
        candidates=[t for t in tokens if t not in ignored and not t.isdigit()]
        if candidates: return candidates[-1]
    return ''


def coverage_lookup(context, vin: str) -> dict[str, Any]:
    open_owl_url(context, OWL_COVERAGE_URL, 'Coverage Info / Check Coverage')
    page,frame=submit_vin(context,vin); inject_hint(page,f'Diehl VIN: reading Coverage Info for {vin}')
    text=body_text(frame); compact=norm(text)
    if re.search(r'not\s+found|no\s+(vehicle|record|coverage|results?)|invalid\s+(vin|serial)',compact,re.I):
        return {'vin':vin,'verificationStatus':'Not Found','source':'OWL Coverage Info','customerResult':'VIN not found in OWL Coverage Info'}
    in_service_date=labeled(text,[r'In[- ]?Service\s+Date',r'Warranty\s+Start\s+Date',r'Inservice\s+Date'])
    in_service_status=labeled(text,[r'In[- ]?Service\s+Status',r'Warranty\s+Status'])
    mileage=labeled(text,[r'Mileage',r'Odometer'])
    customer=labeled(text,[r'Registered\s+Customer\s+Name',r'Customer\s+Name',r'Owner\s+Name'])
    account=labeled(text,[r'Registered\s+Customer\s+Account',r'Customer\s+Account'])
    warranty_status=labeled(text,[r'Warranty\s+Status',r'Coverage\s+Status'])
    return {'vin':vin,'verificationStatus':'Verified','inServiceStatus':in_service_status or ('In Service' if in_service_date else ''),'inServiceDate':in_service_date,'mileage':mileage,'customerResult':customer,'customerName':customer,'registeredCustomerName':customer,'registeredCustomerAccount':account,'warrantyStatus':warranty_status,'warrantyCoverage':text[:12000],'source':'OWL Coverage Info'}


def major_components_lookup(context, vin: str) -> dict[str, str]:
    open_owl_url(context, OWL_MAJOR_COMPONENTS_URL, 'Major Components')
    page,frame=submit_vin(context,vin); inject_hint(page,f'Diehl VIN: reading Major Components for {vin}')
    text=body_text(frame); rows=table_rows(frame)
    engine=extract_serial_from_rows(rows,[r'engine']) or labeled(text,[r'Engine\s+Serial(?:\s+Number|\s+No\.?)?',r'Engine\s+S/N'])
    allison=extract_serial_from_rows(rows,[r'allison']) or labeled(text,[r'Allison(?:\s+Transmission)?\s+Serial(?:\s+Number|\s+No\.?)?',r'Allison\s+S/N'])
    return {'engineSerialNumber':engine,'allisonTransmissionSerialNumber':allison,'majorComponentsText':text[:8000]}


def lookup_one(context, vin: str) -> dict[str, Any]:
    coverage=coverage_lookup(context,vin)
    if coverage.get('verificationStatus')=='Not Found': return coverage
    result={**coverage,**major_components_lookup(context,vin)}
    log(f'OWL {vin}: in-service={result.get("inServiceDate") or "blank"}; engine={result.get("engineSerialNumber") or "blank"}; allison={result.get("allisonTransmissionSerialNumber") or "blank"}')
    return result


def main() -> int:
    if not VINS:
        RESULT.write_text('{}',encoding='utf-8'); return 0
    out: dict[str,Any]={}
    with sync_playwright() as p:
        context=launch_context(p)
        try:
            page=context.pages[0] if context.pages else context.new_page()
            page.goto(OWL_SIGNON_URL,wait_until='domcontentloaded',timeout=120_000)
            inject_hint(page,'Diehl VIN: OWL opened. Complete Freightliner login/MFA if requested.')
            wait_logged_in(context)
            for vin in VINS:
                try: out[vin]=lookup_one(context,vin)
                except Exception as exc:
                    log(f'OWL lookup failed for {vin}: {exc}'); out[vin]={'vin':vin,'_error':str(exc),'source':'OWL'}
        finally:
            try: context.close()
            except Exception: pass
    RESULT.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8'); return 0


if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as exc:
        log(f'FATAL OWL LOOKUP ERROR: {exc}'); RESULT.write_text(json.dumps({'_error':str(exc)}),encoding='utf-8'); raise
