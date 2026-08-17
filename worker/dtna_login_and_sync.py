from __future__ import annotations

import argparse
import json
import os
import re
import time
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
    'baseModel': 'default', 'orderPreApproval': True, 'orderToReview': False,
    'orderVehSerNo': 'default', 'poUnitNumberSales': 'default', 'salesPerson': 'default',
    'soCdList': ''
}
TRACK_FIELDS = ['statusMsg','statusDate','scheduled','chassisStartDate','destRecvDate','origProjDelvDate','projDelvDate','dispatchDate','deliveredDate','customer','baseMdl','errorFlag']


def ensure_dirs():
    for p in (PROFILE_DIR, OUTPUT_DIR, REPORT_DIR, HISTORY_DIR, CHANGES_DIR, LOG_DIR):
        p.mkdir(parents=True, exist_ok=True)


def log(message: str):
    ensure_dirs()
    stamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{stamp}] {message}'
    print(line)
    with (LOG_DIR / 'dtna_manual_sync.log').open('a', encoding='utf-8') as f:
        f.write(line + '\n')


def status(**values):
    ensure_dirs()
    STATUS_FILE.write_text('\n'.join(f'{k}: {v}' for k, v in values.items()), encoding='utf-8')


def clean(v: Any) -> str:
    if v is None:
        return ''
    try:
        if pd.isna(v):
            return ''
    except Exception:
        pass
    return str(v).strip()


def norm_header(v: Any) -> str:
    return re.sub(r'[^a-z0-9]', '', clean(v).lower())


def norm_serial(v: Any) -> str:
    return re.sub(r'[^A-Z0-9]', '', clean(v).upper())


def norm_vin(v: Any) -> str:
    x = norm_serial(v)
    return x if len(x) == 17 else ''


def norm_date(v: Any) -> str:
    raw = clean(v)
    if not raw:
        return ''
    d = pd.to_datetime(raw, errors='coerce')
    return raw if pd.isna(d) else d.strftime('%Y-%m-%d')


def normalize_response(value: Any):
    if isinstance(value, list):
        return [r for r in value if isinstance(r, dict)]
    if isinstance(value, dict):
        for k in ('data', 'results', 'records', 'items'):
            if isinstance(value.get(k), list):
                return [r for r in value[k] if isinstance(r, dict)]
    raise ValueError(f'Unexpected DTNA response type: {type(value).__name__}')


def launch_context(p):
    args = dict(
        user_data_dir=str(PROFILE_DIR),
        headless=False,
        viewport={'width': 1500, 'height': 900},
        accept_downloads=True,
    )
    try:
        return p.chromium.launch_persistent_context(channel='msedge', **args)
    except PlaywrightError:
        return p.chromium.launch_persistent_context(**args)


def dom_click(locator) -> bool:
    try:
        if locator.count() and locator.first.is_visible():
            locator.first.evaluate('(el) => el.click()')
            return True
    except Exception:
        pass
    return False


def auto_login(page):
    page.wait_for_timeout(800)
    for pat in (r'^Login$', r'^Log\s*In$', r'^Sign\s*In$', r'^Continue$'):
        for loc in (
            page.get_by_role('button', name=re.compile(pat, re.I)),
            page.get_by_role('link', name=re.compile(pat, re.I)),
        ):
            if dom_click(loc):
                page.wait_for_timeout(1200)
                return


def fetch_sales(page):
    return page.evaluate(
        """async ({apiUrl,payload})=>{const r=await fetch(apiUrl,{method:'POST',credentials:'include',headers:{'Accept':'application/json, text/plain, */*','Content-Type':'application/json'},body:JSON.stringify(payload)});const t=await r.text();if(!r.ok)throw new Error(`HTTP ${r.status}: ${t.slice(0,500)}`);if(!(r.headers.get('content-type')||'').includes('application/json'))throw new Error('DTNA login is not complete');return JSON.parse(t)}""",
        {'apiUrl': API_URL, 'payload': PAYLOAD},
    )


def wait_for_sales_page(page, timeout_seconds=300):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        auto_login(page)
        try:
            search = page.get_by_role('button', name=re.compile(r'^Search$', re.I))
            if search.count() and search.first.is_visible():
                return
        except Exception:
            pass
        page.wait_for_timeout(1000)
    raise RuntimeError('DTNA Sales Order did not become ready. Complete login/MFA and retry.')


def uncheck_orders_to_be_reviewed(page):
    pattern = re.compile(r'Orders\s+To\s+Be\s+Reviewed', re.I)
    try:
        control = page.get_by_label(pattern)
        for i in range(control.count()):
            item = control.nth(i)
            if item.is_visible():
                try:
                    if item.is_checked():
                        item.evaluate('(el) => el.click()')
                    return
                except Exception:
                    pass
    except Exception:
        pass

    try:
        boxes = page.locator('input[type="checkbox"]')
        for i in range(boxes.count()):
            box = boxes.nth(i)
            try:
                nearby = box.evaluate("el => (el.closest('label') || el.parentElement || el).innerText || ''")
                if pattern.search(nearby or ''):
                    if box.is_checked():
                        box.evaluate('(el) => el.click()')
                    return
            except Exception:
                pass
    except Exception:
        pass


def search_sales(page):
    wait_for_sales_page(page)
    uncheck_orders_to_be_reviewed(page)
    search = page.get_by_role('button', name=re.compile(r'^Search$', re.I))
    if not dom_click(search):
        raise RuntimeError('Could not press Search on Sales Order.')
    page.wait_for_timeout(1200)


def fetch_all_sales(page):
    search_sales(page)
    last_error = None
    for _ in range(8):
        try:
            rows = normalize_response(fetch_sales(page))
            if rows:
                return rows
        except Exception as exc:
            last_error = exc
        page.wait_for_timeout(1000)
    if last_error:
        raise last_error
    return []


def wait_for_dealer_reporting(page, timeout_seconds=300):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        auto_login(page)
        try:
            label = page.get_by_text(re.compile(r'^\s*Order\s*Received\s*Date\s*$', re.I), exact=False)
            if label.count() and label.first.is_visible():
                return
        except Exception:
            pass
        page.wait_for_timeout(1000)
    raise RuntimeError('Dealer Reporting did not become ready. Complete login/MFA and retry.')


def open_order_received_calendar(page):
    # Target only the date field and its own calendar toggle. Do not click arbitrary text/buttons.
    label = page.get_by_text(re.compile(r'^\s*Order\s*Received\s*Date\s*$', re.I), exact=False)
    try:
        if label.count() and label.first.is_visible():
            field = label.first.locator('xpath=ancestor::*[self::mat-form-field or self::div][1]')
            for selector in (
                'button[aria-label*="calendar" i]',
                'button[aria-haspopup="dialog"]',
                'mat-datepicker-toggle button',
                'button',
            ):
                candidate = field.locator(selector)
                for i in range(candidate.count()):
                    c = candidate.nth(i)
                    if c.is_visible():
                        c.evaluate('(el) => el.click()')
                        page.wait_for_timeout(400)
                        return True
    except Exception:
        pass

    for selector in (
        'button[aria-label*="Order Received" i]',
        'button[aria-label*="calendar" i]',
        'mat-datepicker-toggle button',
    ):
        try:
            candidate = page.locator(selector)
            for i in range(candidate.count()):
                c = candidate.nth(i)
                if c.is_visible():
                    c.evaluate('(el) => el.click()')
                    page.wait_for_timeout(400)
                    return True
        except Exception:
            pass
    return False


def set_widest_date_range(page):
    if not open_order_received_calendar(page):
        raise RuntimeError('Could not open the Order Received Date picker.')

    range_pattern = re.compile(r'^\s*-\s*48\s*months\s*to\s*\+\s*12\s*months\s*$', re.I)
    selected = False
    for loc in (
        page.get_by_role('option', name=range_pattern),
        page.get_by_text(range_pattern, exact=False),
        page.get_by_role('button', name=range_pattern),
    ):
        try:
            for i in range(loc.count()):
                item = loc.nth(i)
                if item.is_visible():
                    item.evaluate('(el) => el.click()')
                    selected = True
                    break
            if selected:
                break
        except Exception:
            pass
    if not selected:
        raise RuntimeError('Could not select -48 months to +12 months.')

    ok = page.get_by_role('button', name=re.compile(r'^OK$', re.I))
    try:
        if ok.count() and ok.last.is_visible():
            ok.last.evaluate('(el) => el.click()')
            page.wait_for_timeout(300)
    except Exception:
        pass

    search = page.get_by_role('button', name=re.compile(r'^Search$', re.I))
    if not dom_click(search):
        raise RuntimeError('Could not press Search in Dealer Reporting.')
    wait_for_report_results(page)


def wait_for_report_results(page, timeout_seconds=75):
    deadline = time.time() + timeout_seconds
    stable = 0
    while time.time() < deadline:
        spinner_visible = False
        for selector in ('mat-spinner', '.mat-progress-spinner', '.mat-mdc-progress-spinner', '[role="progressbar"]'):
            try:
                loc = page.locator(selector)
                spinner_visible = any(loc.nth(i).is_visible() for i in range(loc.count()))
                if spinner_visible:
                    break
            except Exception:
                pass

        export = page.get_by_role('button', name=re.compile(r'Export\s*to\s*Excel|^Export$', re.I))
        export_ready = False
        try:
            export_ready = export.count() > 0 and export.first.is_visible() and not export.first.is_disabled()
        except Exception:
            pass

        if not spinner_visible and export_ready:
            stable += 1
            if stable >= 3:
                return
        else:
            stable = 0
        page.wait_for_timeout(500)
    raise RuntimeError('Dealer Reporting results did not finish loading.')


def click_export_to_excel(page):
    for pat in (r'^Export\s*to\s*Excel$', r'^Export$'):
        loc = page.get_by_role('button', name=re.compile(pat, re.I))
        if dom_click(loc):
            page.wait_for_timeout(500)
            return True
        loc = page.get_by_role('link', name=re.compile(pat, re.I))
        if dom_click(loc):
            page.wait_for_timeout(500)
            return True
    return False


def choose_auto_vin(page):
    # Prefer native selects. This never scans/clicks unrelated comboboxes.
    try:
        for i in range(page.locator('select').count()):
            sel = page.locator('select').nth(i)
            if not sel.is_visible():
                continue
            opts = sel.locator('option').all_text_contents()
            match = next((x for x in opts if re.fullmatch(r'\s*AUTO\s*VIN\s*', x or '', re.I)), None)
            if match:
                sel.select_option(label=match)
                page.wait_for_timeout(300)
                return True
    except Exception:
        pass

    pattern = re.compile(r'^\s*AUTO\s*VIN\s*$', re.I)
    for loc in (
        page.get_by_role('option', name=pattern),
        page.get_by_text(pattern, exact=False),
        page.get_by_role('menuitem', name=pattern),
    ):
        try:
            for i in range(loc.count()):
                item = loc.nth(i)
                if item.is_visible():
                    item.evaluate('(el) => el.click()')
                    page.wait_for_timeout(300)
                    return True
        except Exception:
            pass
    raise RuntimeError('Could not select the saved AUTO VIN template.')


def download_auto_vin(page):
    page.goto(REPORT_URL, wait_until='domcontentloaded', timeout=120000)
    wait_for_dealer_reporting(page)
    set_widest_date_range(page)

    if not click_export_to_excel(page):
        raise RuntimeError('Could not find Export to Excel in Dealer Reporting.')

    choose_auto_vin(page)

    with page.expect_download(timeout=120000) as info:
        final = page.get_by_role('button', name=re.compile(r'^Export$|^Download$', re.I))
        if not dom_click(final):
            raise RuntimeError('Could not click the final Export button.')
    dl = info.value
    suffix = Path(dl.suggested_filename).suffix or '.xlsx'
    dest = REPORT_DIR / f'AUTO_VIN_{datetime.now():%Y%m%d_%H%M%S}{suffix}'
    dl.save_as(str(dest))
    return dest


def read_report(path):
    return pd.read_csv(path, dtype=str).fillna('') if path.suffix.lower() == '.csv' else pd.read_excel(path, dtype=str).fillna('')


def find_col(df, names):
    n = {norm_header(c): c for c in df.columns}
    for x in names:
        if norm_header(x) in n:
            return n[norm_header(x)]
    for k, v in n.items():
        if any(norm_header(x) in k for x in names):
            return v
    return None


def report_map(path):
    df = read_report(path)
    s = find_col(df, ['Serial Number', 'Vehicle Serial Number', 'Serial No'])
    d = find_col(df, ['In-Service Date', 'In Service Date'])
    v = find_col(df, ['VIN', 'Vehicle Identification Number', 'Full VIN'])
    if not s or not d or not v:
        raise RuntimeError(f'AUTO VIN is missing required columns. Found: {list(df.columns)}')
    out = {}
    for _, row in df.iterrows():
        serial = norm_serial(row.get(s, ''))
        vin = norm_vin(row.get(v, ''))
        date = norm_date(row.get(d, ''))
        keys = set()
        if serial:
            keys.update([serial, serial[-8:], serial[-7:]])
        if vin:
            keys.update([vin[-8:], vin[-7:]])
        for k in keys:
            out[k] = {'VIN': vin, 'inServiceDate': date}
    return out


def enrich(rows, mapping):
    for row in rows:
        vals = []
        for x in (norm_serial(row.get('serialNo')), norm_serial(row.get('leadSerialNo'))):
            if x:
                vals.extend([x, x[-8:], x[-7:]])
        m = next((mapping[k] for k in vals if k in mapping), None)
        row['VIN'] = m.get('VIN', '') if m else ''
        row['inServiceDate'] = m.get('inServiceDate', '') if m else ''
        row['vinSource'] = 'Dealer Reporting' if m else ''


def row_key(r):
    return '|'.join(clean(r.get(k)) for k in ('serialNo', 'leadSerialNo', 'soCode', 'baseMdl', 'customer'))


def old_snapshot():
    p = HISTORY_DIR / 'latest_snapshot.json'
    return normalize_response(json.loads(p.read_text(encoding='utf-8'))) if p.exists() else []


def compare(old, new):
    a = {row_key(r): r for r in old}
    b = {row_key(r): r for r in new}
    when = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    changes = []
    for k, r in b.items():
        if k not in a:
            if a:
                changes.append({'changeTime': when, 'changeType': 'NEW ORDER', 'serialNo': clean(r.get('serialNo')), 'VIN': clean(r.get('VIN')), 'field': '', 'oldValue': '', 'newValue': 'Order added'})
            continue
        for f in TRACK_FIELDS:
            x, y = clean(a[k].get(f)), clean(r.get(f))
            if x != y:
                changes.append({'changeTime': when, 'changeType': 'FIELD CHANGED', 'serialNo': clean(r.get('serialNo')), 'VIN': clean(r.get('VIN')), 'field': f, 'oldValue': x, 'newValue': y})
    return changes


def save(rows, changes):
    ensure_dirs()
    df = pd.json_normalize(rows)
    tmp = OUTPUT_DIR / 'dtna_sales_orders.new.xlsx'
    df.to_excel(tmp, index=False, sheet_name='DTNA_Orders')
    os.replace(tmp, WORKING_EXCEL)
    df.to_csv(OUTPUT_DIR / 'dtna_sales_orders.csv', index=False, encoding='utf-8-sig')
    (OUTPUT_DIR / 'dtna_sales_orders_raw.json').write_text(json.dumps(rows, indent=2, default=str), encoding='utf-8')
    c = pd.DataFrame(changes)
    c.to_excel(CHANGES_DIR / 'latest_changes.xlsx', index=False, sheet_name='Latest_Changes')
    c.to_csv(CHANGES_DIR / 'latest_changes.csv', index=False, encoding='utf-8-sig')
    snap = json.dumps(rows, indent=2, default=str)
    (HISTORY_DIR / 'latest_snapshot.json').write_text(snap, encoding='utf-8')
    (HISTORY_DIR / f'snapshot_{datetime.now():%Y%m%d_%H%M%S}.json').write_text(snap, encoding='utf-8')
    status(
        status='SUCCESS',
        lastRun=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        orderCount=len(rows),
        vinCount=sum(bool(clean(r.get('VIN'))) for r in rows),
        inServiceDateCount=sum(bool(clean(r.get('inServiceDate'))) for r in rows),
        changeCount=len(changes),
        loginProfile=PROFILE_DIR,
    )


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--login-only', action='store_true')
    args, _ = parser.parse_known_args()

    ensure_dirs()
    status(status='RUNNING', lastRun=datetime.now().strftime('%Y-%m-%d %H:%M:%S'), message='DTNA browser starting', loginProfile=PROFILE_DIR)

    with sync_playwright() as p:
        ctx = launch_context(p)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(SALES_URL, wait_until='domcontentloaded', timeout=120000)
            wait_for_sales_page(page)

            if args.login_only:
                print('DTNA login is ready. You can close this window when finished.')
                input('Press ENTER to close DTNA login... ')
                return

            rows = fetch_all_sales(page)
            log(f'Downloaded {len(rows):,} Sales Order rows with Orders To Be Reviewed OFF')
            report = download_auto_vin(page)
            enrich(rows, report_map(report))
        finally:
            ctx.close()

    old = old_snapshot()
    changes = compare(old, rows)
    save(rows, changes)
    print(f'SUCCESS: {len(rows):,} orders, {len(changes):,} changes')
    print('Excel:', WORKING_EXCEL)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        log(f'ERROR: {exc}')
        status(status='FAILED', lastRun=datetime.now().strftime('%Y-%m-%d %H:%M:%S'), message=exc, loginProfile=PROFILE_DIR)
        print('ERROR:', exc)
        input('Press ENTER to close... ')
        raise
