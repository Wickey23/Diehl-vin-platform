from __future__ import annotations

import json
from typing import Any

import owl_lookup_v4 as flow

core = flow.core


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

    # Exact labels confirmed from the live OWL Coverage Information page.
    product_sn = flow._field_value(frame, ['Product S/N']) or vin
    make = flow._field_value(frame, ['Make'])
    in_service_distance = flow._field_value(frame, ['In Service Distance'])
    in_service_date = flow._field_value(frame, ['In Service Date'])
    cab_start_date = flow._field_value(frame, ['Cab Start Date'])
    build_date = flow._field_value(frame, ['Build Date'])
    refurbished = flow._field_value(frame, ['Refurbished'])
    pdi_date = flow._field_value(frame, ['PDI Date'])
    first_service_date = flow._field_value(frame, ['First Service Date'])
    go_to = flow._field_value(frame, ['Go To'])
    unit_number = flow._field_value(frame, ['Unit #'])
    base_model = flow._field_value(frame, ['Base Model'])
    model = flow._field_value(frame, ['Model'])
    order_date = flow._field_value(frame, ['Order Date'])
    offline_date = flow._field_value(frame, ['Offline Date'])
    customer_name = flow._field_value(frame, ['Customer Name'])
    special_conditions = flow._field_value(frame, ['Special Conditions'])
    pdi_submitting_location = flow._field_value(frame, ['PDI Submitting Location'])

    coverage_rows = core.exact_table(frame, ['Coverage'])
    if not coverage_rows:
        coverage_rows = core.exact_table(frame, ['Description'])

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
        f'OWL {vin}: Coverage exact fields populated: '
        f'date={in_service_date or "blank"}; distance={in_service_distance or "blank"}; '
        f'customer={customer_name or "blank"}; model={model or base_model or "blank"}'
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
        'inServiceStatus': 'In Service' if in_service_date else '',
        'inServiceDate': in_service_date,
        'mileage': in_service_distance,
        'inServiceDistance': in_service_distance,
        'customerResult': customer_name,
        'customerName': customer_name,
        'registeredCustomerName': customer_name,
        'refurbished': refurbished,
        'specialConditions': special_conditions,
        'pdiSubmittingLocation': pdi_submitting_location,
        'goTo': go_to,
        'warrantyCoverage': '\n'.join(
            ' | '.join(f'{k}: {v}' for k, v in row.items() if v)
            for row in coverage_rows
        ),
        'coverageRecordsJson': json.dumps(coverage_rows, ensure_ascii=False),
        'coverageFieldsJson': json.dumps(exact_fields, ensure_ascii=False),
        'source': 'OWL Coverage Info + Major Components',
    }


# Keep v4's corrected Major Components flow (Chassis S/N -> Tab -> populated table),
# but replace Coverage extraction with exact live-page labels.
core.coverage_lookup = coverage_lookup
core.major_lookup = flow.major_lookup


if __name__ == '__main__':
    raise SystemExit(core.main())
