from __future__ import annotations

from datetime import datetime
from pathlib import Path
import os
import re
import time

import pandas as pd

import dtna_login_and_sync as base
from database_cache import write_table


# Keep the proven DTNA browser/data flow in dtna_login_and_sync.py.
# The localhost app may override only the workbook/sheet target through env vars.
try:
    base.PAYLOAD['orderToReview'] = True
except Exception:
    pass


LOCAL_WORKBOOK_ENV = 'DIEHL_DTNA_WORKBOOK'
LOCAL_SHEET_ENV = 'DIEHL_DTNA_SHEET'


_original_get_working_excel = base.get_working_excel


def get_working_excel_with_local_override() -> Path:
    selected = os.environ.get(LOCAL_WORKBOOK_ENV, '').strip()
    if not selected:
        return _original_get_working_excel()
    workbook = Path(os.path.expandvars(selected)).expanduser().resolve()
    if not workbook.exists():
        raise RuntimeError(f'Selected localhost workbook does not exist: {workbook}')
    if workbook.suffix.lower() not in {'.xlsx', '.xlsm'}:
        raise RuntimeError('Selected localhost workbook must be an .xlsx or .xlsm file.')
    base.log(f'Using localhost-selected DTNA workbook: {workbook}')
    return workbook


def selected_sheet_name() -> str:
    return os.environ.get(LOCAL_SHEET_ENV, '').strip() or 'DTNA'


def select_auto_vin(page) -> None:
    """Select AUTO VIN from the Templates field in the Export to Excel dialog."""
    dialog = None
    for selector in ('[role="dialog"]', 'mat-dialog-container', '.mat-dialog-container', '.mat-mdc-dialog-container'):
        try:
            loc = page.locator(selector)
            for i in range(loc.count()):
                item = loc.nth(i)
                if item.is_visible() and 'Export to Excel' in (item.inner_text() or ''):
                    dialog = item
                    break
        except Exception:
            pass
        if dialog is not None:
            break

    if dialog is None:
        try:
            title = page.get_by_text(re.compile(r'^\s*Export\s+to\s+Excel\s*$', re.I), exact=False)
            title.first.wait_for(state='visible', timeout=15000)
            dialog = title.first.locator('xpath=ancestor::*[@role="dialog" or self::mat-dialog-container][1]')
        except Exception:
            dialog = None

    scope = dialog if dialog is not None else page

    try:
        selects = scope.locator('select')
        for i in range(selects.count()):
            sel = selects.nth(i)
            if not sel.is_visible():
                continue
            opts = sel.locator('option').all_text_contents()
            match = next((x for x in opts if re.fullmatch(r'\s*AUTO\s*VIN\s*', x or '', re.I)), None)
            if match:
                sel.select_option(label=match)
                return
    except Exception:
        pass

    opened = False
    try:
        template_text = scope.get_by_text(re.compile(r'^\s*Templates\s*$', re.I), exact=True)
        for i in range(template_text.count()):
            label = template_text.nth(i)
            if not label.is_visible():
                continue
            opened = bool(label.evaluate("""el => {
                const field = el.closest('mat-form-field') || el.parentElement || el;
                const candidates = [
                    field.querySelector('mat-select'),
                    field.querySelector('[role="combobox"]'),
                    field.querySelector('.mat-select-trigger'),
                    field.querySelector('.mat-mdc-select-trigger'),
                    field
                ].filter(Boolean);
                for (const c of candidates) {
                    const r = c.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) { c.click(); return true; }
                }
                return false;
            }"""))
            if opened:
                break
    except Exception:
        pass

    if not opened:
        for selector in ('mat-select', '[role="combobox"]', '.mat-select-trigger', '.mat-mdc-select-trigger'):
            try:
                loc = scope.locator(selector)
                for i in range(loc.count()):
                    item = loc.nth(i)
                    if item.is_visible():
                        item.click()
                        opened = True
                        break
            except Exception:
                pass
            if opened:
                break

    if opened:
        page.wait_for_timeout(700)
        for locator in (
            page.get_by_role('option', name=re.compile(r'^\s*AUTO\s*VIN\s*$', re.I)),
            page.get_by_text(re.compile(r'^\s*AUTO\s*VIN\s*$', re.I), exact=True),
        ):
            try:
                for i in range(locator.count()):
                    option = locator.nth(i)
                    if option.is_visible():
                        option.click()
                        page.wait_for_timeout(400)
                        return
            except Exception:
                pass

    print()
    print('AUTO VIN could not be selected automatically.')
    print('In the Export to Excel window, open Templates and choose AUTO VIN.')
    input('After AUTO VIN is selected, return here and press ENTER to continue... ')


_original_add_change_notes = base.add_change_notes_to_current_rows


def add_change_notes_with_run_time(records: list[dict], changes: list[dict]) -> None:
    _original_add_change_notes(records, changes)
    run_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    for row in records:
        row['lastChangeTime'] = run_time
    base.log(f'DTNA lastChangeTime set to {run_time} for all {len(records)} rows.')


def _norm_path(value: str | Path) -> str:
    try:
        return os.path.normcase(os.path.abspath(str(value))).rstrip('\\/')
    except Exception:
        return str(value).lower().rstrip('\\/')


def _find_open_workbook(pythoncom, win32com, destination: Path):
    exact = []
    same_name = []
    seen = set()

    def inspect_app(app) -> None:
        try:
            count = int(app.Workbooks.Count)
        except Exception:
            return
        for i in range(1, count + 1):
            try:
                wb = app.Workbooks.Item(i)
                name = str(wb.Name or '')
                full = str(wb.FullName or '')
                key = (name.casefold(), full.casefold())
                if key in seen:
                    continue
                seen.add(key)
                if full and _norm_path(full) == _norm_path(destination):
                    exact.append(wb)
                elif name.casefold() == destination.name.casefold():
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
                    key = (name.casefold(), full.casefold())
                    if key in seen:
                        continue
                    seen.add(key)
                    if full and _norm_path(full) == _norm_path(destination):
                        exact.append(wb)
                    elif name.casefold() == destination.name.casefold():
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
            key = (str(wb.Name).casefold(), str(wb.FullName).casefold())
        except Exception:
            continue
        if key not in keys:
            keys.add(key)
            unique.append(wb)
    return unique[0] if len(unique) == 1 else None


def _mirror_dataframe(df: pd.DataFrame, destination: Path) -> None:
    headers = [str(column) for column in df.columns]
    rows: list[dict[str, str]] = []
    for raw_row in df.itertuples(index=False, name=None):
        item: dict[str, str] = {}
        for header, value in zip(headers, raw_row):
            if value is None:
                item[header] = ''
                continue
            try:
                if pd.isna(value):
                    item[header] = ''
                    continue
            except Exception:
                pass
            item[header] = str(value)
        rows.append(item)

    write_table(
        'DTNA', headers, rows, str(destination),
        'Fresh DTNA Sales Order + Dealer Reporting AUTO VIN collection',
    )
    base.log(f'Refreshed local website DTNA mirror with {len(rows)} collected rows.')


def write_dataframe_into_selected_excel(df: pd.DataFrame, destination: Path) -> None:
    """Write DTNA into the explicitly selected workbook and existing sheet."""
    import pythoncom  # type: ignore
    import win32com.client  # type: ignore

    fixed = df.copy()
    run_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    fixed['lastChangeTime'] = run_time

    destination = destination.resolve()
    sheet_name = selected_sheet_name()
    strict_existing_sheet = bool(os.environ.get(LOCAL_WORKBOOK_ENV, '').strip())

    if not destination.exists():
        raise RuntimeError(f'Selected workbook no longer exists: {destination}')

    last_error = None
    for attempt in range(1, 7):
        pythoncom.CoInitialize()
        excel = workbook = None
        opened_here = created_excel = False
        try:
            workbook = _find_open_workbook(pythoncom, win32com, destination)
            if workbook is not None:
                excel = workbook.Application
                base.log(f'Attached to selected OPEN workbook: {workbook.FullName}')
            else:
                excel = win32com.client.DispatchEx('Excel.Application')
                created_excel = True
                excel.Visible = False
                excel.DisplayAlerts = False
                workbook = excel.Workbooks.Open(
                    str(destination), UpdateLinks=0, ReadOnly=False,
                    IgnoreReadOnlyRecommended=True, AddToMru=False,
                )
                opened_here = True
                base.log(f'Opened selected workbook for DTNA write: {destination}')

            if workbook is None:
                raise RuntimeError('Excel did not return the selected workbook object.')
            if bool(getattr(workbook, 'ReadOnly', False)):
                raise RuntimeError('The selected workbook is read-only in Excel.')

            excel.DisplayAlerts = False
            excel.ScreenUpdating = False
            excel.EnableEvents = False
            try:
                excel.Calculation = -4135
            except Exception:
                pass

            try:
                sheet = workbook.Worksheets(sheet_name)
            except Exception:
                if strict_existing_sheet:
                    raise RuntimeError(
                        f'The selected workbook does not contain the existing sheet "{sheet_name}". '
                        'Choose a sheet that already exists in the workbook.'
                    )
                sheet = workbook.Worksheets.Add(After=workbook.Worksheets(workbook.Worksheets.Count))
                sheet.Name = sheet_name

            headers = [str(c) for c in fixed.columns]
            if not headers:
                raise RuntimeError('No DTNA columns were available to write.')

            table = None
            try:
                for i in range(1, int(sheet.ListObjects.Count) + 1):
                    candidate = sheet.ListObjects.Item(i)
                    if str(candidate.Name).strip().lower() in {'dtna', 'dtnadata'}:
                        table = candidate
                        break
            except Exception:
                table = None

            if table is not None:
                try:
                    if table.DataBodyRange is not None:
                        table.DataBodyRange.ClearContents()
                    table.HeaderRowRange.ClearContents()
                except Exception:
                    pass
            else:
                sheet.UsedRange.ClearContents()

            sheet.Range(sheet.Cells(1, 1), sheet.Cells(1, len(headers))).Value2 = tuple(headers)

            rows = []
            for raw_row in fixed.itertuples(index=False, name=None):
                safe = []
                for value in raw_row:
                    if value is None:
                        safe.append('')
                        continue
                    try:
                        if pd.isna(value):
                            safe.append('')
                            continue
                    except Exception:
                        pass
                    safe.append(str(value))
                rows.append(tuple(safe))

            block_size = 75
            for offset in range(0, len(rows), block_size):
                block = rows[offset:offset + block_size]
                first_row = offset + 2
                last_row = first_row + len(block) - 1
                sheet.Range(sheet.Cells(first_row, 1), sheet.Cells(last_row, len(headers))).Value2 = tuple(block)
                if offset % 300 == 0:
                    base.log(f'Writing Excel rows {first_row}-{last_row} of {len(rows) + 1}')

            target_range = sheet.Range(
                sheet.Cells(1, 1),
                sheet.Cells(max(2, len(rows) + 1), len(headers)),
            )
            if table is not None:
                try:
                    table.Resize(target_range)
                except Exception:
                    pass
            else:
                try:
                    table = sheet.ListObjects.Add(1, target_range, None, 1)
                    table.Name = 'DTNAData'
                except Exception:
                    pass

            header_lookup = {name: idx + 1 for idx, name in enumerate(headers)}
            for name in ('statusDate', 'chassisStartDate', 'destRecvDate', 'origProjDelvDate', 'projDelvDate', 'dispatchDate', 'deliveredDate', 'changeNotes'):
                col = header_lookup.get(name)
                if col:
                    sheet.Columns(col).WrapText = True
                    sheet.Columns(col).ColumnWidth = 24
            for name, width in {
                'VIN': 20, 'inServiceDate': 16, 'serialNo': 16,
                'leadSerialNo': 18, 'customer': 28, 'statusMsg': 22,
                'lastChangeTime': 20,
            }.items():
                col = header_lookup.get(name)
                if col:
                    sheet.Columns(col).ColumnWidth = width

            workbook.Save()
            base.log(f'UPDATED SELECTED WORKBOOK: {workbook.FullName} -> {sheet_name}')
            base.log(f'DTNA lastChangeTime written as {run_time} for {len(rows)} rows.')
            _mirror_dataframe(fixed, destination)
            return

        except Exception as exc:
            last_error = exc
            base.log(f'Excel write attempt {attempt}/6 failed: {exc}')
            if attempt < 6:
                time.sleep(2)
        finally:
            try:
                if excel is not None:
                    excel.ScreenUpdating = True
                    excel.EnableEvents = True
                    try:
                        excel.Calculation = -4105
                    except Exception:
                        pass
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

    raise RuntimeError(
        'DTNA could not update the selected workbook after 6 attempts. '
        f'Target: {destination} | Sheet: {sheet_name}\nDetails: {last_error}'
    )


base.get_working_excel = get_working_excel_with_local_override
base.select_auto_vin = select_auto_vin
base.add_change_notes_to_current_rows = add_change_notes_with_run_time
base.write_dataframe_into_same_excel = write_dataframe_into_selected_excel


if __name__ == '__main__':
    raise SystemExit(base.main())
