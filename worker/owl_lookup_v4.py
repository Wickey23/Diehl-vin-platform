from __future__ import annotations

import json
import re
import time
from typing import Any

import owl_lookup_v3 as core


def _is_not_found(text: str) -> bool:
    return bool(re.search(r'not\s+found|invalid\s+(vin|serial)|no\s+matching|no\s+(vehicle|record|coverage|results?)', text or '', re.I))


def _field_value(frame, labels: list[str]) -> str:
    return core.exact_label_value(frame, labels)


def _major_rows(frame) -> list[dict[str, str]]:
    return core.exact_table(frame, ['Component', 'MFG', 'Model', 'Component S/N'])


def _coverage_ready(frame) -> bool:
    # Wait for actual result data, not merely the VIN remaining in Product S/N.
    exact_fields = [
        _field_value(frame, ['In Service Date', 'In-Service Date']),
        _field_value(frame, ['Mileage', 'In Service Mileage', 'In-Service Mileage', 'In Service Distance', 'In-Service Distance']),
        _field_value(frame, ['Registered Customer Name', 'Customer Name', 'Registered Customer']),
        _field_value(frame, ['Warranty Status', 'Coverage Status']),
        _field_value(frame, ['Build Date', 'Manufacture Date', 'Manufactured Date']),
    ]
    if any(core.clean(v) for v in exact_fields):
        return True
    if core.exact_table(frame, ['Coverage']):
        return True
    if core.exact_table(frame, ['Description']):
        return True
    return False


def _major_ready(frame, vin: str) -> bool:
    # Major Components is only ready when the vehicle header and/or component table has populated.
    chassis = core.clean(_field_value(frame, ['Chassis S/N'])).upper()
    model = core.clean(_field_value(frame, ['Make/Base/Model']))
    in_service = core.clean(_field_value(frame, ['In Service Date']))
    rows = _major_rows(frame)

    if chassis and chassis != vin:
        # Reject a stale vehicle from a previous lookup.
        normalized_chassis = re.sub(r'[^A-Z0-9]', '', chassis)
        normalized_vin = re.sub(r'[^A-Z0-9]', '', vin.upper())
        if normalized_chassis != normalized_vin:
            return False

    if rows:
        return True
    if chassis and (model or in_service):
        return True
    return False


def _submit_and_wait(context, vin: str, page_kind: str, timeout: float = 25.0):
    page, frame, field = core.find_main_product_sn(context, timeout=15.0)
    if 'quicksearch' in (page.url or '').lower():
        raise RuntimeError(f'{page_kind}: OWL is on Quick Search; refusing to enter VIN there.')

    box = field.bounding_box()
    if not box or box['x'] < core.MIN_MAIN_X:
        raise RuntimeError(f'{page_kind}: Product S/N candidate is inside the left sidebar.')

    # Always force the requested VIN into THIS page's Product S/N input.
    field.click()
    field.fill('')
    field.fill(vin)
    actual = core.clean(field.input_value()).upper()
    if actual != vin:
        field.fill('')
        field.type(vin, delay=8)
        actual = core.clean(field.input_value()).upper()
    if actual != vin:
        raise RuntimeError(f'{page_kind}: Product S/N did not contain the complete VIN {vin}.')

    # Re-check immediately before Tab so a page script cannot silently replace it.
    actual_before_tab = core.clean(field.input_value()).upper()
    if actual_before_tab != vin:
        raise RuntimeError(f'{page_kind}: Product S/N changed before Tab; refusing stale lookup.')

    core.log(f'OWL {vin}: {page_kind} Product S/N verified at x={round(box["x"])}; pressing Tab now.')
    field.press('Tab')

    # No fixed sleep. Poll the actual OWL result state until it is populated.
    deadline = time.time() + timeout
    stable_hits = 0
    last_signature = ''
    while time.time() < deadline:
        if 'quicksearch' in (page.url or '').lower():
            raise RuntimeError(f'{page_kind}: OWL navigated to Quick Search after Tab; result rejected.')

        for _candidate_page, candidate_frame in core.iter_frames(context):
            text = core.body_text(candidate_frame)
            if _is_not_found(text):
                core.log(f'OWL {vin}: {page_kind} returned explicit not-found state.')
                return candidate_frame

            if page_kind == 'Major Components':
                ready = _major_ready(candidate_frame, vin)
            else:
                ready = _coverage_ready(candidate_frame)

            if not ready:
                continue

            signature = core.main_signature(candidate_frame, vin)
            if signature and signature == last_signature:
                stable_hits += 1
            else:
                last_signature = signature
                stable_hits = 1

            # Require two consecutive populated reads to avoid harvesting during an OWL redraw.
            if stable_hits >= 2:
                core.log(f'OWL {vin}: {page_kind} information populated and stable; extracting now.')
                return candidate_frame

        time.sleep(.08)

    if page_kind == 'Major Components':
        raise RuntimeError(
            f'{page_kind}: VIN {vin} was entered and Tab was pressed, but the Major Components '
            'vehicle/component information never populated.'
        )
    raise RuntimeError(f'{page_kind}: VIN {vin} was entered and Tab was pressed, but OWL information never populated.')


def coverage_lookup(context, vin: str) -> dict[str, Any]:
    page = core.open_url(context, core.OWL_COVERAGE_URL, 'Coverage Info')
    frame = _submit_and_wait(context, vin, 'Coverage Info')
    text = core.body_text(frame)
    if _is_not_found(text):
        return {'vin': vin, 'verificationStatus': 'Not Found', 'customerResult': 'VIN not found in OWL', 'source': 'OWL Coverage Info'}

    in_service_date = _field_value(frame, ['In Service Date', 'In-Service Date'])
    mileage = _field_value(frame, ['Mileage', 'In Service Mileage', 'In-Service Mileage', 'In Service Distance', 'In-Service Distance'])
    customer_name = _field_value(frame, ['Registered Customer Name', 'Customer Name', 'Registered Customer'])
    customer_account = _field_value(frame, ['Registered Customer Account', 'Customer Account', 'Customer Number'])
    warranty_status = _field_value(frame, ['Warranty Status', 'Coverage Status'])
    build_date = _field_value(frame, ['Build Date', 'Manufacture Date', 'Manufactured Date'])

    coverage_rows = core.exact_table(frame, ['Coverage'])
    if not coverage_rows:
        coverage_rows = core.exact_table(frame, ['Description'])

    return {
        'vin': vin,
        'verificationStatus': 'Verified',
        'productSerialNumber': vin,
        'buildDate': build_date,
        'inServiceStatus': 'In Service' if in_service_date else '',
        'inServiceDate': in_service_date,
        'mileage': mileage,
        'customerResult': customer_name,
        'customerName': customer_name,
        'registeredCustomerName': customer_name,
        'registeredCustomerAccount': customer_account,
        'warrantyStatus': warranty_status,
        'warrantyCoverage': '\n'.join(' | '.join(f'{k}: {v}' for k, v in row.items() if v) for row in coverage_rows),
        'coverageRecordsJson': json.dumps(coverage_rows, ensure_ascii=False),
        'coverageFieldsJson': json.dumps({
            'In Service Date': in_service_date,
            'Mileage': mileage,
            'Registered Customer Name': customer_name,
            'Registered Customer Account': customer_account,
            'Warranty Status': warranty_status,
            'Build Date': build_date,
        }, ensure_ascii=False),
        'source': 'OWL Coverage Info + Major Components',
    }


def major_lookup(context, vin: str) -> dict[str, Any]:
    # IMPORTANT: Major Components gets its own VIN entry and Tab. We do not reuse Coverage state.
    page = core.open_url(context, core.OWL_MAJOR_URL, 'Major Components')
    frame = _submit_and_wait(context, vin, 'Major Components')
    text = core.body_text(frame)
    if _is_not_found(text):
        raise RuntimeError(f'Major Components: VIN {vin} was not found.')

    chassis_sn = _field_value(frame, ['Chassis S/N'])
    vehicle_model = _field_value(frame, ['Make/Base/Model'])
    in_service_date = _field_value(frame, ['In Service Date'])
    vocation = _field_value(frame, ['Vocation'])
    unit_number = _field_value(frame, ['Unit #'])
    wheelbase = _field_value(frame, ['Wheelbase'])
    gvwr = _field_value(frame, ['GVW'])

    rows = _major_rows(frame)
    if not rows:
        raise RuntimeError(
            f'Major Components: VIN {vin} populated the page, but the Component / MFG / Model / Component S/N table was not available.'
        )

    engine_row = None
    allison_row = None
    for row in rows:
        component = core.canon(core.record_value(row, 'Component'))
        mfg = core.canon(core.record_value(row, 'MFG'))
        if engine_row is None and component == 'ENGINE':
            engine_row = row
        if allison_row is None and ('ALLISON' in component or 'TRANSMISSION' in component or 'ALLISON' in mfg):
            allison_row = row

    def row_field(row: dict[str, str] | None, header: str) -> str:
        return core.record_value(row or {}, header)

    return {
        'vehicleModel': vehicle_model,
        'inServiceDateFromMajorComponents': in_service_date,
        'chassisSerialNumber': chassis_sn or vin,
        'unitNumber': unit_number,
        'vocation': vocation,
        'wheelbase': wheelbase,
        'gvwr': gvwr,
        'engineSerialNumber': row_field(engine_row, 'Component S/N'),
        'engineModel': row_field(engine_row, 'Model'),
        'engineManufacturer': row_field(engine_row, 'MFG'),
        'allisonTransmissionSerialNumber': row_field(allison_row, 'Component S/N'),
        'transmissionModel': row_field(allison_row, 'Model'),
        'transmissionManufacturer': row_field(allison_row, 'MFG'),
        'majorComponentsText': '\n'.join(' | '.join(f'{k}: {v}' for k, v in row.items() if v) for row in rows),
        'majorComponentsJson': json.dumps(rows, ensure_ascii=False),
        'majorComponentFieldsJson': json.dumps({
            'Chassis S/N': chassis_sn,
            'Make/Base/Model': vehicle_model,
            'In Service Date': in_service_date,
            'Unit #': unit_number,
            'Vocation': vocation,
            'Wheelbase': wheelbase,
            'GVW': gvwr,
        }, ensure_ascii=False),
    }


# Patch v3's execution pipeline so its login/profile/result handling stays unchanged.
core.coverage_lookup = coverage_lookup
core.major_lookup = major_lookup


if __name__ == '__main__':
    raise SystemExit(core.main())
