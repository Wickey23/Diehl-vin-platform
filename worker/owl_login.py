from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
LOCAL_APPDATA = Path(os.environ.get('LOCALAPPDATA', str(ROOT)))
PROFILE_DIR = LOCAL_APPDATA / 'DiehlDTNAManual' / 'browser_profile'
OWL_URL = 'https://secure.freightliner.com/iwarranty/signOn'


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
            page.goto(OWL_URL, wait_until='domcontentloaded', timeout=120_000)
            print()
            print('OWL login/browser opened for this Windows user.')
            print('Complete your own Freightliner login/MFA if prompted.')
            print('VIN In-Service will use Coverage Info / Check Coverage and Major Components automatically.')
            print()
            input('Press ENTER here when the OWL Home page is visible... ')
        finally:
            try:
                context.close()
            except Exception:
                pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
