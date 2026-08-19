from __future__ import annotations

"""Diehl VIN worker v5 integration layer.

VIN In-Service always performs a live OWL lookup. A VIN is only marked complete
after OWL verifies that both Coverage Info and Major Components belong to the
submitted VIN, then the normalized result is written to and verified in the
shared Excel workbook. Raw structured OWL records are also retained for audit.
"""

import getpass
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import HTTPException

import service_v4 as base
from database_cache import update_vin
from excel_bridge import collect_open_workbook

base.VERSION = '5.12'
ROOT = Path(__file__).resolve().parent
OWL_LOGIN = ROOT / 'owl_login.py'
ORIGINAL_RUN_LOOKUP = base.run_lookup


def force_live_owl_lookup(_wanted: set[str]):
    return {}


def validated_owl_lookup(vins: list[str]) -> dict[str, Any]:
    data = ORIGINAL_RUN_LOOKUP(vins)
    if not isinstance(data, dict):
        return {'_error': 'OWL lookup did not return a valid result payload.'}
    global_error = str(data.get('_error') or '').strip()
    out: dict[str, Any] = {}
    errors: list[str] = []
    for vin in vins:
        result = data.get(vin)
        if isinstance(result, dict) and result.get('_error'):
            errors.append(f'{vin}: {result.get("_error")}')
            continue
        if isinstance(result, dict) and result:
            status = str(result.get('verificationStatus') or '').strip()
            if status not in {'Verified', 'Not Found'}:
                errors.append(f'{vin}: OWL did not return a trusted verification state.')
                continue
            result.setdefault('vin', vin)
            result.setdefault('source', 'OWL Coverage Info + Major Components')
            out[vin] = result
        else:
            errors.append(f'{vin}: OWL returned no result.')
    if global_error:
        errors.insert(0, global_error)
    if errors:
        out['_error'] = 'OWL lookup failed: ' + ' | '.join(errors)
    return out


def _write_vin_once(vin: str, result: dict[str, Any]) -> None:
    import pythoncom
    import win32com.client

    path = base.workbook_path()
    if not path.exists():
        raise RuntimeError('Shared Excel database cannot be found.')

    mapping = {
        'verificationStatus': 'Verification Status',
        'productSerialNumber': 'Product Serial Number',
        'chassisSerialNumber': 'Chassis Serial Number',
        'vehicleModel': 'Vehicle Model',
        'buildDate': 'Build Date',
        'unitNumber': 'Unit Number',
        'vocation': 'Vocation',
        'wheelbase': 'Wheelbase',
        'gvwr': 'GVW',
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
        'engineManufacturer': 'Engine Manufacturer',
        'allisonTransmissionSerialNumber': 'Allison Transmission Serial Number',
        'transmissionModel': 'Transmission Model',
        'transmissionManufacturer': 'Transmission Manufacturer',
        'majorComponentsText': 'Major Components Details',
        'majorComponentsJson': 'Major Components JSON',
        'majorComponentFieldsJson': 'Major Component Fields JSON',
        'source': 'Source',
    }

    pythoncom.CoInitialize()
    excel = workbook = None
    opened_here = created_excel = False
    try:
        workbook = collect_open_workbook(pythoncom, win32com, path)
        if workbook is not None:
            excel = workbook.Application
            print(f'VIN Excel: attached to already-open workbook: {workbook.FullName}', flush=True)
        else:
            excel = win32com.client.DispatchEx('Excel.Application')
            created_excel = True
            excel.Visible = False
            excel.DisplayAlerts = False
            workbook = excel.Workbooks.Open(str(path), UpdateLinks=0, ReadOnly=False, IgnoreReadOnlyRecommended=True, AddToMru=False)
            opened_here = True
            print(f'VIN Excel: opened shared workbook for write: {path}', flush=True)

        if workbook is None:
            raise RuntimeError('Excel did not return the shared workbook object.')
        if bool(getattr(workbook, 'ReadOnly', False)):
            raise RuntimeError('Shared workbook is temporarily read-only.')

        excel.DisplayAlerts = False
        excel.ScreenUpdating = False
        excel.EnableEvents = False

        try:
            ws = workbook.Worksheets(base.VIN_SHEET)
        except Exception:
            ws = workbook.Worksheets.Add(After=workbook.Worksheets(workbook.Worksheets.Count))
            ws.Name = base.VIN_SHEET

        cols = max(1, int(ws.UsedRange.Columns.Count))
        headers: dict[str, int] = {}
        for c in range(1, cols + 1):
            header = str(ws.Cells(1, c).Value or '').strip()
            if header:
                headers[header] = c

        required = ['VIN', *mapping.values(), 'Last Updated', 'Updated By']
        for header in required:
            if header not in headers:
                cols += 1
                ws.Cells(1, cols).Value = header
                headers[header] = cols

        vin_col = headers['VIN']
        last = int(ws.Cells(ws.Rows.Count, vin_col).End(-4162).Row)
        target = None
        for row_num in range(2, max(2, last) + 1):
            if str(ws.Cells(row_num, vin_col).Value or '').strip().upper() == vin.upper():
                target = row_num
                break
        if target is None:
            target = max(2, last + 1)
            if target > 2:
                try:
                    ws.Rows(target - 1).Copy()
                    ws.Rows(target).PasteSpecial(Paste=-4122)
                    excel.CutCopyMode = False
                except Exception:
                    pass
            ws.Cells(target, vin_col).Value = vin.upper()

        for key, header in mapping.items():
            value = result.get(key)
            if value not in (None, ''):
                ws.Cells(target, headers[header]).Value = value

        stamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ws.Cells(target, headers['Last Updated']).Value = stamp
        ws.Cells(target, headers['Updated By']).Value = getpass.getuser()

        try:
            ws.Rows(1).Font.Bold = True
            ws.Rows(1).WrapText = True
            for name in ('Warranty / Coverage Details', 'Major Components Details'):
                ws.Columns(headers[name]).WrapText = True
                ws.Columns(headers[name]).ColumnWidth = 42
            for name in ('Coverage Records JSON', 'Coverage Fields JSON', 'Major Components JSON', 'Major Component Fields JSON'):
                ws.Columns(headers[name]).Hidden = True
            for name in ('VIN', 'Product Serial Number', 'Chassis Serial Number', 'Engine Serial Number', 'Allison Transmission Serial Number'):
                ws.Columns(headers[name]).ColumnWidth = 22
            for name in ('Vehicle Model', 'Engine Model', 'Transmission Model', 'Customer Name'):
                ws.Columns(headers[name]).ColumnWidth = 26
        except Exception:
            pass

        workbook.Save()

        saved_vin = str(ws.Cells(target, vin_col).Value or '').strip().upper()
        if saved_vin != vin.upper():
            raise RuntimeError(f'Excel save verification failed for VIN {vin}.')

        for key, header in mapping.items():
            expected = result.get(key)
            if expected in (None, ''):
                continue
            actual = ws.Cells(target, headers[header]).Value
            if str(actual or '').strip() != str(expected).strip():
                raise RuntimeError(f'Excel save verification failed for {vin} field {header}.')

        update_vin(vin, result, str(path))
        print(f'Excel database verified and mirrored: {vin} -> {base.VIN_SHEET}', flush=True)
    finally:
        try:
            if excel is not None:
                excel.ScreenUpdating = True
                excel.EnableEvents = True
        except Exception:
            pass
        try:
            if workbook is not None and opened_here:
                workbook.Close(SaveChanges=True)
        except Exception:
            pass
        try:
            if excel is not None and created_excel:
                excel.Quit()
        except Exception:
            pass
        pythoncom.CoUninitialize()


def robust_vin_write(vin: str, result: dict[str, Any]) -> None:
    if not isinstance(result, dict) or result.get('_error'):
        raise RuntimeError(str(result.get('_error') if isinstance(result, dict) else 'OWL returned an invalid VIN result.'))
    last_error: Exception | None = None
    with base.excel_lock:
        for attempt in range(1, 7):
            try:
                _write_vin_once(vin, result)
                return
            except Exception as exc:
                last_error = exc
                if attempt < 6:
                    print(f'VIN Excel write attempt {attempt}/6 failed for {vin}: {exc}; retrying...', flush=True)
                    time.sleep(.5)
    raise RuntimeError(f'Could not write VIN {vin} to shared Excel database after 6 attempts: {last_error}')


base.read_master = force_live_owl_lookup
base.run_lookup = validated_owl_lookup
base.write_result = robust_vin_write


@base.app.get('/owl/status')
def owl_status():
    return {
        'ready': OWL_LOGIN.exists() and (ROOT / 'owl_lookup_v3.py').exists(),
        'source': 'OWL Coverage Info + Major Components',
        'version': base.VERSION,
        'message': 'VIN In-Service uses exact OWL labels and exact Major Components columns; no fuzzy page-text mapping.',
    }


@base.app.post('/owl/open')
def owl_open():
    if not OWL_LOGIN.exists():
        raise HTTPException(500, 'OWL login launcher is not installed. Download the current worker package.')
    py = ROOT / '.venv' / 'Scripts' / 'python.exe'
    if not py.exists():
        raise HTTPException(500, 'Local Python environment is not ready.')
    flags = getattr(subprocess, 'CREATE_NEW_CONSOLE', 0)
    subprocess.Popen([str(py), str(OWL_LOGIN)], cwd=str(ROOT), creationflags=flags)
    return {'ok': True, 'message': 'OWL login/browser opened locally.'}


if __name__ == '__main__':
    uvicorn.run(base.app, host='127.0.0.1', port=base.PORT, log_level='warning')
