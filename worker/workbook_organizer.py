from __future__ import annotations

from pathlib import Path

COLUMNS = [
    'VIN','Verification Status','In-Service Status','In-Service Date','Mileage',
    'Customer Result','Customer Name','Registered Customer Name',
    'Registered Customer Account','Ordered Customer Name','Last Updated','Updated By'
]
WIDTHS = [20,20,18,16,12,20,28,30,24,30,20,20]


def organize_workbook(path: Path) -> None:
    import os
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    excel = wb = None
    opened = created = False
    try:
        try:
            excel = win32com.client.GetActiveObject('Excel.Application')
        except Exception:
            excel = win32com.client.DispatchEx('Excel.Application')
            excel.Visible = False
            excel.DisplayAlerts = False
            created = True

        target = os.path.normcase(os.path.abspath(str(path)))
        try:
            for item in excel.Workbooks:
                if os.path.normcase(os.path.abspath(str(item.FullName))) == target:
                    wb = item
                    break
        except Exception:
            pass
        if wb is None:
            wb = excel.Workbooks.Open(str(path), UpdateLinks=0, ReadOnly=False, IgnoreReadOnlyRecommended=True)
            opened = True
        if bool(getattr(wb, 'ReadOnly', False)):
            raise RuntimeError('Shared workbook is read-only. Let OneDrive finish syncing and try again.')

        try:
            ws = wb.Worksheets('VIN Data')
        except Exception:
            ws = wb.Worksheets.Add()
            ws.Name = 'VIN Data'

        used_cols = max(1, int(ws.UsedRange.Columns.Count))
        old_headers = {}
        extras = []
        for c in range(1, used_cols + 1):
            h = str(ws.Cells(1, c).Value or '').strip()
            if h:
                old_headers[h] = c
                if h not in COLUMNS:
                    extras.append(h)
        ordered = COLUMNS + extras

        last_row = max(1, int(ws.UsedRange.Rows.Count))
        merged = {}
        blanks = []
        for r in range(2, last_row + 1):
            row = {h: ws.Cells(r, c).Value for h, c in old_headers.items()}
            vin = str(row.get('VIN') or '').strip().upper()
            if not vin:
                blanks.append(row)
                continue
            dest = merged.setdefault(vin, {'VIN': vin})
            for h, value in row.items():
                if value not in (None, ''):
                    dest[h] = value
        rows = list(merged.values()) + blanks

        ws.Cells.ClearContents()
        for c, h in enumerate(ordered, 1):
            ws.Cells(1, c).Value = h
        for r, row in enumerate(rows, 2):
            for c, h in enumerate(ordered, 1):
                if row.get(h) not in (None, ''):
                    ws.Cells(r, c).Value = row[h]

        last_data = max(2, len(rows) + 1)
        try:
            if ws.ListObjects.Count:
                ws.ListObjects(1).Resize(ws.Range(ws.Cells(1,1), ws.Cells(last_data,len(ordered))))
            else:
                t = ws.ListObjects.Add(1, ws.Range(ws.Cells(1,1), ws.Cells(last_data,len(ordered))), None, 1)
                t.Name = 'VINData'
        except Exception:
            pass

        ws.Rows(1).Font.Bold = True
        ws.Rows(1).WrapText = True
        ws.Rows(1).RowHeight = 30
        for i, width in enumerate(WIDTHS, 1):
            ws.Columns(i).ColumnWidth = width
        for i in range(len(WIDTHS) + 1, len(ordered) + 1):
            ws.Columns(i).ColumnWidth = 18
        try:
            ws.Columns(ordered.index('In-Service Date') + 1).NumberFormat = 'mm/dd/yyyy'
            ws.Columns(ordered.index('Mileage') + 1).NumberFormat = '0'
            ws.Columns(ordered.index('Last Updated') + 1).NumberFormat = 'mm/dd/yyyy hh:mm'
            ws.Activate()
            excel.ActiveWindow.SplitRow = 1
            excel.ActiveWindow.FreezePanes = True
        except Exception:
            pass
        wb.Save()
    finally:
        try:
            if wb is not None and opened:
                wb.Close(SaveChanges=True)
        except Exception:
            pass
        try:
            if excel is not None and created:
                excel.Quit()
        except Exception:
            pass
        pythoncom.CoUninitialize()
