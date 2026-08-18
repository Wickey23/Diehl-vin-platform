from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

import psutil
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from database_cache import read_table

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / 'config.json'
PORT = 8766
ALLOWED_SHEETS = ('DTNA', 'VIN In-Service')
DIEHL_PRODUCTS = {'DiehlVINWorker', 'DiehlVINDatabase'}
DTNA_RUNTIME = ROOT / 'dtna_runtime.py'
PROFILE = Path(os.environ.get('LOCALAPPDATA', str(ROOT))) / 'DiehlDTNAManual' / 'browser_profile'

app = FastAPI(title='Diehl VIN Database Viewer', version='2.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        'https://diehl-vin-platform.vercel.app',
        'http://localhost:3000',
        'http://127.0.0.1:3000',
    ],
    allow_credentials=False,
    allow_methods=['GET', 'POST', 'OPTIONS'],
    allow_headers=['*'],
)


@app.middleware('http')
async def private_network_access(request: Request, call_next):
    response = await call_next(request)
    if request.headers.get('access-control-request-private-network') == 'true':
        response.headers['Access-Control-Allow-Private-Network'] = 'true'
    response.headers['Cache-Control'] = 'no-store'
    return response


def workbook_path() -> Path:
    try:
        data = json.loads(CONFIG.read_text(encoding='utf-8')) if CONFIG.exists() else {}
    except Exception:
        data = {}
    value = str(data.get('masterWorkbook') or '').strip()
    return Path(os.path.expandvars(value)).expanduser()


def launch_dtna_runtime(args: list[str]) -> None:
    if not DTNA_RUNTIME.exists():
        raise HTTPException(500, 'Fixed DTNA runtime is not installed. Download the current worker package.')
    py = ROOT / '.venv' / 'Scripts' / 'python.exe'
    if not py.exists():
        raise HTTPException(500, 'Local Python environment is not ready.')
    flags = getattr(subprocess, 'CREATE_NEW_CONSOLE', 0)
    subprocess.Popen([str(py), str(DTNA_RUNTIME), *args], cwd=str(ROOT), creationflags=flags)


def ping_product(port: int) -> str:
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/ping', timeout=1) as response:
            data = json.loads(response.read().decode('utf-8', errors='replace'))
        return str(data.get('product') or '')
    except Exception:
        return ''


def listener_pid(port: int) -> int | None:
    try:
        for conn in psutil.net_connections(kind='tcp'):
            if conn.status == psutil.CONN_LISTEN and conn.laddr and conn.laddr.port == port and conn.pid:
                return int(conn.pid)
    except Exception:
        pass
    return None


def verified_diehl_process(port: int, pid: int) -> bool:
    product = ping_product(port)
    if product not in DIEHL_PRODUCTS:
        return False
    try:
        proc = psutil.Process(pid)
        text = ' '.join(proc.cmdline()).lower()
    except Exception:
        return False
    if port == 8765:
        return 'service_v5.py' in text or 'service_v4.py' in text or 'diehlvinworker' in text
    if port == 8766:
        return 'database_service.py' in text or pid == os.getpid()
    return False


def _stop_main_worker() -> None:
    pid = listener_pid(8765)
    if pid and verified_diehl_process(8765, pid):
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except Exception:
                if psutil.pid_exists(pid):
                    proc.kill()
        except Exception:
            pass


def _exit_database_service() -> None:
    time.sleep(.8)
    os._exit(0)


@app.get('/ping')
def ping():
    return {'ok': True, 'product': 'DiehlVINDatabase', 'version': '2.0', 'hostname': socket.gethostname()}


@app.get('/database/sheets')
def sheets():
    path = workbook_path()
    return {
        'ok': True,
        'workbook': str(path) if str(path) else '',
        'sheets': list(ALLOWED_SHEETS),
        'mode': 'Verified Excel mirror',
    }


@app.get('/database/{sheet_name}')
def database_sheet(sheet_name: str, limit: int = Query(default=2000, ge=1, le=10000)):
    if sheet_name not in ALLOWED_SHEETS:
        raise HTTPException(404, 'Unknown database sheet.')
    try:
        payload = read_table(sheet_name, limit)
        if not payload.get('workbook'):
            payload['workbook'] = str(workbook_path())
        return payload
    except Exception as exc:
        raise HTTPException(503, f'Could not read the local verified database mirror: {exc}') from exc


@app.get('/dtna/status')
def dtna_status():
    return {'ready': DTNA_RUNTIME.exists(), 'profile': str(PROFILE), 'runtime': str(DTNA_RUNTIME)}


@app.post('/dtna/open')
def dtna_open():
    launch_dtna_runtime(['--login-only'])
    return {'ok': True, 'message': 'DTNA login runtime opened.'}


@app.post('/dtna/sync')
def dtna_sync():
    launch_dtna_runtime([])
    return {'ok': True, 'message': 'DTNA runtime started. Successful sync writes Excel and refreshes the Database mirror.'}


@app.post('/control/stop-all')
def stop_all():
    threading.Thread(target=_stop_main_worker, daemon=True).start()
    threading.Thread(target=_exit_database_service, daemon=True).start()
    return {'ok': True, 'message': 'Stopping verified Diehl worker services on ports 8765 and 8766.'}


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=PORT, log_level='warning')
