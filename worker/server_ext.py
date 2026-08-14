import os
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


def launch_dtna():
    if not DTNA_SCRIPT.exists():
        raise HTTPException(500, 'DTNA automation script is not installed. Re-run the Initializer.')
    creationflags = getattr(subprocess, 'CREATE_NEW_CONSOLE', 0)
    return subprocess.Popen([sys.executable, str(DTNA_SCRIPT)], cwd=str(ROOT), creationflags=creationflags)


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
