from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / 'config.json'
PORT = 8766
ALLOWED_SHEETS = ('DTNA', 'VIN In-Service')

app = FastAPI(title='Diehl VIN Database Viewer', version='1.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        'https://diehl-vin-platform.vercel.app',
        'http://localhost:3000',
        'http://127.0.0.1:3000',
    ],
    allow_credentials=False,
    allow_methods=['GET', 'OPTIONS'],
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


def read_sheet(sheet_name: str, limit: int) -> dict[str, Any]:
    path = workbook_path()
    if not str(path) or not path.exists():
        raise RuntimeError('Shared Excel database was not found on this computer.')

    last_error: Exception | None = None
    for attempt in range(4):
        wb = None
        try:
            wb = load_workbook(path, read_only=True, data_only=True, keep_vba=path.suffix.lower() == '.xlsm')
            if sheet_name not in wb.sheetnames:
                return {
                    'sheet': sheet_name,
                    'workbook': str(path),
                    'headers': [],
                    'rows': [],
                    'rowCount': 0,
                    'exists': False,
                }
            ws = wb[sheet_name]
            rows = ws.iter_rows(values_only=True)
            try:
                raw_headers = next(rows)
            except StopIteration:
                raw_headers = []
            headers = [str(x or '').strip() for x in raw_headers]
            while headers and not headers[-1]:
                headers.pop()

            data = []
            total = 0
            for raw in rows:
                if not any(v not in (None, '') for v in raw):
                    continue
                total += 1
                if len(data) < limit:
                    item = {}
                    for i, header in enumerate(headers):
                        if not header:
                            continue
                        value = raw[i] if i < len(raw) else None
                        item[header] = serialize(value)
                    data.append(item)

            return {
                'sheet': sheet_name,
                'workbook': str(path),
                'headers': headers,
                'rows': data,
                'rowCount': total,
                'returned': len(data),
                'exists': True,
                'modified': path.stat().st_mtime,
            }
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(.5)
        finally:
            try:
                if wb is not None:
                    wb.close()
            except Exception:
                pass
    raise RuntimeError(f'Could not read the shared Excel database: {last_error}')


@app.get('/ping')
def ping():
    return {'ok': True, 'product': 'DiehlVINDatabase', 'version': '1.0', 'hostname': socket.gethostname()}


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


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=PORT, log_level='warning')
