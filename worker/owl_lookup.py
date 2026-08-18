from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
LOCAL_APPDATA = Path(os.environ.get('LOCALAPPDATA', str(ROOT)))
PROFILE_DIR = LOCAL_APPDATA / 'DiehlDTNAManual' / 'browser_profile'
OWL_STATE_DIR = LOCAL_APPDATA / 'DiehlVINWorker' / 'owl'
OWL_URL_FILE = OWL_STATE_DIR / 'owl_url.txt'
LOG_FILE = OWL_STATE_DIR / 'owl_lookup.log'
RESULT = Path(os.environ.get('DIEHL_RESULT_FILE', str(ROOT / 'vin-results.json')))
VINS = [x.strip().upper() for x in os.environ.get('DIEHL_VINS', '').splitlines() if x.strip()]

# Public DTNA portal is intentionally used as the discovery entry point. OWL itself
# is authenticated and its application URL can change. Once OWL is reached, the
# final authenticated URL is saved locally for this Windows user and reused.
PORTAL_URL = 'https://dtnacontent-dtna.prd.freightliner.com/content/public/dtnaportalpublic.html'


def log(message: str) -> None:
    OWL_STATE_DIR.mkdir(parents=True, exist_ok=True)
    line = f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] {message}'
    print(line, flush=True)
    with LOG_FILE.open('a', encoding='utf-8') as f:
        f.write(line + '\n')


def launch_context(playwright):
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    args = dict(
        user_data_dir=str(PROFILE_DIR),
        headless=False,
        viewport={'width': 1500, 'height': 900},
        accept_downloads=True,
    )
    try:
        return playwright.chromium.launch_persistent_context(channel='msedge', **args)
    except PlaywrightError:
        return playwright.chromium.launch_persistent_context(**args)


def all_pages(context):
    pages = list(context.pages)
    for page in pages:
        try:
            for frame in page.frames:
                yield page, frame
        except Exception:
            yield page, page


def visible_text(frame) -> str:
    try:
        return frame.locator('body').inner_text(timeout=3000)
    except Exception:
        return ''


def looks_like_owl(frame) -> bool:
    text = visible_text(frame).lower()
    url = (getattr(frame, 'url', '') or '').lower()
    return 'online warranty link' in text or re.search(r'\bowl\b', text) is not None or 'owl' in url


def find_vin_input(frame):
    selectors = [
        'input[placeholder*="VIN" i]',
        'input[aria-label*="VIN" i]',
        'input[name*="vin" i]',
        'input[id*="vin" i]',
        'input[placeholder*="serial" i]',
        'input[aria-label*="serial" i]',
    ]
    for selector in selectors:
        try:
            loc = frame.locator(selector)
            for i in range(loc.count()):
                item = loc.nth(i)
                if item.is_visible() and item.is_enabled():
                    return item
        except Exception:
            continue

    # Label-associated input fallback.
    try:
        labels = frame.get_by_text(re.compile(r'VIN|Vehicle\s+Identification|Serial\s+Number', re.I), exact=False)
        for i in range(labels.count()):
            label = labels.nth(i)
            if not label.is_visible():
                continue
            handle = label.element_handle()
            if not handle:
                continue
            selector = frame.evaluate("""el => {
                const forId = el.getAttribute && el.getAttribute('for');
                if (forId) return '#' + CSS.escape(forId);
                const box = el.closest('div,td,th,fieldset,form') || el.parentElement;
                const input = box && box.querySelector('input');
                if (!input) return '';
                if (!input.id) input.id = 'diehl-owl-vin-' + Math.random().toString(36).slice(2);
                return '#' + CSS.escape(input.id);
            }""", handle)
            if selector:
                loc = frame.locator(selector)
                if loc.count() and loc.first.is_visible():
                    return loc.first
    except Exception:
        pass
    return None


def find_search_button(frame):
    patterns = [r'^Search$', r'^Lookup$', r'^Find$', r'^Go$', r'Search\s+Vehicle', r'VIN\s+Search']
    for pattern in patterns:
        for role in ('button', 'link'):
            try:
                loc = frame.get_by_role(role, name=re.compile(pattern, re.I))
                for i in range(loc.count()):
                    item = loc.nth(i)
                    if item.is_visible() and item.is_enabled():
                        return item
            except Exception:
                pass
    try:
        loc = frame.locator('input[type="submit"],button[type="submit"]')
        for i in range(loc.count()):
            item = loc.nth(i)
            if item.is_visible() and item.is_enabled():
                return item
    except Exception:
        pass
    return None


def save_owl_url(page) -> None:
    try:
        url = page.url
        if url and url.startswith('http') and 'dtnacontent-' not in url:
            OWL_STATE_DIR.mkdir(parents=True, exist_ok=True)
            OWL_URL_FILE.write_text(url, encoding='utf-8')
            log(f'Saved OWL application URL for this Windows user: {url}')
    except Exception:
        pass


def try_open_saved_owl(page) -> bool:
    if not OWL_URL_FILE.exists():
        return False
    try:
        url = OWL_URL_FILE.read_text(encoding='utf-8').strip()
        if not url.startswith('http'):
            return False
        page.goto(url, wait_until='domcontentloaded', timeout=120_000)
        page.wait_for_timeout(1500)
        return True
    except Exception as exc:
        log(f'Saved OWL URL did not open cleanly: {exc}')
        return False


def click_owl_link(context) -> bool:
    for page, frame in all_pages(context):
        for pattern in (r'^OWL$', r'Online\s+Warranty\s+Link', r'Warranty\s+Link'):
            for role in ('link', 'button'):
                try:
                    loc = frame.get_by_role(role, name=re.compile(pattern, re.I))
                    for i in range(loc.count()):
                        item = loc.nth(i)
                        if not item.is_visible():
                            continue
                        before = len(context.pages)
                        item.click()
                        page.wait_for_timeout(1500)
                        if len(context.pages) > before:
                            context.pages[-1].bring_to_front()
                        return True
                except Exception:
                    continue
    return False


def inject_hint(page, message: str) -> None:
    try:
        page.evaluate("""msg => {
            let el=document.getElementById('diehl-owl-hint');
            if(!el){
              el=document.createElement('div'); el.id='diehl-owl-hint';
              Object.assign(el.style,{position:'fixed',top:'12px',left:'50%',transform:'translateX(-50%)',zIndex:'2147483647',background:'#102a43',color:'white',padding:'12px 18px',borderRadius:'8px',fontFamily:'Arial',fontSize:'14px',boxShadow:'0 2px 10px rgba(0,0,0,.3)'});
              document.body.appendChild(el);
            }
            el.textContent=msg;
        }""", message)
    except Exception:
        pass


def wait_for_owl_ready(context, timeout_seconds: int = 240):
    deadline = time.time() + timeout_seconds
    last_discovery = 0.0
    while time.time() < deadline:
        for page, frame in all_pages(context):
            vin_input = find_vin_input(frame)
            if vin_input is not None and (looks_like_owl(frame) or 'warranty' in visible_text(frame).lower()):
                save_owl_url(page)
                return page, frame, vin_input

        # During login/MFA, periodically try to find and click OWL from the authenticated portal.
        if time.time() - last_discovery > 4:
            last_discovery = time.time()
            click_owl_link(context)
            for page in context.pages:
                inject_hint(page, 'Diehl VIN: complete DTNA login/MFA if prompted. The worker is waiting for OWL Vehicle/VIN Search.')
        time.sleep(1)
    raise RuntimeError('OWL VIN search did not become ready. Open OWL/Vehicle Search in the DTNA browser and try the VIN batch again.')


def norm_space(value: str) -> str:
    return re.sub(r'\s+', ' ', value or '').strip()


def value_after_label(text: str, labels: list[str]) -> str:
    for label in labels:
        # same-line or nearby label/value text
        patterns = [
            rf'{label}\s*[:\-]?\s*([^\n\r|]{{1,120}})',
            rf'{label}\s*[\n\r]+\s*([^\n\r]{{1,120}})',
        ]
        for p in patterns:
            m = re.search(p, text, re.I)
            if m:
                value = norm_space(m.group(1))
                if value and not re.fullmatch(label, value, re.I):
                    return value
    return ''


def extract_result(frame, vin: str) -> dict[str, Any]:
    text = visible_text(frame)
    compact = norm_space(text)

    in_service = value_after_label(text, [
        r'In[- ]?Service\s+Date',
        r'Warranty\s+Start\s+Date',
        r'Inservice\s+Date',
    ])
    mileage = value_after_label(text, [r'Mileage', r'Odometer'])
    registered_name = value_after_label(text, [r'Registered\s+Customer\s+Name', r'Registered\s+Owner', r'Owner\s+Name'])
    registered_account = value_after_label(text, [r'Registered\s+Customer\s+Account', r'Customer\s+Account'])
    customer = registered_name or value_after_label(text, [r'Customer\s+Name', r'Customer'])
    status = value_after_label(text, [r'In[- ]?Service\s+Status', r'Warranty\s+Status'])

    not_found = bool(re.search(r'no\s+(vehicle|record|results?).{0,30}(found|match)|vin.{0,30}not\s+found|invalid\s+vin', compact, re.I))
    vin_visible = vin in re.sub(r'[^A-Z0-9]', '', text.upper())

    if not_found:
        return {
            'vin': vin,
            'verificationStatus': 'Not Found',
            'inServiceStatus': '',
            'inServiceDate': '',
            'mileage': '',
            'customerResult': 'VIN not found in OWL',
            'customerName': '',
            'registeredCustomerName': '',
            'registeredCustomerAccount': '',
            'orderedCustomerName': '',
            'source': 'OWL',
        }

    return {
        'vin': vin,
        'verificationStatus': 'Verified' if (vin_visible or in_service or customer or status) else 'Review',
        'inServiceStatus': status or ('In Service' if in_service else ''),
        'inServiceDate': in_service,
        'mileage': mileage,
        'customerResult': customer,
        'customerName': customer,
        'registeredCustomerName': registered_name,
        'registeredCustomerAccount': registered_account,
        'orderedCustomerName': '',
        'source': 'OWL',
        'rawText': text[:12000],
    }


def lookup_one(context, vin: str) -> dict[str, Any]:
    page, frame, vin_input = wait_for_owl_ready(context)
    inject_hint(page, f'Diehl VIN: looking up {vin} in OWL…')

    try:
        vin_input.click()
        vin_input.fill(vin)
    except Exception:
        # DOM can rerender after the first discovery; reacquire once.
        page, frame, vin_input = wait_for_owl_ready(context, 30)
        vin_input.fill(vin)

    button = find_search_button(frame)
    if button is not None:
        button.click()
    else:
        vin_input.press('Enter')

    # Wait until search settles. Prefer a visible VIN/result marker, but allow legacy OWL pages.
    start = time.time()
    previous = ''
    stable = 0
    while time.time() - start < 45:
        page.wait_for_timeout(750)
        current = visible_text(frame)
        if current == previous and len(current) > 50:
            stable += 1
        else:
            stable = 0
        previous = current
        normalized = re.sub(r'[^A-Z0-9]', '', current.upper())
        if vin in normalized or re.search(r'not\s+found|no\s+results?|invalid\s+vin', current, re.I):
            if stable >= 1:
                break
        elif stable >= 3:
            break

    result = extract_result(frame, vin)
    log(f'OWL result {vin}: {result.get("verificationStatus")} / in-service={result.get("inServiceDate") or "blank"} / customer={result.get("customerName") or "blank"}')
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
            opened = try_open_saved_owl(page)
            if not opened:
                page.goto(PORTAL_URL, wait_until='domcontentloaded', timeout=120_000)
            inject_hint(page, 'Diehl VIN: opening OWL. Complete DTNA login/MFA if requested.')

            # Do not fail the whole batch because one VIN has a page-specific problem.
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
