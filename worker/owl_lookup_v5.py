from __future__ import annotations

import json
import re
from typing import Any

import owl_lookup_v4 as flow

core = flow.core

# Exact Coverage Information labels observed in the live OWL page.  The order is
# also useful for a safe text fallback when legacy OWL renders a label/value pair
# in markup that is not a normal sibling-cell relationship.
COVERAGE_LABELS = [
    'Product S/N',
    'Go To',
    'Make',
    'Unit #',
    'In Service Distance',
    'Base Model',
    'In Service Date',
    'Model',
    'Cab Start Date',
    'Order Date',
    'Build Date',
    'Offline Date',
    'Refurbished',
    'Customer Name',
    'PDI Date',
    'Special Conditions',
    'First Service Date',
    'PDI Submitting Location',
    'Coverage Determination',
]


def _normalize_distance(value: str) -> tuple[str, str]:
    """Return numeric mileage and the original normalized OWL distance.

    OWL examples are formatted like ``3551 MILES`` and ``0 MILES``.  Excel's
    Mileage column should receive the numeric value, while In Service Distance
    keeps the exact normalized portal value for audit/display.
    """
    raw = core.clean(value)
    if not raw:
        return '', ''
    m = re.match(r'^([0-9][0-9,]*(?:\.\d+)?)\s*(?:MILES?|MI)?$', raw, re.I)
    if not m:
        return raw, raw
    numeric = m.group(1).replace(',', '')
    if numeric.endswith('.0'):
        numeric = numeric[:-2]
    return numeric, raw.upper()


def _text_exact_value(text: str, label: str) -> str:
    """Safe fallback bounded by the next known Coverage label.

    This is not fuzzy searching: the requested label must match exactly and the
    captured value is bounded by another known OWL label.  It exists because
    old OWL pages sometimes render labels/values in flattened legacy tables.
    """
    if not text:
        return ''
    labels = sorted((re.escape(x) for x in COVERAGE_LABELS), key=len, reverse=True)
    next_label = '|'.join(labels)
    pattern = rf'(?<![A-Za-z0-9]){re.escape(label)}\s*:\s*(.*?)(?=\s+(?:{next_label})\s*:|$)'
    m = re.search(pattern, text, re.I | re.S)
    if not m:
        return ''
    return core.clean(m.group(1))


def _coverage_value(frame, text: str, labels: list[str]) -> str:
    for label in labels:
        value = flow._field_value(frame, [label])
        if core.clean(value):
            return core.clean(value)
    for label in labels:
        value = _text_exact_value(text, label)
        if value:
            return value
    return ''


def _coverage_table(frame) -> list[dict[str, str]]:
    # Prefer the actual CHASSIS Warranty Coverage table, not any arbitrary table
    # containing the word "Coverage" elsewhere on the page.
    rows = core.exact_table(frame, ['Coverages', 'Time Period', 'End Date', 'Distance', 'Unit'])
    if rows:
        return rows
    rows = core.exact_table(frame, ['Coverages', 'End Date', 'Distance'])
    if rows:
        return rows
    return []


def _coverage_names_and_dates(rows: list[dict[str, str]]) -> tuple[str, str]:
    names: list[str] = []
    dates: list[str] = []
    for row in rows:
        name = core.record_value(row, 'Coverages')
        end = core.record_value(row, 'End Date')
        if name:
            names.append(name)
            dates.append(end)
    return ' | '.join(names), ' | '.join(dates)


def coverage_lookup(context, vin: str) -> dict[str, Any]:
    core.open_url(context, core.OWL_COVERAGE_URL, 'Coverage Info')
    frame = flow._submit_and_wait(context, vin, 'Coverage Info')
    text = core.body_text(frame)
    if flow._is_not_found(text):
        return {
            'vin': vin,
            'verificationStatus': 'Not Found',
            'customerResult': 'VIN not found in OWL',
            'source': 'OWL Coverage Info',
        }

    # Exact live-page mappings. Never substitute generic Model/Template/etc.
    product_sn = _coverage_value(frame, text, ['Product S/N']) or vin
    make = _coverage_value(frame, text, ['Make'])
    distance_raw = _coverage_value(frame, text, ['In Service Distance'])
    mileage, in_service_distance = _normalize_distance(distance_raw)
    in_service_date = _coverage_value(frame, text, ['In Service Date'])
    cab_start_date = _coverage_value(frame, text, ['Cab Start Date'])
    build_date = _coverage_value(frame, text, ['Build Date'])
    refurbished = _coverage_value(frame, text, ['Refurbished'])
    pdi_date = _coverage_value(frame, text, ['PDI Date'])
    first_service_date = _coverage_value(frame, text, ['First Service Date'])
    go_to = _coverage_value(frame, text, ['Go To'])
    unit_number = _coverage_value(frame, text, ['Unit #'])
    base_model = _coverage_value(frame, text, ['Base Model'])
    model = _coverage_value(frame, text, ['Model'])
    order_date = _coverage_value(frame, text, ['Order Date'])
    offline_date = _coverage_value(frame, text, ['Offline Date'])
    customer_name = _coverage_value(frame, text, ['Customer Name'])
    special_conditions = _coverage_value(frame, text, ['Special Conditions'])
    pdi_submitting_location = _coverage_value(frame, text, ['PDI Submitting Location'])

    coverage_rows = _coverage_table(frame)
    coverage_names, coverage_end_dates = _coverage_names_and_dates(coverage_rows)

    # A successfully populated OWL Coverage page with no In Service Date is a
    # genuine NOT IN SERVICE result.  Do not confuse it with parser failure: the
    # page has already passed _submit_and_wait and must contain populated result
    # data before we reach this point.
    in_service_status = 'In Service' if in_service_date else 'Not In Service'

    exact_fields = {
        'Product S/N': product_sn,
        'Make': make,
        'In Service Distance': in_service_distance,
        'In Service Date': in_service_date,
        'Cab Start Date': cab_start_date,
        'Build Date': build_date,
        'Refurbished': refurbished,
        'PDI Date': pdi_date,
        'First Service Date': first_service_date,
        'Go To': go_to,
        'Unit #': unit_number,
        'Base Model': base_model,
        'Model': model,
        'Order Date': order_date,
        'Offline Date': offline_date,
        'Customer Name': customer_name,
        'Special Conditions': special_conditions,
        'PDI Submitting Location': pdi_submitting_location,
    }

    core.log(
        f'OWL {vin}: Coverage verified exact mapping: '
        f'status={in_service_status}; date={in_service_date or "blank"}; '
        f'mileage={mileage or "blank"}; customer={customer_name or "blank"}; '
        f'baseModel={base_model or "blank"}; model={model or "blank"}; '
        f'coverageRows={len(coverage_rows)}'
    )

    return {
        'vin': vin,
        'verificationStatus': 'Verified',
        'productSerialNumber': product_sn,
        'vehicleMake': make,
        'baseModel': base_model,
        'vehicleModel': model or base_model,
        'buildDate': build_date,
        'cabStartDate': cab_start_date,
        'pdiDate': pdi_date,
        'firstServiceDate': first_service_date,
        'orderDate': order_date,
        'offlineDate': offline_date,
        'unitNumber': unit_number,
        'inServiceStatus': in_service_status,
        'inServiceDate': in_service_date,
        'mileage': mileage,
        'inServiceDistance': in_service_distance,
        # Customer must ONLY come from Coverage Information -> Customer Name.
        # Blank OWL customer remains blank; do not fill from Template Name,
        # ordered customer, connected data, or any neighboring text.
        'customerResult': customer_name,
        'customerName': customer_name,
        'registeredCustomerName': customer_name,
        'refurbished': refurbished,
        'specialConditions': special_conditions,
        'pdiSubmittingLocation': pdi_submitting_location,
        'goTo': go_to,
        'freightlinerExtendedCoverageNames': coverage_names,
        'freightlinerExtendedCoverageEndDates': coverage_end_dates,
        'warrantyCoverage': '\n'.join(
            ' | '.join(f'{k}: {v}' for k, v in row.items() if v)
            for row in coverage_rows
        ),
        'coverageRecordsJson': json.dumps(coverage_rows, ensure_ascii=False),
        'coverageFieldsJson': json.dumps(exact_fields, ensure_ascii=False),
        'source': 'OWL Coverage Info + Major Components',
    }


# Keep v4's corrected Major Components flow (Chassis S/N -> Tab -> populated
# Component/MFG/Model/Component S/N table), but replace Coverage extraction with
# this calibrated exact-field mapper.
core.coverage_lookup = coverage_lookup
core.major_lookup = flow.major_lookup


if __name__ == '__main__':
    raise SystemExit(core.main())
