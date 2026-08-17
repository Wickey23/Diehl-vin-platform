from __future__ import annotations

from pathlib import Path

VIN_SHEET = 'VIN In-Service'
DTNA_SHEET = 'DTNA'
VIN_COLUMNS = [
    'VIN','Verification Status','In-Service Status','In-Service Date','Mileage',
    'Customer Result','Customer Name','Registered Customer Name',
    'Registered Customer Account','Ordered Customer Name','Last Updated','Updated By'
]
VIN_WIDTHS = [20,20,18,16,12,20,28,30,24,30,20,20]


def _find_open_workbook(excel, path: Path):
    import os
    target = os.path.normcase(os.path.abspath(str(path)))
    try:
        for wb in excel.Workbooks:
            try:
                if os.path.normcase(os.path.abspath(str(wb.FullName))) == target:
                    return wb
            except Exception:
                pass
    except Exception:
        pass
    return None


def _ensure_sheet(wb, name: str):
    try:
        return wb.Worksheets(name)
    except Exception:
        ws = wb.Worksheets.Add(After=wb.Worksheets(wb.Worksheets.Count))
        ws.Name = name
        return ws


def _read_rows(ws):
    used_cols = max(1, int(ws.UsedRange.Columns.Count))
    headers = {}
    extras = []
    for c in range(1, used_cols + 1):
        h = str(ws.Cells(1, c).Value or '').strip()
        if h:
            headers[h] = c
            if h not in VIN_COLUMNS:
                extras.append(h)
    ordered = VIN_COLUMNS + extras
    last_row = max(1, int(ws.UsedRange.Rows.Count))
    merged = {}
    for r in range(2, last_row + 1):
        row = {h: ws.Cells(r, c).Value for h, c in headers.items()}
        vin = str(row.get('VIN') or '').strip().upper()
        if not vin:
            continue
        dest = merged.setdefault(vin, {'VIN': vin})
        for h, value in row.items():
            if value not in (None, ''):
                dest[h] = value
    return ordered, list(merged.values())


def _organize_vin_sheet(ws, source_ws=None):
    read_from = source_ws or ws
    ordered, rows = _read_rows(read_from)

    ws.Cells.ClearContents()
    for c, h in enumerate(ordered, 1):
        ws.Cells(1, c).Value = h
    for r, row in enumerate(rows, 2):
        for c, h in enumerate(ordered, 1):
            value = row.get(h)
            if value not in (None, ''):
                ws.Cells(r, c).Value = value

    last_data = max(2, len(rows) + 1)
    try:
        while ws.ListObjects.Count > 1:
            ws.ListObjects(ws.ListObjects.Count).Unlist()
        if ws.ListObjects.Count:
            table = ws.ListObjects(1)
            table.Resize(ws.Range(ws.Cells(1,1), ws.Cells(last_data,len(ordered))))
        else:
            table = ws.ListObjects.Add(1, ws.Range(ws.Cells(1,1), ws.Cells(last_data,len(ordered))), None, 1)
        try:
            table.Name = 'VINInServiceData'
        except Exception:
            pass
    except Exception:
        pass

    ws.Rows(1).Font.Bold = True
    ws.Rows(1).WrapText = True
    ws.Rows(1).RowHeight = 30
    for i, width in enumerate(VIN_WIDTHS, 1):
        ws.Columns(i).ColumnWidth = width
    for i in range(len(VIN_WIDTHS) + 1, len(ordered) + 1):
        ws.Columns(i).ColumnWidth = 18
    try:
        ws.Columns(ordered.index('In-Service Date') + 1).NumberFormat = 'mm/dd/yyyy'
        ws.Columns(ordered.index('Mileage') + 1).NumberFormat = '0'
        ws.Columns(ordered.index('Last Updated') + 1).NumberFormat = 'mm/dd/yyyy hh:mm'
    except Exception:
        pass


def _organize_dtna_sheet(ws):
    if ws.Cells(1,1).Value in (None, ''):
        headers = [
            'VIN','Serial Number','Sales Order','Status','Status Date','Customer',
            'Base Model','In-Service Date','Last Updated'
        ]
        for c, h in enumerate(headers, 1):
            ws.Cells(1, c).Value = h
    ws.Rows(1).Font.Bold = True
    ws.Rows(1).WrapText = True
    ws.Rows(1).RowHeight = 30
    try:
        ws.UsedRange.Columns.AutoFit()
        count = max(1, int(ws.UsedRange.Columns.Count))
        for c in range(1, count + 1):
            width = ws.Columns(c).ColumnWidth
            if width > 35:
                ws.Columns(c).ColumnWidth = 35
            elif width < 12:
                ws.Columns(c).ColumnWidth = 12
    except Exception:
        pass


def organize_workbook(path: Path) -> None:
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    excel = wb = None
    opened_here = created_excel = False
    try:
        try:
            excel = win32com.client.GetActiveObject('Excel.Application')
        except Exception:
            excel = win32com.client.DispatchEx('Excel.Application')
            excel.Visible = False
            excel.DisplayAlerts = False
            created_excel = True

        wb = _find_open_workbook(excel, path)
        if wb is None:
            wb = excel.Workbooks.Open(str(path), UpdateLinks=0, ReadOnly=False, IgnoreReadOnlyRecommended=True)
            opened_here = True
        if bool(getattr(wb, 'ReadOnly', False)):
            raise RuntimeError('Shared workbook opened read-only. Let OneDrive finish syncing and try again.')

        legacy = None
        try:
            legacy = wb.Worksheets('VIN Data')
        except Exception:
            pass

        try:
            vin_ws = wb.Worksheets(VIN_SHEET)
        except Exception:
            if legacy is not None:
                legacy.Name = VIN_SHEET
                vin_ws = legacy
                legacy = None
            else:
                vin_ws = _ensure_sheet(wb, VIN_SHEET)

        dtna_ws = _ensure_sheet(wb, DTNA_SHEET)

        _organize_vin_sheet(vin_ws, legacy)
        _organize_dtna_sheet(dtna_ws)

        if legacy is not None:
            try:
                excel.DisplayAlerts = False
                legacy.Delete()
            except Exception:
                pass

        try:
            vin_ws.Move(Before=wb.Worksheets(1))
            if dtna_ws.Index != 2:
                dtna_ws.Move(After=vin_ws)
            vin_ws.Activate()
            excel.ActiveWindow.SplitRow = 1
            excel.ActiveWindow.FreezePanes = True
        except Exception:
            pass

        wb.Save()
    finally:
        try:
            if wb is not None and opened_here:
                wb.Close(SaveChanges=True)
        except Exception:
            pass
        try:
            if excel is not None and created_excel:
                excel.Quit()
        except Exception:
            pass
        pythoncom.CoUninitialize()
