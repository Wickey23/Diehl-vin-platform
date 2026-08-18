from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

import psutil
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / 'config.json'
PORT = 8766
ALLOWED_SHEETS = ('DTNA', 'VIN In-Service')
DIEHL_PRODUCTS = {'DiehlVINWorker', 'DiehlVINDatabase'}
DTNA_RUNTIME = ROOT / 'dtna_runtime.py'
PROFILE = Path(os.environ.get('LOCALAPPDATA', str(ROOT))) / 'DiehlDTNAManual' / 'browser_profile'

app = FastAPI(title='Diehl VIN Database Viewer', version='1.3')
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


def config() -> dict[str, Any]:
    try:
        return json.loads(CONFIG.read_text(encoding='utf-8')) if CONFIG.exists() else {}
    except Exception:
        return {}


def workbook_path() -> Path:
    value = str(config().get('masterWorkbook') or '').strip()
    return Path(os.path.expandvars(value)).expanduser()


def serialize(value: Any) -> Any:
    if value is None:
        return ''
    if hasattr(value, 'isoformat'):
        try:
            return value.isoformat()
        except Exception:
            pass
    return value if isinstance(value, (str, int, float, bool)) else str(value)


def _norm_path(value: str | Path) -> str:
    try:
        return os.path.normcase(os.path.abspath(str(value))).rstrip('\\/')
    except Exception:
        return str(value).lower().rstrip('\\/')


def _find_open_workbook(pythoncom, win32com, destination: Path):
    exact = []
    same_name = []
    seen = set()

    def inspect_app(app):
        try:
            count = int(app.Workbooks.Count)
        except Exception:
            return
        for i in range(1, count + 1):
            try:
                wb = app.Workbooks.Item(i)
                name = str(wb.Name or '')
                full = str(wb.FullName or '')
                key = (name, full)
                if key in seen:
                    continue
                seen.add(key)
                if full and _norm_path(full) == _norm_path(destination):
                    exact.append(wb)
                elif name.lower() == destination.name.lower():
                    same_name.append(wb)
            except Exception:
                continue

    try:
        inspect_app(win32com.client.GetActiveObject('Excel.Application'))
    except Exception:
        pass

    try:
        rot = pythoncom.GetRunningObjectTable()
        enum = rot.EnumRunning()
        bind = pythoncom.CreateBindCtx(0)
        while True:
            monikers = enum.Next(1)
            if not monikers:
                break
            moniker = monikers[0]
            try:
                display = moniker.GetDisplayName(bind, None)
            except Exception:
                display = ''
            if 'excel' not in display.lower() and destination.name.lower() not in display.lower():
                continue
            try:
                obj = win32com.client.Dispatch(rot.GetObject(moniker))
            except Exception:
                continue
            try:
                if hasattr(obj, 'Workbooks'):
                    inspect_app(obj)
                elif hasattr(obj, 'Application') and hasattr(obj, 'FullName'):
                    wb = obj
                    name = str(wb.Name or '')
                    full = str(wb.FullName or '')
                    key = (name, full)
                    if key not in seen:
                        seen.add(key)
                        if full and _norm_path(full) == _norm_path(destination):
                            exact.append(wb)
                        elif name.lower() == destination.name.lower():
                            same_name.append(wb)
            except Exception:
                continue
    except Exception:
        pass

    if exact:
        return exact[0]

    unique = []
    keys = set()
    for wb in same_name:
        try:
            key = (str(wb.Name), str(wb.FullName))
        except Exception:
            continue
        if key not in keys:
            keys.add(key)
            unique.append(wb)
    return unique[0] if len(unique) == 1 else None


def _payload_from_com(sheet_name: str, path: Path, ws, limit: int) -> dict[str, Any]:
    used = ws.UsedRange
    row_count = max(1, int(used.Rows.Count))
    col_count = max(1, int(used.Columns.Count))
    headers = [str(ws.Cells(1, c).Value or '').strip() for c in range(1, col_count + 1)]
    while headers and not headers[-1]:
        headers.pop()

    data: list[dict[str, Any]] = []
    total = 0
    for r in range(2, row_count + 1):
        values = [ws.Cells(r, c).Value for c in range(1, len(headers) + 1)]
        if not any(v not in (None, '') for v in values):
            continue
        total += 1
        if len(data) < limit:
            item: dict[str, Any] = {}
            for i, header in enumerate(headers):
                if header:
                    item[header] = serialize(values[i] if i < len(values) else None)
            data.append(item)

    try:
        modified = path.stat().st_mtime
    except Exception:
        modified = 0

    return {
        'sheet': sheet_name,
        'workbook': str(path),
        'headers': headers,
        'rows': data,
        'rowCount': total,
        'returned': len(data),
        'exists': True,
        'modified': modified,
        'readMode': 'Excel COM',
    }


def read_sheet_com(path: Path, sheet_name: str, limit: int) -> dict[str, Any]:
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    excel = wb = None
    opened_here = created_excel = False
    try:
        wb = _find_open_workbook(pythoncom, win32com, path)
        if wb is not None:
            excel = wb.Application
        else:
            try:
                excel = win32com.client.GetActiveObject('Excel.Application')
            except Exception:
                excel = win32com.client.DispatchEx('Excel.Application')
                excel.Visible = False
                excel.DisplayAlerts = False
                created_excel = True

            wb = excel.Workbooks.Open(
                str(path),
                UpdateLinks=0,
                ReadOnly=True,
                IgnoreReadOnlyRecommended=True,
                AddToMru=False,
            )
            opened_here = True

        try:
            ws = wb.Worksheets(sheet_name)
        except Exception:
            return {
                'sheet': sheet_name,
                'workbook': str(path),
                'headers': [],
                'rows': [],
                'rowCount': 0,
                'exists': False,
                'readMode': 'Excel COM',
            }

        return _payload_from_com(sheet_name, path, ws, limit)
    finally:
        try:
            if wb is not None and opened_here:
                wb.Close(SaveChanges=False)
        except Exception:
            pass
        try:
            if excel is not None and created_excel:
                excel.Quit()
        except Exception:
            pass
        pythoncom.CoUninitialize()


def read_sheet(sheet_name: str, limit: int) -> dict[str, Any]:
    path = workbook_path()
    if not str(path) or not path.exists():
        raise RuntimeError('Shared Excel database was not found on this computer.')

    errors: list[str] = []
    for attempt in range(1, 7):
        try:
            return read_sheet_com(path, sheet_name, limit)
        except Exception as exc:
            errors.append(str(exc))
            if attempt < 6:
                time.sleep(.5)
    raise RuntimeError('Could not read the shared Excel database through Excel after 6 attempts: ' + ' | '.join(errors[-3:]))


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
        return 'service_v4.py' in text or 'diehlvinworker' in text
    if port == 8766:
        return 'database_service.py' in text or pid == os.getpid()
    return False


def _stop_main_worker() -> None:
    pid = listener_pid(8765)
    if pid and verified_diehl_process(8765, pid):
        try:
            psutil.Process(pid).terminate()
            try:
                psutil.Process(pid).wait(timeout=3)
            except Exception:
                if psutil.pid_exists(pid):
                    psutil.Process(pid).kill()
        except Exception:
            pass


def _exit_database_service() -> None:
    time.sleep(.8)
    os._exit(0)


@app.get('/ping')
def ping():
    return {'ok': True, 'product': 'DiehlVINDatabase', 'version': '1.3', 'hostname': socket.gethostname()}


@app.get('/database/sheets')
def sheets():
    path = workbook_path()
    return {'ok': True, 'workbook': str(path) if str(path) else '', 'sheets': list(ALLOWED_SHEETS)}


@app.get('/database/{sheet_name}')
def database_sheet(sheet_name: str, limit: int = Query(default=2000, ge=1, le=10000)):
    if sheet_name not in ALLOWED_SHEETS:
        raise HTTPException(404, 'Unknown database sheet.')
    try:
        return read_sheet(sheet_name, limit)
    except Exception as exc:
        raise HTTPException(503, str(exc)) from exc


@app.get('/dtna/status')
def dtna_status():
    return {'ready': DTNA_RUNTIME.exists(), 'profile': str(PROFILE), 'runtime': str(DTNA_RUNTIME)}


@app.post('/dtna/open')
def dtna_open():
    launch_dtna_runtime(['--login-only'])
    return {'ok': True, 'message': 'Fixed DTNA login runtime opened.'}


@app.post('/dtna/sync')
def dtna_sync():
    launch_dtna_runtime([])
    return {'ok': True, 'message': 'Fixed DTNA runtime started. Successful sync writes the DTNA sheet.'}


@app.post('/control/stop-all')
def stop_all():
    threading.Thread(target=_stop_main_worker, daemon=True).start()
    threading.Thread(target=_exit_database_service, daemon=True).start()
    return {'ok': True, 'message': 'Stopping Diehl worker services on ports 8765 and 8766.'}


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=PORT, log_level='warning')
