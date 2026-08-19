import JSZip from 'jszip';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';
export const revalidate = 0;

const REPO = 'Wickey23/Diehl-vin-platform';
const PACKAGE_VERSION = '5.11';
const PACKAGE_REF = '030301c59c75581a23c1e00b7a770afc0a6a1364';
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
    const owlStrict = get('owl_lookup_v2.py');
    const owlLogin = get('owl_login.py');
    const vinLookup = get('vin_lookup.py');
    const runtime = get('dtna_runtime.py');
    const database = get('database_service.py');
    const cache = get('database_cache.py');
    const excelBridge = get('excel_bridge.py');

    if (!launcher.includes('SETUP AND START v5.11') || !launcher.includes('owl_lookup_v2.py')) throw new Error('Pinned v5.11 launcher verification failed.');
    if (!stopper.includes('service_v5\\.py') || !stopper.includes('DIEHL VIN - STOP ALL RUNNING')) throw new Error('Pinned Stop All utility verification failed.');
    if (!initializer.includes("EXPECTED_WORKER_VERSION = '5.11'")) throw new Error('Pinned initializer worker-version verification failed.');
    if (!serviceV5.includes("base.VERSION = '5.11'") || !serviceV5.includes('owl_lookup_v2.py')) throw new Error('Pinned v5.11 worker service verification failed.');
    if (!owlStrict.includes('MIN_MAIN_X = 220') || !owlStrict.includes('left Quick Search input is intentionally ignored') || !owlStrict.includes('Confirmed MAIN Product S/N field')) throw new Error('Pinned strict OWL main Product S/N locator verification failed.');
    if (!owlStrict.includes('bounding_box()') || !owlStrict.includes("field.press('Tab')") || !owlStrict.includes('page.wait_for_timeout(1000)')) throw new Error('Pinned strict Product S/N timing/position checks failed.');
    if (!owlStrict.includes('coverageRecordsJson') || !owlStrict.includes('majorComponentsJson')) throw new Error('Pinned structured OWL extraction verification failed.');
    if (!owlLogin.includes("OWL_URL = 'https://secure.freightliner.com/iwarranty/signOn'")) throw new Error('Pinned OWL login URL verification failed.');
    if (!vinLookup.includes("OWL = ROOT / 'owl_lookup_v2.py'")) throw new Error('Pinned VIN lookup is not routed to strict OWL v2.');
    if (!runtime.includes('AUTO VIN could not be selected automatically') || !runtime.includes('Attached to already-open shared workbook')) throw new Error('Pinned DTNA runtime verification failed.');
    if (!database.includes("@app.post('/database/open-workbook')") || !database.includes('excel.Workbooks.Open') || !database.includes('workbook.Activate()')) throw new Error('Pinned Database Open Excel verification failed.');
    if (!database.includes('from database_cache import read_table') || database.includes('openpyxl')) throw new Error('Pinned Database viewer must remain lock-free.');
    if (!cache.includes("'DTNA' else 'vin-in-service.json'") || !cache.includes('Coverage Records JSON') || !cache.includes('Major Components JSON')) throw new Error('Pinned Database mirror verification failed.');
    if (!excelBridge.includes('collect_open_workbook') || !excelBridge.includes('GetRunningObjectTable')) throw new Error('Pinned Excel bridge verification failed.');

    const zip = new JSZip();
    const folder = zip.folder('Diehl_VIN_Local_Worker_v5_11');
    if (!folder) throw new Error('Could not create ZIP folder.');
    for (const file of fetched) folder.file(file.path.replace(/^worker\//, ''), file.text);

    folder.file('PACKAGE VERSION.txt', [
      `Diehl VIN Local Worker ${PACKAGE_VERSION}`,
      `Pinned package revision: ${PACKAGE_REF}`,
      'Expected launcher banner: DIEHL VIN - SETUP AND START v5.11',
      'VIN In-Service now refuses the left OWL Quick Search box completely.',
      'Only a Product S/N input in the main content area at x >= 220 is accepted.',
      'The VIN is typed, verified, held for one second, verified again, then Tab is pressed.',
      'Coverage Info and Major Components must each confirm the submitted VIN before results are accepted.',
      'Structured warranty/component audit data is retained in Excel.',
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
      '4. The launcher banner must say v5.11.',
      '5. VIN In-Service opens OWL and ignores the left Quick Search field.',
      '6. Only the main Product S/N box is allowed. The worker checks its screen position before typing.',
      '7. VIN is typed -> verified -> wait 1 second -> verified again -> Tab.',
      '8. Coverage Info and Major Components must both confirm the requested VIN.',
      '9. Successful results are written and verified in the VIN In-Service worksheet.',
    ].join('\r\n'));

    const body = await zip.generateAsync({type: 'arraybuffer', compression: 'DEFLATE', compressionOptions: {level: 6}});
    return new Response(body, {
      status: 200,
      headers: {
        'Content-Type': 'application/zip',
        'Content-Disposition': 'attachment; filename="Diehl_VIN_Local_Worker_v5_11.zip"',
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
