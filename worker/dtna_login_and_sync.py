from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

APP_NAME = 'DiehlDTNAManual'
ROOT = Path(__file__).resolve().parent
LOCAL_APPDATA = Path(os.environ.get('LOCALAPPDATA', ROOT))
SHARED_ROOT = LOCAL_APPDATA / APP_NAME
PROFILE_DIR = SHARED_ROOT / 'browser_profile'
DATA_ROOT = SHARED_ROOT / 'data'
OUTPUT_DIR = DATA_ROOT / 'output'
REPORT_DIR = DATA_ROOT / 'report_downloads'
HISTORY_DIR = DATA_ROOT / 'history'
CHANGES_DIR = DATA_ROOT / 'changes'
LOG_DIR = DATA_ROOT / 'logs'
STATUS_FILE = DATA_ROOT / 'SYNC_STATUS.txt'
WORKING_EXCEL = OUTPUT_DIR / 'dtna_sales_orders.xlsx'

SALES_URL = 'https://salesorder-dtna.prd.freightliner.com/SalesOrder/'
API_URL = 'https://salesorder-dtna.prd.freightliner.com/SalesOrder/getMainTableData'
REPORT_URL = 'https://dealerreporting-dtna.prd.freightliner.com/DealerReporting/?app=salesorder'
PAYLOAD = {
    'soCode': 'GNPD', 'chassisDate': '', 'glider': 'N', 'customer': 'default',
    'baseModel': 'default', 'orderPreApproval': True, 'orderToReview': True,
    'orderVehSerNo': 'default', 'poUnitNumberSales': 'default', 'salesPerson': 'default',
    'soCdList': ''
}
TRACK_FIELDS = ['statusMsg','statusDate','scheduled','chassisStartDate','destRecvDate','origProjDelvDate','projDelvDate','dispatchDate','deliveredDate','customer','baseMdl','errorFlag']


def ensure_dirs():
    for p in (PROFILE_DIR, OUTPUT_DIR, REPORT_DIR, HISTORY_DIR, CHANGES_DIR, LOG_DIR): p.mkdir(parents=True, exist_ok=True)


def log(message: str):
    ensure_dirs(); stamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'); line=f'[{stamp}] {message}'; print(line)
    with (LOG_DIR/'dtna_manual_sync.log').open('a',encoding='utf-8') as f: f.write(line+'\n')


def status(**values):
    ensure_dirs(); STATUS_FILE.write_text('\n'.join(f'{k}: {v}' for k,v in values.items()),encoding='utf-8')


def clean(v: Any) -> str:
    if v is None: return ''
    try:
        if pd.isna(v): return ''
    except Exception: pass
    return str(v).strip()


def norm_header(v: Any) -> str: return re.sub(r'[^a-z0-9]','',clean(v).lower())
def norm_serial(v: Any) -> str: return re.sub(r'[^A-Z0-9]','',clean(v).upper())
def norm_vin(v: Any) -> str:
    x=norm_serial(v); return x if len(x)==17 else ''
def norm_date(v: Any) -> str:
    raw=clean(v)
    if not raw:return ''
    d=pd.to_datetime(raw,errors='coerce')
    return raw if pd.isna(d) else d.strftime('%Y-%m-%d')


def normalize_response(value: Any):
    if isinstance(value,list): return [r for r in value if isinstance(r,dict)]
    if isinstance(value,dict):
        for k in ('data','results','records','items'):
            if isinstance(value.get(k),list): return [r for r in value[k] if isinstance(r,dict)]
    raise ValueError(f'Unexpected DTNA response type: {type(value).__name__}')


def launch_context(p):
    args=dict(user_data_dir=str(PROFILE_DIR),headless=False,viewport={'width':1500,'height':900},accept_downloads=True)
    try:return p.chromium.launch_persistent_context(channel='msedge',**args)
    except PlaywrightError:return p.chromium.launch_persistent_context(**args)


def auto_login(page):
    page.wait_for_timeout(1000)
    for pat in (r'^Login$',r'^Log\s*In$',r'^Sign\s*In$',r'Continue'):
        for loc in (page.get_by_role('button',name=re.compile(pat,re.I)),page.get_by_role('link',name=re.compile(pat,re.I))):
            try:
                for i in range(loc.count()):
                    if loc.nth(i).is_visible(): loc.nth(i).click(); page.wait_for_timeout(1800); return
            except Exception: pass


def fetch_sales(page):
    return page.evaluate("""async ({apiUrl,payload})=>{const r=await fetch(apiUrl,{method:'POST',credentials:'include',headers:{'Accept':'application/json, text/plain, */*','Content-Type':'application/json'},body:JSON.stringify(payload)});const t=await r.text();if(!r.ok)throw new Error(`HTTP ${r.status}: ${t.slice(0,500)}`);if(!(r.headers.get('content-type')||'').includes('application/json'))throw new Error('DTNA login is not complete');return JSON.parse(t)}""",{'apiUrl':API_URL,'payload':PAYLOAD})


def click_visible(page,patterns):
    for pat in patterns:
        for loc in (page.get_by_role('button',name=re.compile(pat,re.I)),page.get_by_role('link',name=re.compile(pat,re.I)),page.get_by_text(re.compile(pat,re.I),exact=False)):
            try:
                for i in range(loc.count()):
                    if loc.nth(i).is_visible(): loc.nth(i).click(); return True
            except Exception: pass
    return False


def choose_auto_vin(page):
    for i in range(page.locator('select').count()):
        sel=page.locator('select').nth(i)
        try:
            opts=sel.locator('option').all_text_contents(); match=next((x for x in opts if 'AUTO VIN' in x.upper()),None)
            if match: sel.select_option(label=match); return
        except Exception: pass
    for loc in (page.get_by_text('AUTO VIN',exact=True),page.get_by_role('option',name='AUTO VIN')):
        try:
            if loc.count() and loc.first.is_visible(): loc.first.click(); return
        except Exception: pass
    raise RuntimeError('Could not select the saved AUTO VIN template.')


def set_widest_date_range(page):
    # DTNA changes this control occasionally. Try automatic selection first, then allow manual completion.
    if not click_visible(page,[r'Order\s*Received\s*Date',r'calendar',r'choose\s*date']):
        print('Click the calendar icon next to Order Received Date.'); input('Press ENTER when the picker is open... ')
    page.wait_for_timeout(600)
    try:
        hit=page.get_by_text(re.compile(r'-\s*48\s*months\s*to\s*\+\s*12\s*months',re.I),exact=False)
        if hit.count() and hit.first.is_visible(): hit.first.click()
        else: raise RuntimeError()
    except Exception:
        print('Select "-48 months to +12 months" in Dealer Reporting.'); input('Press ENTER when selected... ')
    try:
        ok=page.get_by_role('button',name=re.compile(r'^OK$',re.I))
        if ok.count() and ok.last.is_visible(): ok.last.click()
    except Exception: pass


def download_auto_vin(page):
    page.goto(REPORT_URL,wait_until='domcontentloaded',timeout=120000); auto_login(page); page.wait_for_timeout(2500)
    try: page.get_by_text(re.compile(r'Order\s*Received\s*Date',re.I),exact=False).first.wait_for(timeout=10000)
    except Exception:
        print('Dealer Reporting needs login/MFA. Complete it in the browser.'); input('Press ENTER when the report page is visible... ')
    set_widest_date_range(page)
    if not click_visible(page,[r'Export\s*to\s*Excel',r'^Export$']): raise RuntimeError('Could not find Export to Excel.')
    page.wait_for_timeout(1000); choose_auto_vin(page); page.wait_for_timeout(500)
    with page.expect_download(timeout=120000) as info:
        if not click_visible(page,[r'^Export$',r'Download',r'Export\s*to\s*Excel']): raise RuntimeError('Could not click final Export button.')
    dl=info.value; suffix=Path(dl.suggested_filename).suffix or '.xlsx'; dest=REPORT_DIR/f'AUTO_VIN_{datetime.now():%Y%m%d_%H%M%S}{suffix}'; dl.save_as(str(dest)); return dest


def read_report(path): return pd.read_csv(path,dtype=str).fillna('') if path.suffix.lower()=='.csv' else pd.read_excel(path,dtype=str).fillna('')
def find_col(df,names):
    n={norm_header(c):c for c in df.columns}
    for x in names:
        if norm_header(x) in n:return n[norm_header(x)]
    for k,v in n.items():
        if any(norm_header(x) in k for x in names):return v
    return None


def report_map(path):
    df=read_report(path); s=find_col(df,['Serial Number','Vehicle Serial Number','Serial No']); d=find_col(df,['In-Service Date','In Service Date']); v=find_col(df,['VIN','Vehicle Identification Number','Full VIN'])
    if not s or not d or not v: raise RuntimeError(f'AUTO VIN is missing required columns. Found: {list(df.columns)}')
    out={}
    for _,row in df.iterrows():
        serial=norm_serial(row.get(s,'')); vin=norm_vin(row.get(v,'')); date=norm_date(row.get(d,'')); keys=set()
        if serial: keys.update([serial,serial[-8:],serial[-7:]])
        if vin: keys.update([vin[-8:],vin[-7:]])
        for k in keys: out[k]={'VIN':vin,'inServiceDate':date}
    return out


def enrich(rows,mapping):
    for row in rows:
        vals=[]
        for x in (norm_serial(row.get('serialNo')),norm_serial(row.get('leadSerialNo'))):
            if x: vals.extend([x,x[-8:],x[-7:]])
        m=next((mapping[k] for k in vals if k in mapping),None); row['VIN']=m.get('VIN','') if m else ''; row['inServiceDate']=m.get('inServiceDate','') if m else ''; row['vinSource']='Dealer Reporting' if m else ''


def row_key(r): return '|'.join(clean(r.get(k)) for k in ('serialNo','leadSerialNo','soCode','baseMdl','customer'))
def old_snapshot():
    p=HISTORY_DIR/'latest_snapshot.json'
    return normalize_response(json.loads(p.read_text(encoding='utf-8'))) if p.exists() else []


def compare(old,new):
    a={row_key(r):r for r in old}; b={row_key(r):r for r in new}; when=datetime.now().strftime('%Y-%m-%d %H:%M:%S'); changes=[]
    for k,r in b.items():
        if k not in a:
            if a: changes.append({'changeTime':when,'changeType':'NEW ORDER','serialNo':clean(r.get('serialNo')),'VIN':clean(r.get('VIN')),'field':'','oldValue':'','newValue':'Order added'})
            continue
        for f in TRACK_FIELDS:
            x,y=clean(a[k].get(f)),clean(r.get(f))
            if x!=y: changes.append({'changeTime':when,'changeType':'FIELD CHANGED','serialNo':clean(r.get('serialNo')),'VIN':clean(r.get('VIN')),'field':f,'oldValue':x,'newValue':y})
    return changes


def save(rows,changes):
    ensure_dirs(); df=pd.json_normalize(rows); tmp=OUTPUT_DIR/'dtna_sales_orders.new.xlsx'; df.to_excel(tmp,index=False,sheet_name='DTNA_Orders'); os.replace(tmp,WORKING_EXCEL); df.to_csv(OUTPUT_DIR/'dtna_sales_orders.csv',index=False,encoding='utf-8-sig')
    (OUTPUT_DIR/'dtna_sales_orders_raw.json').write_text(json.dumps(rows,indent=2,default=str),encoding='utf-8')
    c=pd.DataFrame(changes); c.to_excel(CHANGES_DIR/'latest_changes.xlsx',index=False,sheet_name='Latest_Changes'); c.to_csv(CHANGES_DIR/'latest_changes.csv',index=False,encoding='utf-8-sig')
    snap=json.dumps(rows,indent=2,default=str); (HISTORY_DIR/'latest_snapshot.json').write_text(snap,encoding='utf-8'); (HISTORY_DIR/f'snapshot_{datetime.now():%Y%m%d_%H%M%S}.json').write_text(snap,encoding='utf-8')
    status(status='SUCCESS',lastRun=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),orderCount=len(rows),vinCount=sum(bool(clean(r.get('VIN'))) for r in rows),inServiceDateCount=sum(bool(clean(r.get('inServiceDate'))) for r in rows),changeCount=len(changes),loginProfile=PROFILE_DIR)


def main():
    ensure_dirs(); status(status='RUNNING',lastRun=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),message='DTNA browser starting',loginProfile=PROFILE_DIR)
    with sync_playwright() as p:
        ctx=launch_context(p)
        try:
            page=ctx.pages[0] if ctx.pages else ctx.new_page(); page.goto(SALES_URL,wait_until='domcontentloaded',timeout=120000); auto_login(page)
            try:data=fetch_sales(page)
            except Exception:
                print('DTNA needs login/MFA. Complete it in the browser and wait for Sales Order.'); input('Press ENTER to continue... '); data=fetch_sales(page)
            rows=normalize_response(data); log(f'Downloaded {len(rows):,} Sales Order rows'); report=download_auto_vin(page); enrich(rows,report_map(report))
        finally: ctx.close()
    old=old_snapshot(); changes=compare(old,rows); save(rows,changes); print(f'SUCCESS: {len(rows):,} orders, {len(changes):,} changes'); print('Excel:',WORKING_EXCEL)


if __name__=='__main__':
    try: main()
    except Exception as exc:
        log(f'ERROR: {exc}'); status(status='FAILED',lastRun=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),message=exc,loginProfile=PROFILE_DIR); print('ERROR:',exc); input('Press ENTER to close... '); raise
