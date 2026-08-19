from __future__ import annotations

import csv
import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
LOCAL_APPDATA = Path(os.environ.get('LOCALAPPDATA', str(ROOT)))
CACHE_DIR = LOCAL_APPDATA / 'DiehlVINWorker' / 'database_cache'
DTNA_OUTPUT = LOCAL_APPDATA / 'DiehlDTNAManual' / 'data' / 'output' / 'dtna_sales_orders.csv'
STATE_DB = ROOT / 'worker_state.db'
LOCK = threading.RLock()
ALLOWED = ('DTNA', 'VIN In-Service')


def _cache_path(sheet: str) -> Path:
    return CACHE_DIR / ('dtna.json' if sheet == 'DTNA' else 'vin-in-service.json')


def _clean(value: Any) -> Any:
    if value is None:
        return ''
    if isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, 'isoformat'):
        try:
            return value.isoformat()
        except Exception:
            pass
    return str(value)


def write_table(sheet: str, headers: list[str], rows: list[dict[str, Any]], workbook: str, source: str) -> None:
    if sheet not in ALLOWED:
        raise ValueError(f'Unsupported database sheet: {sheet}')
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        'sheet': sheet,
        'workbook': workbook,
        'headers': [str(x) for x in headers],
        'rows': [{str(k): _clean(v) for k, v in row.items()} for row in rows],
        'rowCount': len(rows),
        'returned': len(rows),
        'exists': True,
        'modified': time.time(),
        'readMode': 'Verified Excel mirror',
        'source': source,
    }
    target = _cache_path(sheet)
    temp = target.with_suffix('.tmp')
    with LOCK:
        temp.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        os.replace(temp, target)


def vin_mapping() -> dict[str, str]:
    return {
        'vin': 'VIN',
        'verificationStatus': 'Verification Status',
        'productSerialNumber': 'Product Serial Number',
        'vehicleModel': 'Vehicle Model',
        'buildDate': 'Build Date',
        'inServiceStatus': 'In-Service Status',
        'inServiceDate': 'In-Service Date',
        'mileage': 'Mileage',
        'customerResult': 'Customer Result',
        'customerName': 'Customer Name',
        'registeredCustomerName': 'Registered Customer Name',
        'registeredCustomerAccount': 'Registered Customer Account',
        'orderedCustomerName': 'Ordered Customer Name',
        'warrantyStatus': 'Warranty Status',
        'warrantyCoverage': 'Warranty / Coverage Details',
        'coverageRecordsJson': 'Coverage Records JSON',
        'coverageFieldsJson': 'Coverage Fields JSON',
        'engineSerialNumber': 'Engine Serial Number',
        'engineModel': 'Engine Model',
        'allisonTransmissionSerialNumber': 'Allison Transmission Serial Number',
        'transmissionModel': 'Transmission Model',
        'majorComponentsText': 'Major Components Details',
        'majorComponentsJson': 'Major Components JSON',
        'majorComponentFieldsJson': 'Major Component Fields JSON',
        'source': 'Source',
    }


def update_vin(vin: str, result: dict[str, Any], workbook: str) -> None:
    sheet = 'VIN In-Service'
    with LOCK:
        current = read_table(sheet, limit=100000, seed=False)
        rows = list(current.get('rows') or []) if current else []
        headers = list(current.get('headers') or []) if current else []
        mapping = vin_mapping()
        for header in [*mapping.values(), 'Last Updated']:
            if header not in headers:
                headers.append(header)
        target = None
        for row in rows:
            if str(row.get('VIN') or '').strip().upper() == vin.upper():
                target = row
                break
        if target is None:
            target = {'VIN': vin.upper()}
            rows.append(target)
        for key, header in mapping.items():
            value = result.get(key)
            if value not in (None, ''):
                target[header] = _clean(value)
        target['VIN'] = vin.upper()
        target['Last Updated'] = time.strftime('%Y-%m-%d %H:%M:%S')
        write_table(sheet, headers, rows, workbook, 'OWL -> verified Excel save')


def _seed_dtna() -> bool:
    if not DTNA_OUTPUT.exists():
        return False
    try:
        with DTNA_OUTPUT.open('r', encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            headers = list(reader.fieldnames or [])
            rows = [dict(row) for row in reader]
        if not headers:
            return False
        write_table('DTNA', headers, rows, '', 'DTNA local output from last successful sync')
        return True
    except Exception:
        return False


def _seed_vin() -> bool:
    if not STATE_DB.exists():
        return False
    try:
        c = sqlite3.connect(STATE_DB, timeout=2)
        c.row_factory = sqlite3.Row
        items = c.execute("select vin,result,completed_at from items where status='complete' and result is not null order by completed_at").fetchall()
        c.close()
    except Exception:
        return False
    if not items:
        return False
    rows_by_vin: dict[str, dict[str, Any]] = {}
    mapping = vin_mapping()
    for item in items:
        try:
            result = json.loads(item['result'])
        except Exception:
            continue
        vin = str(item['vin'] or '').upper()
        row = {'VIN': vin, 'Last Updated': str(item['completed_at'] or '')}
        for key, header in mapping.items():
            value = result.get(key)
            if value not in (None, ''):
                row[header] = _clean(value)
        rows_by_vin[vin] = row
    if not rows_by_vin:
        return False
    headers = list(dict.fromkeys(['VIN', *mapping.values(), 'Last Updated']))
    write_table('VIN In-Service', headers, list(rows_by_vin.values()), '', 'Completed OWL results mirror')
    return True


def _dtna_mirror_is_stale(target: Path) -> bool:
    if not DTNA_OUTPUT.exists():
        return False
    if not target.exists():
        return True
    try:
        return DTNA_OUTPUT.stat().st_mtime > target.stat().st_mtime + 0.1
    except Exception:
        return True


def read_table(sheet: str, limit: int = 10000, seed: bool = True) -> dict[str, Any]:
    if sheet not in ALLOWED:
        raise ValueError(f'Unsupported database sheet: {sheet}')
    target = _cache_path(sheet)
    if seed and sheet == 'DTNA' and _dtna_mirror_is_stale(target):
        _seed_dtna()
    elif not target.exists() and seed and sheet == 'VIN In-Service':
        _seed_vin()
    if not target.exists():
        return {
            'sheet': sheet,
            'workbook': '',
            'headers': [],
            'rows': [],
            'rowCount': 0,
            'returned': 0,
            'exists': False,
            'modified': 0,
            'readMode': 'Verified Excel mirror',
            'source': 'No successful write mirrored yet',
        }
    with LOCK:
        data = json.loads(target.read_text(encoding='utf-8'))
    if data.get('sheet') != sheet:
        raise RuntimeError(f'Cache isolation failure: requested {sheet}, cache contains {data.get("sheet")}.')
    rows = list(data.get('rows') or [])
    data['rowCount'] = len(rows)
    data['rows'] = rows[:limit]
    data['returned'] = len(data['rows'])
    return data
