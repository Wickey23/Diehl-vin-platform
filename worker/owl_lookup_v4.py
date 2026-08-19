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


def _find_labeled_main_input(context, labels: list[str], timeout: float = 15.0):
    wanted = [core.canon(x) for x in labels]
    deadline = time.time() + timeout
    while time.time() < deadline:
        for page, frame in core.iter_frames(context):
            try:
                temp_id = frame.evaluate("""({wanted,minX}) => {
                  const canon=s=>(s||'').replace(/[^A-Za-z0-9]+/g,' ').trim().toUpperCase();
                  const usable=input=>{
                    if(!input || input.disabled) return false;
                    if((input.getAttribute('type')||'text').toLowerCase()!=='text') return false;
                    const r=input.getBoundingClientRect();
                    if(!r.width || !r.height || r.left<minX) return false;
                    let n=input;
                    while(n&&n!==document.body){
                      const sig=((n.id||'')+' '+(n.className||'')+' '+(n.getAttribute?.('name')||'')).toLowerCase();
                      if(/quick.?search|left.?nav|left.?menu|side.?nav|sidebar/.test(sig)) return false;
                      n=n.parentElement;
                    }
                    return true;
                  };
                  const found=[];
                  for(const cell of document.querySelectorAll('td,th,label,span,b,font')){
                    const label=canon(cell.innerText||cell.textContent);
                    if(!wanted.includes(label)) continue;
                    const td=cell.closest('td,th');
                    const row=cell.closest('tr');
                    if(td?.nextElementSibling){
                      for(const input of td.nextElementSibling.querySelectorAll('input')) if(usable(input)) found.push({input,score:300});
                    }
                    if(row){
                      for(const input of row.querySelectorAll('input')) if(usable(input)) found.push({input,score:200});
                    }
                  }
                  if(!found.length) return '';
                  found.sort((a,b)=>b.score-a.score);
                  const input=found[0].input;
                  if(!input.id) input.id='diehl-main-vin-'+Math.random().toString(36).slice(2);
                  return input.id;
                }""", {'wanted': wanted, 'minX': core.MIN_MAIN_X})
            except Exception:
                temp_id = ''
            if not temp_id:
                continue
            loc = frame.locator('#' + temp_id)
            if not loc.count():
                continue
            field = loc.first
            try:
                box = field.bounding_box()
                if box and box['x'] >= core.MIN_MAIN_X:
                    return page, frame, field
            except Exception:
                continue
        time.sleep(.08)
    raise RuntimeError(f"Could not find main OWL input labeled {' / '.join(labels)}. Left Quick Search is intentionally ignored.")


def _coverage_ready(frame) -> bool:
    values = [
        _field_value(frame, ['In Service Date', 'In-Service Date']),
        _field_value(frame, ['Mileage', 'In Service Mileage', 'In-Service Mileage', 'In Service Distance', 'In-Service Distance']),
        _field_value(frame, ['Registered Customer Name', 'Customer Name', 'Registered Customer']),
        _field_value(frame, ['Warranty Status', 'Coverage Status']),
        _field_value(frame, ['Build Date', 'Manufacture Date', 'Manufactured Date']),
    ]
    return any(core.clean(v) for v in values) or bool(core.exact_table(frame, ['Coverage'])) or bool(core.exact_table(frame, ['Description']))


def _major_ready(frame, vin: str) -> bool:
    chassis = core.clean(_field_value(frame, ['Chassis S/N'])).upper()
    normalized_chassis = re.sub(r'[^A-Z0-9]', '', chassis)
    normalized_vin = re.sub(r'[^A-Z0-9]', '', vin.upper())
    if not chassis or normalized_chassis != normalized_vin:
        return False
    model = core.clean(_field_value(frame, ['Make/Base/Model']))
    in_service = core.clean(_field_value(frame, ['In Service Date']))
    rows = _major_rows(frame)
    return bool(rows or model or in_service)


def _submit_and_wait(context, vin: str, page_kind: str, timeout: float = 25.0):
    if page_kind == 'Major Components':
        page, frame, field = _find_labeled_main_input(context, ['Chassis S/N'])
        label_name = 'Chassis S/N'
    else:
        page, frame, field = _find_labeled_main_input(context, ['Product S/N'])
        label_name = 'Product S/N'

    if 'quicksearch' in (page.url or '').lower():
        raise RuntimeError(f'{page_kind}: OWL is on Quick Search; refusing to enter VIN there.')

    box = field.bounding_box()
    if not box or box['x'] < core.MIN_MAIN_X:
        raise RuntimeError(f'{page_kind}: {label_name} candidate is inside the left sidebar.')

    field.click()
    field.fill('')
    field.fill(vin)
    actual = core.clean(field.input_value()).upper()
    if actual != vin:
        field.fill('')
        field.type(vin, delay=8)
        actual = core.clean(field.input_value()).upper()
    if actual != vin:
        raise RuntimeError(f'{page_kind}: {label_name} did not contain the complete VIN {vin}.')

    if core.clean(field.input_value()).upper() != vin:
        raise RuntimeError(f'{page_kind}: {label_name} changed before Tab; refusing stale lookup.')

    core.log(f'OWL {vin}: {page_kind} {label_name} verified at x={round(box["x"])}; pressing Tab now.')
    field.press('Tab')

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

            ready = _major_ready(candidate_frame, vin) if page_kind == 'Major Components' else _coverage_ready(candidate_frame)
            if not ready:
                continue

            signature = core.main_signature(candidate_frame, vin)
            if signature and signature == last_signature:
                stable_hits += 1
            else:
                last_signature = signature
                stable_hits = 1

            if stable_hits >= 2:
                core.log(f'OWL {vin}: {page_kind} information populated and stable; extracting now.')
                return candidate_frame

        time.sleep(.08)

    if page_kind == 'Major Components':
        raise RuntimeError(f'Major Components: VIN {vin} was entered into Chassis S/N and Tab was pressed, but vehicle/component information never populated.')
    raise RuntimeError(f'Coverage Info: VIN {vin} was entered into Product S/N and Tab was pressed, but OWL information never populated.')


def coverage_lookup(context, vin: str) -> dict[str, Any]:
    core.open_url(context, core.OWL_COVERAGE_URL, 'Coverage Info')
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
    core.open_url(context, core.OWL_MAJOR_URL, 'Major Components')
    frame = _submit_and_wait(context, vin, 'Major Components')
    text = core.body_text(frame)
    if _is_not_found(text):
        raise RuntimeError(f'Major Components: VIN {vin} was not found.')

    chassis_sn = _field_value(frame, ['Chassis S/N'])
    normalized_chassis = re.sub(r'[^A-Z0-9]', '', core.clean(chassis_sn).upper())
    normalized_vin = re.sub(r'[^A-Z0-9]', '', vin.upper())
    if normalized_chassis != normalized_vin:
        raise RuntimeError(f'Major Components returned Chassis S/N {chassis_sn or "[blank]"}, not requested VIN {vin}.')

    vehicle_model = _field_value(frame, ['Make/Base/Model'])
    in_service_date = _field_value(frame, ['In Service Date'])
    vocation = _field_value(frame, ['Vocation'])
    unit_number = _field_value(frame, ['Unit #'])
    wheelbase = _field_value(frame, ['Wheelbase'])
    gvwr = _field_value(frame, ['GVW'])

    rows = _major_rows(frame)
    if not rows:
        raise RuntimeError(f'Major Components: VIN {vin} populated the vehicle header, but the Component / MFG / Model / Component S/N table did not populate.')

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
        'chassisSerialNumber': chassis_sn,
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


core.coverage_lookup = coverage_lookup
core.major_lookup = major_lookup


if __name__ == '__main__':
    raise SystemExit(core.main())
