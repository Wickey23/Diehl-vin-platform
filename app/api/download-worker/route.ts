import JSZip from 'jszip';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';
export const revalidate = 0;

const REPO = 'Wickey23/Diehl-vin-platform';
const PACKAGE_VERSION = '5.12';
const PACKAGE_REF = '99829ba7a519e556e9c6e109ba27430de59d6980';
const FILES = [
  'worker/START DIEHL VIN.cmd',
  'worker/STOP ALL DIEHL.cmd',
  'worker/DiehlInitializer.py',
  'worker/service_v4.py',
  'worker/service_v5.py',
  'worker/database_service.py',
  'worker/database_cache.py',
  'worker/excel_bridge.py',
  'worker/shared_workbook.py',
  'worker/workbook_organizer.py',
  'worker/vin_lookup.py',
  'worker/owl_lookup.py',
  'worker/owl_lookup_v2.py',
  'worker/owl_lookup_v3.py',
  'worker/owl_login.py',
  'worker/dtna_login_and_sync.py',
  'worker/dtna_runtime.py',
  'worker/requirements.txt',
  'worker/README_LOCAL.txt',
];

async function fetchPinned(path: string) {
  const encodedPath = path.split('/').map(encodeURIComponent).join('/');
  const url = `https://raw.githubusercontent.com/${REPO}/${PACKAGE_REF}/${encodedPath}`;
  const response = await fetch(url, {cache: 'no-store'});
  if (!response.ok) throw new Error(`Could not fetch pinned package file ${path} (${response.status})`);
  const text = await response.text();
  if (!text || text.length < 10) throw new Error(`Pinned package file ${path} is empty or incomplete.`);
  return text;
}

export async function GET() {
  try {
    const fetched = await Promise.all(FILES.map(async path => ({path, text: await fetchPinned(path)})));
    const get = (name: string) => fetched.find(x => x.path.endsWith(name))?.text || '';

    const launcher = get('START DIEHL VIN.cmd');
    const stopper = get('STOP ALL DIEHL.cmd');
    const initializer = get('DiehlInitializer.py');
    const serviceV5 = get('service_v5.py');
    const owlFast = get('owl_lookup_v3.py');
    const owlLogin = get('owl_login.py');
    const vinLookup = get('vin_lookup.py');
    const runtime = get('dtna_runtime.py');
    const database = get('database_service.py');
    const cache = get('database_cache.py');
    const excelBridge = get('excel_bridge.py');

    if (!launcher.includes('SETUP AND START v5.12') || !launcher.includes('owl_lookup_v3.py')) throw new Error('Pinned v5.12 launcher verification failed.');
    if (!stopper.includes('service_v5\\.py') || !stopper.includes('DIEHL VIN - STOP ALL RUNNING')) throw new Error('Pinned Stop All utility verification failed.');
    if (!initializer.includes("EXPECTED_WORKER_VERSION = '5.12'")) throw new Error('Pinned initializer worker-version verification failed.');
    if (!serviceV5.includes("base.VERSION = '5.12'") || !serviceV5.includes('owl_lookup_v3.py') || !serviceV5.includes('Engine Manufacturer')) throw new Error('Pinned v5.12 worker service verification failed.');
    if (!owlFast.includes('MIN_MAIN_X = 220') || !owlFast.includes("field.press('Tab')") || !owlFast.includes('main_signature')) throw new Error('Pinned fast Product S/N flow verification failed.');
    if (owlFast.includes('wait_for_timeout(1000)')) throw new Error('Pinned OWL v5.12 still contains the removed fixed one-second wait.');
    if (!owlFast.includes("exact_label_value(frame, ['In Service Date'])") || !owlFast.includes("exact_table(frame, ['Component', 'MFG', 'Model', 'Component S/N'])")) throw new Error('Pinned exact OWL field mapping verification failed.');
    if (!owlFast.includes("row_field(engine_row, 'Component S/N')") || !owlFast.includes("component == 'ENGINE'")) throw new Error('Pinned exact Major Components serial mapping verification failed.');
    if (!owlFast.includes('sig != before_signature') || !owlFast.includes('stable_since')) throw new Error('Pinned OWL result wait is not based on actual main-form data changes.');
    if (!owlLogin.includes("OWL_URL = 'https://secure.freightliner.com/iwarranty/signOn'")) throw new Error('Pinned OWL login URL verification failed.');
    if (!vinLookup.includes("OWL = ROOT / 'owl_lookup_v3.py'")) throw new Error('Pinned VIN lookup is not routed to exact OWL v3.');
    if (!runtime.includes('AUTO VIN could not be selected automatically') || !runtime.includes('Attached to already-open shared workbook')) throw new Error('Pinned DTNA runtime verification failed.');
    if (!database.includes("@app.post('/database/open-workbook')") || !database.includes('excel.Workbooks.Open') || !database.includes('workbook.Activate()')) throw new Error('Pinned Database Open Excel verification failed.');
    if (!database.includes('from database_cache import read_table') || database.includes('openpyxl')) throw new Error('Pinned Database viewer must remain lock-free.');
    if (!cache.includes("'DTNA' else 'vin-in-service.json'") || !cache.includes('Engine Manufacturer') || !cache.includes('Transmission Manufacturer')) throw new Error('Pinned Database mirror exact field verification failed.');
    if (!excelBridge.includes('collect_open_workbook') || !excelBridge.includes('GetRunningObjectTable')) throw new Error('Pinned Excel bridge verification failed.');

    const zip = new JSZip();
    const folder = zip.folder('Diehl_VIN_Local_Worker_v5_12');
    if (!folder) throw new Error('Could not create ZIP folder.');
    for (const file of fetched) folder.file(file.path.replace(/^worker\//, ''), file.text);

    folder.file('PACKAGE VERSION.txt', [
      `Diehl VIN Local Worker ${PACKAGE_VERSION}`,
      `Pinned package revision: ${PACKAGE_REF}`,
      'Expected launcher banner: DIEHL VIN - SETUP AND START v5.12',
      'VIN In-Service is faster: no fixed one-second delay after Product S/N entry.',
      'OWL waits for a real main-form DOM/value change after Tab instead of treating the VIN input itself as a result.',
      'Coverage Info uses exact labeled cells only; unknown fields stay blank rather than being guessed.',
      'Major Components uses exact Component / MFG / Model / Component S/N columns.',
      'ENGINE serial comes only from Component S/N on the ENGINE row.',
      'Allison serial comes only from Component S/N on an ALLISON/TRANSMISSION row.',
      'Exact Major Components fields include Make/Base/Model, In Service Date, Chassis S/N, Unit #, Vocation, Wheelbase and GVW.',
      'DTNA remains a separate Sales Order + Dealer Reporting AUTO VIN workflow.',
      'Shared workbook: DIEHL-VIN-PLATFORM WORKBOOK.xlsx',
      'Main worker: 127.0.0.1:8765',
      'Database + DTNA control service: 127.0.0.1:8766',
      `Generated: ${new Date().toISOString()}`,
    ].join('\r\n'));

    folder.file('READ ME FIRST.txt', [
      `DIEHL VIN LOCAL WORKER v${PACKAGE_VERSION}`,
      '',
      '1. Extract the ENTIRE ZIP to a normal folder.',
      '2. Double-click STOP ALL DIEHL.cmd to stop older Diehl services.',
      '3. Double-click START DIEHL VIN.cmd.',
      '4. The launcher banner must say v5.12.',
      '5. VIN In-Service uses only the main OWL Product S/N box and ignores Quick Search.',
      '6. VIN is verified in the box and Tab is sent immediately; no fixed one-second delay.',
      '7. The worker waits until OWL actually changes/populates main-form data before reading fields.',
      '8. Field values are accepted only from exact labels/tables. If a field is not mapped exactly it stays blank.',
      '9. ENGINE and Allison serials are read only from Major Components -> Component S/N.',
      '10. Successful results are written and verified in the VIN In-Service worksheet.',
    ].join('\r\n'));

    const body = await zip.generateAsync({type: 'arraybuffer', compression: 'DEFLATE', compressionOptions: {level: 6}});
    return new Response(body, {
      status: 200,
      headers: {
        'Content-Type': 'application/zip',
        'Content-Disposition': 'attachment; filename="Diehl_VIN_Local_Worker_v5_12.zip"',
        'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
        'Pragma': 'no-cache',
        'Expires': '0',
        'X-Diehl-Worker-Package': PACKAGE_VERSION,
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Could not build local worker ZIP.';
    return Response.json({error: message}, {status: 500, headers: {'Cache-Control': 'no-store'}});
  }
}
