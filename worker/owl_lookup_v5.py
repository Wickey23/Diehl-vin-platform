from __future__ import annotations

import json
import re
import time
from typing import Any

import owl_lookup_v4 as flow

core = flow.core

COVERAGE_LABELS = [
    'Product S/N','Go To','Make','Unit #','In Service Distance','Base Model',
    'In Service Date','Model','Cab Start Date','Order Date','Build Date','Offline Date',
    'Refurbished','Customer Name','PDI Date','Special Conditions','First Service Date',
    'PDI Submitting Location','Coverage Determination',
]


def _normalize_distance(value: str) -> tuple[str, str]:
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
    if not text:
        return ''
    labels = sorted((re.escape(x) for x in COVERAGE_LABELS), key=len, reverse=True)
    next_label = '|'.join(labels)
    pattern = rf'(?<![A-Za-z0-9]){re.escape(label)}\s*:\s*(.*?)(?=\s+(?:{next_label})\s*:|$)'
    m = re.search(pattern, text, re.I | re.S)
    return core.clean(m.group(1)) if m else ''


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
    rows = core.exact_table(frame, ['Coverages', 'Time Period', 'End Date', 'Distance', 'Unit'])
    if rows:
        return rows
    rows = core.exact_table(frame, ['Coverages', 'End Date', 'Distance'])
    return rows or []


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
        return {'vin': vin, 'verificationStatus': 'Not Found', 'customerResult': 'VIN not found in OWL', 'source': 'OWL Coverage Info'}

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
    coverage_customer_name = _coverage_value(frame, text, ['Customer Name'])
    special_conditions = _coverage_value(frame, text, ['Special Conditions'])
    pdi_submitting_location = _coverage_value(frame, text, ['PDI Submitting Location'])

    coverage_rows = _coverage_table(frame)
    coverage_names, coverage_end_dates = _coverage_names_and_dates(coverage_rows)
    in_service_status = 'In Service' if in_service_date else 'Not In Service'

    exact_fields = {
        'Product S/N': product_sn,'Make': make,'In Service Distance': in_service_distance,
        'In Service Date': in_service_date,'Cab Start Date': cab_start_date,'Build Date': build_date,
        'Refurbished': refurbished,'PDI Date': pdi_date,'First Service Date': first_service_date,
        'Go To': go_to,'Unit #': unit_number,'Base Model': base_model,'Model': model,
        'Order Date': order_date,'Offline Date': offline_date,'Customer Name': coverage_customer_name,
        'Special Conditions': special_conditions,'PDI Submitting Location': pdi_submitting_location,
    }

    core.log(
        f'OWL {vin}: Coverage verified exact mapping: status={in_service_status}; '
        f'date={in_service_date or "blank"}; mileage={mileage or "blank"}; '
        f'baseModel={base_model or "blank"}; model={model or "blank"}; coverageRows={len(coverage_rows)}'
    )

    return {
        'vin': vin,'verificationStatus': 'Verified','productSerialNumber': product_sn,
        'vehicleMake': make,'baseModel': base_model,'vehicleModel': model or base_model,
        'buildDate': build_date,'cabStartDate': cab_start_date,'pdiDate': pdi_date,
        'firstServiceDate': first_service_date,'orderDate': order_date,'offlineDate': offline_date,
        'unitNumber': unit_number,'inServiceStatus': in_service_status,'inServiceDate': in_service_date,
        'mileage': mileage,'inServiceDistance': in_service_distance,
        # Keep Coverage customer only as audit/fallback evidence. Product Registration
        # is the authoritative source for the customer fields written to Excel.
        'coverageCustomerName': coverage_customer_name,
        'refurbished': refurbished,'specialConditions': special_conditions,
        'pdiSubmittingLocation': pdi_submitting_location,'goTo': go_to,
        'freightlinerExtendedCoverageNames': coverage_names,
        'freightlinerExtendedCoverageEndDates': coverage_end_dates,
        'warrantyCoverage': '\n'.join(' | '.join(f'{k}: {v}' for k, v in row.items() if v) for row in coverage_rows),
        'coverageRecordsJson': json.dumps(coverage_rows, ensure_ascii=False),
        'coverageFieldsJson': json.dumps(exact_fields, ensure_ascii=False),
        'source': 'OWL Coverage Info + Major Components + Product Registration',
    }


def _click_product_registration(context):
    page = context.pages[0] if context.pages else context.new_page()
    for candidate in reversed(context.pages):
        if not candidate.is_closed():
            page = candidate
            break
    for frame in page.frames:
        try:
            link = frame.get_by_text('Product Registration', exact=True)
            if link.count():
                link.first.click()
                page.wait_for_load_state('domcontentloaded', timeout=30_000)
                return page
        except Exception:
            pass
    raise RuntimeError('Could not open OWL Product Registration from the left navigation.')


def _registration_has_vin(frame, vin: str) -> bool:
    text = re.sub(r'[^A-Z0-9]', '', core.body_text(frame).upper())
    return re.sub(r'[^A-Z0-9]', '', vin.upper()) in text


def _ensure_registration_vin(context, vin: str):
    page = _click_product_registration(context)
    deadline = time.time() + 12
    while time.time() < deadline:
        for _p, frame in core.iter_frames(context):
            if _registration_has_vin(frame, vin) and re.search(r'Customer', core.body_text(frame), re.I):
                return frame
        time.sleep(.08)

    # Some OWL sessions carry the current VIN into Product Registration; others
    # present a fresh main VIN input. If fresh, enter the VIN in the main content
    # only, verify it, press Tab, and wait for Customer data.
    try:
        _p, _f, field = flow._find_labeled_main_input(context, ['Product S/N', 'Chassis S/N'])
    except Exception as exc:
        raise RuntimeError(f'Product Registration did not carry VIN {vin} and no main VIN input was found: {exc}')

    field.click(); field.fill(''); field.fill(vin)
    if core.clean(field.input_value()).upper() != vin.upper():
        field.fill(''); field.type(vin, delay=8)
    if core.clean(field.input_value()).upper() != vin.upper():
        raise RuntimeError(f'Product Registration could not verify VIN {vin} before Tab.')
    field.press('Tab')
    core.log(f'OWL {vin}: Product Registration VIN verified and Tab sent.')

    deadline = time.time() + 25
    while time.time() < deadline:
        for _p, frame in core.iter_frames(context):
            if _registration_has_vin(frame, vin) and re.search(r'Customer', core.body_text(frame), re.I):
                return frame
        time.sleep(.08)
    raise RuntimeError(f'Product Registration did not populate Customer information for VIN {vin}.')


def _customer_section_fields(frame) -> dict[str, str]:
    """Collect label/value pairs only from the Product Registration Customer area."""
    try:
        return frame.evaluate("""() => {
          const norm=s=>(s||'').replace(/\s+/g,' ').trim();
          const canon=s=>norm(s).replace(/[^A-Za-z0-9/#]+/g,' ').trim().toUpperCase();
          const candidates=Array.from(document.querySelectorAll('td,th,div,span,b,font'))
            .filter(el=>/^CUSTOMER(?: INFORMATION)?$/i.test(norm(el.innerText||el.textContent)));
          if(!candidates.length) return {};
          const anchor=candidates[0];
          try{anchor.scrollIntoView({block:'center'});}catch(e){}
          const y=anchor.getBoundingClientRect().top + window.scrollY;
          const out={};
          for(const tr of document.querySelectorAll('tr')){
            const ry=tr.getBoundingClientRect().top + window.scrollY;
            if(ry < y-10 || ry > y+900) continue;
            const cells=Array.from(tr.querySelectorAll(':scope > td,:scope > th'));
            if(cells.length<2) continue;
            for(let i=0;i<cells.length-1;i++){
              const label=norm(cells[i].innerText||cells[i].textContent);
              if(!label || label.length>80) continue;
              const next=cells[i+1];
              const form=next.querySelector('input,select,textarea');
              let value='';
              if(form){
                value=form.tagName==='SELECT' ? norm(form.options[form.selectedIndex]?.text||form.value) : norm(form.value);
              } else value=norm(next.innerText||next.textContent);
              if(value && value!==label && !out[label]) out[label]=value;
            }
          }
          return out;
        }""") or {}
    except Exception:
        return {}


def _pick_customer(fields: dict[str, str], aliases: list[str]) -> str:
    wanted = {core.canon(a) for a in aliases}
    for key, value in fields.items():
        if core.canon(key) in wanted and core.clean(value):
            return core.clean(value)
    return ''


def product_registration_lookup(context, vin: str) -> dict[str, Any]:
    frame = _ensure_registration_vin(context, vin)
    fields = _customer_section_fields(frame)
    if not fields:
        raise RuntimeError(f'Product Registration Customer section could not be read for VIN {vin}.')

    registered_name = _pick_customer(fields, ['Registered Customer Name','Customer Name','Registered Customer','Name'])
    registered_account = _pick_customer(fields, ['Registered Customer Account','Customer Account','Customer Account #','Account Number','Account #','Customer #'])
    ordered_name = _pick_customer(fields, ['Ordered Customer Name','Ordered Customer'])
    ordered_account = _pick_customer(fields, ['Ordered Customer Account','Ordered Customer Account #','Ordered Account','Ordered Account #'])
    address = _pick_customer(fields, ['Registered Address','Address','Address 1','Street Address'])
    city = _pick_customer(fields, ['Registered City','City'])
    state = _pick_customer(fields, ['Registered State/Province','State/Province','State','Province'])
    postal = _pick_customer(fields, ['Registered Zip/Postal Code','Zip/Postal Code','Postal Code','Zip Code','ZIP'])
    phone = _pick_customer(fields, ['Registered Phone','Phone','Phone Number','Telephone'])
    email = _pick_customer(fields, ['Registered Email','Email','Email Address'])

    core.log(
        f'OWL {vin}: Product Registration Customer mapped: '
        f'registered={registered_name or "blank"}; account={registered_account or "blank"}; '
        f'ordered={ordered_name or "blank"}'
    )
    return {
        'customerResult': registered_name or ordered_name,
        'customerName': registered_name or ordered_name,
        'registeredCustomerName': registered_name,
        'registeredCustomerAccount': registered_account,
        'orderedCustomerName': ordered_name,
        'orderedCustomerAccount': ordered_account,
        'registeredAddress': address,
        'registeredCity': city,
        'registeredStateProvince': state,
        'registeredZipPostalCode': postal,
        'registeredPhone': phone,
        'registeredEmail': email,
        'productRegistrationFieldsJson': json.dumps(fields, ensure_ascii=False),
    }


def lookup_one(context, vin: str) -> dict[str, Any]:
    coverage = coverage_lookup(context, vin)
    if coverage.get('verificationStatus') == 'Not Found':
        return coverage
    major = flow.major_lookup(context, vin)
    registration = product_registration_lookup(context, vin)
    result = {**coverage, **major, **registration}
    if major.get('inServiceDateFromMajorComponents'):
        # Coverage remains authoritative for in-service data. Only use Major as
        # fallback if Coverage was blank.
        if not result.get('inServiceDate'):
            result['inServiceDate'] = major['inServiceDateFromMajorComponents']
            result['inServiceStatus'] = 'In Service'
    result.pop('inServiceDateFromMajorComponents', None)
    result['verificationStatus'] = 'Verified'
    result['source'] = 'OWL Coverage Info + Major Components + Product Registration'
    core.log(
        f'OWL COMPLETE {vin}: date={result.get("inServiceDate") or "blank"}; '
        f'mileage={result.get("mileage") or "blank"}; customer={result.get("customerName") or "blank"}; '
        f'engineSN={result.get("engineSerialNumber") or "blank"}; '
        f'allisonSN={result.get("allisonTransmissionSerialNumber") or "blank"}'
    )
    return result


core.coverage_lookup = coverage_lookup
core.major_lookup = flow.major_lookup
core.lookup_one = lookup_one


if __name__ == '__main__':
    raise SystemExit(core.main())
