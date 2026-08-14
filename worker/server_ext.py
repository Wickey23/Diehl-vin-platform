import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from fastapi import Header, HTTPException

import server

app = server.app
ROOT = Path(__file__).resolve().parent
LOCAL_APPDATA = Path(os.environ.get('LOCALAPPDATA', ROOT))
DTNA_ROOT = LOCAL_APPDATA / 'DiehlDTNAManual'
DTNA_STATUS = DTNA_ROOT / 'data' / 'SYNC_STATUS.txt'
DTNA_SCRIPT = ROOT / 'dtna_login_and_sync.py'


def auth(key: Optional[str]):
    server.auth(key)


def command_configured(name: str) -> bool:
    return bool(os.environ.get(name, '').strip())


def parse_status():
    result = {'running': server.proc_running('python.exe', 'python') and (DTNA_ROOT / 'browser_profile').exists()}
    if DTNA_STATUS.exists():
        for line in DTNA_STATUS.read_text(encoding='utf-8', errors='ignore').splitlines():
            if ':' in line:
                k, v = line.split(':', 1)
                key = {
                    'status': 'status',
                    'lastRun': 'lastRun',
                    'orderCount': 'orderCount',
                    'vinCount': 'vinCount',
                    'inServiceDateCount': 'inServiceDateCount',
                    'changeCount': 'changeCount',
                    'loginProfile': 'loginProfile',
                    'message': 'message',
                }.get(k.strip(), k.strip())
                result[key] = v.strip()
    result.setdefault('loginProfile', str(DTNA_ROOT / 'browser_profile'))
    result['scriptInstalled'] = DTNA_SCRIPT.exists()
    return result


def prerequisite_status():
    workbook = server.WORKBOOK
    venv_python = ROOT / '.venv' / 'Scripts' / 'python.exe'
    browser_profiles = ROOT / 'browser_profiles'
    checks = [
        {'id': 'worker', 'label': 'Diehl worker service', 'status': 'ok', 'detail': f'Running on port {server.PORT}'},
        {'id': 'python', 'label': 'Python virtual environment', 'status': 'ok' if venv_python.exists() else 'missing', 'detail': str(venv_python) if venv_python.exists() else 'Re-run the Windows Initializer'},
        {'id': 'excel', 'label': 'VIN_Master_Data.xlsx', 'status': 'ok' if workbook.exists() else 'missing', 'detail': str(workbook)},
        {'id': 'onedrive', 'label': 'OneDrive workbook access', 'status': 'ok' if workbook.exists() else 'missing', 'detail': 'Workbook is reachable' if workbook.exists() else 'Master workbook path is not reachable'},
        {'id': 'outlook', 'label': 'Microsoft Outlook', 'status': 'ok' if server.proc_running('outlook') else 'warning', 'detail': 'Outlook is open' if server.proc_running('outlook') else 'Outlook is not open; sync can still be configured separately'},
        {'id': 'edge', 'label': 'Edge / Chromium browser', 'status': 'ok' if (server.proc_running('msedge','chrome') or shutil.which('msedge') or shutil.which('chrome')) else 'warning', 'detail': 'Browser detected' if (server.proc_running('msedge','chrome') or shutil.which('msedge') or shutil.which('chrome')) else 'Playwright browser may be used instead'},
        {'id': 'playwright', 'label': 'Playwright DTNA automation', 'status': 'ok' if DTNA_SCRIPT.exists() else 'missing', 'detail': str(DTNA_SCRIPT)},
        {'id': 'dtna-sync', 'label': 'DTNA Sales Order + AUTO VIN command', 'status': 'ok' if (DTNA_SCRIPT.exists() or command_configured('DTNA_SYNC_COMMAND')) else 'missing', 'detail': os.environ.get('DTNA_SYNC_COMMAND', 'dtna_login_and_sync.py')},
        {'id': 'vin-lookup', 'label': 'VIN In-Service lookup engine', 'status': 'ok' if command_configured('VIN_LOOKUP_COMMAND') else 'warning', 'detail': os.environ.get('VIN_LOOKUP_COMMAND', 'Not configured yet') or 'Not configured yet'},
        {'id': 'cloudflared', 'label': 'Cloudflare secure tunnel', 'status': 'ok' if shutil.which('cloudflared') else 'missing', 'detail': shutil.which('cloudflared') or 'Re-run the Windows Initializer'},
        {'id': 'profiles', 'label': 'Isolated browser worker profiles', 'status': 'ok' if browser_profiles.exists() else 'warning', 'detail': str(browser_profiles)},
    ]
    blocking = [c for c in checks if c['status'] == 'missing']
    return {
        'ready': not blocking,
        'checks': checks,
        'summary': f"{len([c for c in checks if c['status']=='ok'])} ready · {len([c for c in checks if c['status']=='warning'])} warnings · {len(blocking)} missing",
        'installRoot': str(ROOT),
    }


def launch_dtna():
    if not DTNA_SCRIPT.exists():
        raise HTTPException(500, 'DTNA automation script is not installed. Re-run the Initializer.')
    creationflags = getattr(subprocess, 'CREATE_NEW_CONSOLE', 0)
    return subprocess.Popen([sys.executable, str(DTNA_SCRIPT)], cwd=str(ROOT), creationflags=creationflags)


@app.get('/initializer/status')
def initializer_status(x_worker_key: Optional[str] = Header(default=None)):
    auth(x_worker_key)
    return prerequisite_status()


@app.get('/dtna/status')
def dtna_status(x_worker_key: Optional[str] = Header(default=None)):
    auth(x_worker_key)
    return parse_status()


@app.post('/dtna/open')
def dtna_open(x_worker_key: Optional[str] = Header(default=None)):
    auth(x_worker_key)
    launch_dtna()
    return {'ok': True, 'message': 'DTNA window launched. Complete login/MFA in the local browser if requested.'}


@app.post('/dtna/sync')
def dtna_sync(x_worker_key: Optional[str] = Header(default=None)):
    auth(x_worker_key)
    launch_dtna()
    return {'ok': True, 'message': 'Sales Order + AUTO VIN sync launched on the Windows worker.'}


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=server.PORT)
