from __future__ import annotations

import os
import re
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

import dtna_login_and_sync as base
from database_cache import write_table


# Preserve the known-good working program behavior.
try:
    base.PAYLOAD['orderToReview'] = True
except Exception:
    pass


DTNA_SCHEMA = [
    'VIN', 'inServiceDate', 'serialNo', 'leadSerialNo', 'changeCount',
    'changeNotes', 'lastChangeTime', 'vinSource', 'vinMatchMethod', 'soCode',
    'baseMdl', 'customer', 'statusMsg', 'statusDate', 'scheduled',
    'chassisStartDate', 'destRecvDate', 'origProjDelvDate', 'projDelvDate',
    'dispatchDate', 'deliveredDate', 'errorFlag', 'errorMessage', 'dlrHandshk',
    'estArrvDate', 'dateInvcPrt', 'mfgRlseDate', 'offlineDate', 'deliverDate',
    'vehNotSchCat', 'reqDelivery', 'drivableIndc', 'salesperson', 'bldLocation',
    'qtyOrdered', 'tsoSt', 'tsoNo', 'famCd', 'shCtry', 'vehOrdType',
    'daysOutActIndc', 'childSerials', 'createTcoUrl', 'orderNotToBeReviewedURL',
    'salespersonEmailId', 'navAppsByStatus', 'estStartDateCAE', 'estDueDateCAE',
    'greenDays', 'yellowDays', 'redDays', 'xferSoCd',
    '_dateHistory.statusDate', '_dateHistory.chassisStartDate',
    '_dateHistory.destRecvDate', '_dateHistory.origProjDelvDate',
    '_dateHistory.projDelvDate', '_dateHistory.dispatchDate',
    '_dateHistory.deliveredDate', 'revPDD', 'delvTrnptrDate', 'caeDaysOut',
]


def _normalize_dtna_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Keep the shared DTNA worksheet in the historical 62-column layout."""
    result = df.copy()
    for column in DTNA_SCHEMA:
        if column not in result.columns:
            result[column] = ''
    return result[DTNA_SCHEMA]


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


def _norm_path(value: str | Path) -> str:
    try:
        return os.path.normcase(os.path.abspath(str(value))).rstrip('\\/')
    except Exception:
        return str(value).lower().rstrip('\\/')


def _collect_excel_workbooks(pythoncom, win32com, destination: Path):
    """Find the workbook even when Excel exposes a OneDrive/SharePoint URL as FullName."""
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
                key = (str(wb.Name), str(wb.FullName))
                if key in seen:
                    continue
                seen.add(key)
                if _norm_path(str(wb.FullName)) == _norm_path(destination):
                    exact.append(wb)
                elif str(wb.Name).lower() == destination.name.lower():
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
                    key = (str(wb.Name), str(wb.FullName))
                    if key not in seen:
                        seen.add(key)
                        if _norm_path(str(wb.FullName)) == _norm_path(destination):
                            exact.append(wb)
                        elif str(wb.Name).lower() == destination.name.lower():
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


def _mirror_dtna_dataframe(df: pd.DataFrame, destination: Path) -> None:
    """Publish the exact freshly-collected DTNA dataset to the local website mirror."""
    df = _normalize_dtna_schema(df)
    headers = [str(c) for c in df.columns]
    rows: list[dict[str, str]] = []
    for raw_row in df.itertuples(index=False, name=None):
        row: dict[str, str] = {}
        for header, value in zip(headers, raw_row):
            if value is None:
                row[header] = ''
                continue
            try:
                if pd.isna(value):
                    row[header] = ''
                    continue
            except Exception:
                pass
            row[header] = str(value)
        rows.append(row)
    write_table(
        'DTNA',
        headers,
        rows,
        str(destination),
        'Fresh DTNA Sales Order + Dealer Reporting AUTO VIN collection',
    )
    base.log(f'Refreshed local website DTNA mirror with {len(rows)} collected rows.')


def _change_note(change: dict) -> str:
    change_type = base.clean(change.get('changeType'))
    field = base.clean(change.get('field'))
    old_value = base.clean(change.get('oldValue'))
    new_value = base.clean(change.get('newValue'))
    if change_type == 'FIELD CHANGED':
        return f"{field}: {old_value or '[blank]'} -> {new_value or '[blank]'}"
    if change_type == 'NEW ORDER':
        return 'NEW ORDER'
    if change_type == 'ORDER REMOVED':
        return 'ORDER REMOVED'
    return change_type or 'Changed'


_original_add_change_notes = base.add_change_notes_to_current_rows


def preserve_last_change_metadata(records, changes) -> None:
    """Keep DTNA last-change metadata across syncs and establish a baseline when none exists."""
    prior_rows = base.previous_snapshot()
    prior_by_key = {base.row_key(r): r for r in prior_rows}

    _original_add_change_notes(records, changes)

    history_by_serial: dict[str, list[dict]] = {}
    history_path = base.CHANGES_DIR / 'dtna_change_log.csv'
    if history_path.exists() and history_path.stat().st_size > 0:
        try:
            hist = pd.read_csv(history_path, dtype=str).fillna('')
            for item in hist.to_dict('records'):
                serial = base.norm_serial(item.get('serialNo'))
                if serial:
                    history_by_serial.setdefault(serial, []).append(item)
            for serial in history_by_serial:
                history_by_serial[serial].sort(key=lambda x: base.clean(x.get('changeTime')))
        except Exception as exc:
            base.log(f'Could not read DTNA change history while restoring last-change metadata: {exc}')

    current_changed = {
        base.norm_serial(c.get('serialNo'))
        for c in changes
        if base.norm_serial(c.get('serialNo'))
    }
    baseline_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    for row in records:
        serial = base.norm_serial(row.get('serialNo'))
        if serial in current_changed:
            continue

        prior = prior_by_key.get(base.row_key(row), {})
        prior_time = base.clean(prior.get('lastChangeTime'))
        prior_notes = base.clean(prior.get('changeNotes'))
        prior_count = base.clean(prior.get('changeCount'))

        history = history_by_serial.get(serial, [])
        latest = history[-1] if history else None
        recovered_time = prior_time or (base.clean(latest.get('changeTime')) if latest else '')
        recovered_notes = prior_notes or (_change_note(latest) if latest else '')

        if not base.clean(row.get('lastChangeTime')):
            row['lastChangeTime'] = recovered_time or baseline_time

        if not base.clean(row.get('changeNotes')):
            row['changeNotes'] = recovered_notes

        if not base.clean(row.get('changeCount')) or base.clean(row.get('changeCount')) == '0':
            if prior_count and prior_count != '0':
                row['changeCount'] = prior_count
            elif history:
                row['changeCount'] = len(history)
            else:
                row['changeCount'] = 0


def write_dataframe_into_same_excel(df: pd.DataFrame, destination: Path) -> None:
    """Write DTNA data into the canonical shared workbook and refresh the website mirror."""
    import pythoncom  # type: ignore
    import win32com.client  # type: ignore

    df = _normalize_dtna_schema(df)
    destination = destination.resolve()
    if not destination.exists():
        raise RuntimeError(f'Shared workbook no longer exists: {destination}')

    last_error = None
    for attempt in range(1, 7):
        pythoncom.CoInitialize()
        excel = workbook = None
        opened_here = created_excel = False
        try:
            workbook = _collect_excel_workbooks(pythoncom, win32com, destination)
            if workbook is not None:
                excel = workbook.Application
                base.log(f'Attached to already-open shared workbook: {workbook.FullName}')
            else:
                try:
                    excel = win32com.client.GetActiveObject('Excel.Application')
                except Exception:
                    excel = win32com.client.DispatchEx('Excel.Application')
                    excel.Visible = False
                    created_excel = True
                excel.DisplayAlerts = False
                workbook = excel.Workbooks.Open(
                    str(destination),
                    UpdateLinks=0,
                    ReadOnly=False,
                    IgnoreReadOnlyRecommended=True,
                    AddToMru=False,
                )
                opened_here = True
                base.log(f'Opened shared workbook for DTNA write: {destination}')

            if workbook is None:
                raise RuntimeError('Excel did not return the shared workbook object.')
            if bool(getattr(workbook, 'ReadOnly', False)):
                raise RuntimeError('Shared workbook is temporarily read-only.')

            excel.DisplayAlerts = False
            excel.ScreenUpdating = False
            excel.EnableEvents = False
            try:
                excel.Calculation = -4135
            except Exception:
                pass

            try:
                sheet = workbook.Worksheets('DTNA')
            except Exception:
                sheet = workbook.Worksheets.Add(After=workbook.Worksheets(workbook.Worksheets.Count))
                sheet.Name = 'DTNA'

            headers = [str(c) for c in df.columns]
            if not headers:
                raise RuntimeError('No DTNA columns were available to write.')

            base.log('Writing full DTNA dataset to shared workbook sheet: DTNA')
            table = None
            try:
                for i in range(1, int(sheet.ListObjects.Count) + 1):
                    candidate = sheet.ListObjects.Item(i)
                    if str(candidate.Name).strip().lower() in {'dtna', 'dtnadata'}:
                        table = candidate
                        break
            except Exception:
                table = None

            try:
                if table is not None and table.DataBodyRange is not None:
                    table.DataBodyRange.ClearContents()
                else:
                    sheet.UsedRange.ClearContents()
            except Exception:
                sheet.UsedRange.ClearContents()

            sheet.Range(sheet.Cells(1, 1), sheet.Cells(1, len(headers))).Value2 = tuple(headers)

            rows = []
            for raw_row in df.itertuples(index=False, name=None):
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
            for name in (
                'statusDate', 'chassisStartDate', 'destRecvDate', 'origProjDelvDate',
                'projDelvDate', 'dispatchDate', 'deliveredDate', 'changeNotes'
            ):
                col = header_lookup.get(name)
                if col:
                    sheet.Columns(col).WrapText = True
                    sheet.Columns(col).ColumnWidth = 24
            for name, width in {
                'VIN': 20, 'inServiceDate': 16, 'serialNo': 16, 'leadSerialNo': 18,
                'customer': 28, 'statusMsg': 22, 'lastChangeTime': 20
            }.items():
                col = header_lookup.get(name)
                if col:
                    sheet.Columns(col).ColumnWidth = width

            workbook.Save()
            base.log(f'Updated shared Excel database successfully: {destination} -> DTNA')
            _mirror_dtna_dataframe(df, destination)
            return
        except Exception as exc:
            last_error = exc
            base.log(f'Excel/database write attempt {attempt}/6 failed: {exc}')
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
        'DTNA data was collected, but Excel/database publishing failed after 6 attempts. '
        f'Target: {destination}\nDetails: {last_error}'
    )


# Override only the fragile integration points. The known-good DTNA browser/data
# collection stays in dtna_login_and_sync.py.
base.select_auto_vin = select_auto_vin
base.add_change_notes_to_current_rows = preserve_last_change_metadata
base.write_dataframe_into_same_excel = write_dataframe_into_same_excel


if __name__ == '__main__':
    raise SystemExit(base.main())
