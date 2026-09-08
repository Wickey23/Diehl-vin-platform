from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

import pandas as pd

import dtna_login_and_sync as base
from database_cache import write_table


# Keep the proven DTNA browser/data flow in dtna_login_and_sync.py.
# This runtime only patches the integration points that have historically
# needed help: AUTO VIN selection, last-run timestamping, Excel write/mirror.
try:
    base.PAYLOAD['orderToReview'] = True
except Exception:
    pass


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
    """Use the original proven change-note logic, then stamp this DTNA run time."""
    _original_add_change_notes(records, changes)
    run_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    for row in records:
        row['lastChangeTime'] = run_time
    base.log(f'DTNA lastChangeTime set to {run_time} for all {len(records)} rows.')


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
        'DTNA',
        headers,
        rows,
        str(destination),
        'Fresh DTNA Sales Order + Dealer Reporting AUTO VIN collection',
    )
    base.log(f'Refreshed local website DTNA mirror with {len(rows)} collected rows.')


_original_writer = base.write_dataframe_into_same_excel


def write_dataframe_with_run_time(df: pd.DataFrame, destination: Path) -> None:
    """Final write guard: stamp every dataframe row before Excel receives it."""
    fixed = df.copy()
    run_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    fixed['lastChangeTime'] = run_time
    base.log(f'Final DTNA Excel write timestamp: {run_time} for {len(fixed)} rows.')
    _original_writer(fixed, destination)
    _mirror_dataframe(fixed, destination)


# These are the same integration hooks used by the proven Aug 18/19 runtime.
base.select_auto_vin = select_auto_vin
base.add_change_notes_to_current_rows = add_change_notes_with_run_time
base.write_dataframe_into_same_excel = write_dataframe_with_run_time


if __name__ == '__main__':
    raise SystemExit(base.main())
