from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
LOCAL_APPDATA = Path(os.environ.get('LOCALAPPDATA', str(ROOT)))
PROFILE_DIR = LOCAL_APPDATA / 'DiehlDTNAManual' / 'browser_profile'
OWL_URL_FILE = LOCAL_APPDATA / 'DiehlVINWorker' / 'owl' / 'owl_url.txt'
PORTAL_URL = 'https://dtnacontent-dtna.prd.freightliner.com/content/public/dtnaportalpublic.html'


def launch_context(playwright):
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    args = dict(user_data_dir=str(PROFILE_DIR), headless=False, viewport={'width': 1500, 'height': 900})
    try:
        return playwright.chromium.launch_persistent_context(channel='msedge', **args)
    except PlaywrightError:
        return playwright.chromium.launch_persistent_context(**args)


def main() -> int:
    with sync_playwright() as p:
        context = launch_context(p)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            target = PORTAL_URL
            if OWL_URL_FILE.exists():
                saved = OWL_URL_FILE.read_text(encoding='utf-8').strip()
                if saved.startswith('http'):
                    target = saved
            page.goto(target, wait_until='domcontentloaded', timeout=120_000)
            print()
            print('OWL login/browser opened for this Windows user.')
            print('Complete your own DTNA login/MFA if prompted, then navigate to OWL Vehicle/VIN Search.')
            print('Leave OWL ready for VIN In-Service checks.')
            print()
            input('Press ENTER here when your OWL session is ready... ')
        finally:
            try:
                context.close()
            except Exception:
                pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
