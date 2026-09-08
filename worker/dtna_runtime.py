from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

import dtna_login_and_sync as base
from database_cache import write_table


# Keep the current DTNA collection flow. This file only fixes the integration
# behavior needed by the v5.16.1 worker.
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


def normalize_schema(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for column in DTNA_SCHEMA:
        if column not in result.columns:
            result[column] = ''
    return result[DTNA_SCHEMA]


def change_note(change: dict) -> str:
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


def apply_last_change_time(records: list[dict], changes: list[dict]) -> None:
    """Stamp every DTNA row with the date/time this DTNA run was performed.

    `lastChangeTime` is the latest DTNA refresh/write time, not a per-truck
    field-change timestamp. Every row written by the same run receives the same
    timestamp. changeCount/changeNotes still describe actual detected changes.
    """
    run_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    notes_by_serial: dict[str, list[str]] = {}
    for change in changes:
        serial = base.norm_serial(change.get('serialNo'))
        if not serial:
            continue
        notes_by_serial.setdefault(serial, []).append(change_note(change))

    prior_rows = base.previous_snapshot()
    prior_by_serial: dict[str, dict] = {}
    prior_by_vin: dict[str, dict] = {}
    for prior in prior_rows:
        serial = base.norm_serial(prior.get('serialNo'))
        vin = base.norm_vin(prior.get('VIN'))
        if serial:
            prior_by_serial[serial] = prior
        if vin:
            prior_by_vin[vin] = prior

    for row in records:
        serial = base.norm_serial(row.get('serialNo'))
        vin = base.norm_vin(row.get('VIN'))
        prior = prior_by_serial.get(serial) or prior_by_vin.get(vin) or {}
        current_notes = notes_by_serial.get(serial, [])

        if current_notes:
            row['changeCount'] = len(current_notes)
            row['changeNotes'] = ' | '.join(current_notes)
        else:
            prior_count = base.clean(prior.get('changeCount'))
            prior_notes = base.clean(prior.get('changeNotes'))
            row['changeCount'] = prior_count if prior_count else 0
            row['changeNotes'] = prior_notes

        row['lastChangeTime'] = run_time

    base.log(f'DTNA lastChangeTime stamped for {len(records)} rows at {run_time}.')


def mirror_dataframe(df: pd.DataFrame, destination: Path) -> None:
    df = normalize_schema(df)
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


def write_dtna(df: pd.DataFrame, destination: Path) -> None:
    fixed = normalize_schema(df)

    # Final guard: all rows from one DTNA run must carry a run timestamp.
    blanks = fixed['lastChangeTime'].fillna('').astype(str).str.strip().eq('')
    if blanks.any():
        stamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        fixed.loc[blanks, 'lastChangeTime'] = stamp
        base.log(f'Filled {int(blanks.sum())} missing DTNA lastChangeTime values with run time {stamp}.')

    _original_writer(fixed, destination)
    mirror_dataframe(fixed, destination)


# Patch the existing DTNA program in-place. database_service.py already launches
# this file, so no alternate runtime or renamed core file is involved.
base.add_change_notes_to_current_rows = apply_last_change_time
base.write_dataframe_into_same_excel = write_dtna


if __name__ == '__main__':
    raise SystemExit(base.main())
