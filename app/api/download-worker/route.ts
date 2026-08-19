import JSZip from 'jszip';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';
export const revalidate = 0;

const REPO = 'Wickey23/Diehl-vin-platform';
const PACKAGE_VERSION = '5.10';
const PACKAGE_REF = '6f9e3626e6d5b5cb481fb3fb7ae716a74c09bb0e';
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
    const owl = get('owl_lookup.py');
    const owlLogin = get('owl_login.py');
    const vinLookup = get('vin_lookup.py');
    const runtime = get('dtna_runtime.py');
    const database = get('database_service.py');
    const cache = get('database_cache.py');
    const excelBridge = get('excel_bridge.py');

    if (!launcher.includes('SETUP AND START v5.10') || !launcher.includes('database_cache.py') || !launcher.includes('excel_bridge.py')) throw new Error('Pinned v5.10 launcher verification failed.');
    if (!stopper.includes('service_v5\\.py') || !stopper.includes('DIEHL VIN - STOP ALL RUNNING')) throw new Error('Pinned Stop All utility verification failed.');
    if (!initializer.includes("'vinInServiceSource': 'OWL'")) throw new Error('Pinned initializer verification failed.');
    if (!serviceV5.includes("base.VERSION = '5.10'") || !serviceV5.includes('Coverage Records JSON') || !serviceV5.includes('Major Components JSON') || !serviceV5.includes('Vehicle Model')) throw new Error('Pinned complete OWL persistence verification failed.');
    if (!owl.includes("OWL_SIGNON_URL = 'https://secure.freightliner.com/iwarranty/signOn'") || !owl.includes('WarrantyDetailsGoToServlet?FromInd=Home') || !owl.includes('ProductMaintenanceServlet?ActionType=AddNewSideNav&FromInd=SideNav')) throw new Error('Pinned exact OWL URLs verification failed.');
    if (!owl.includes('page_confirms_vin') || !owl.includes('coverageRecordsJson') || !owl.includes('majorComponentsJson') || !owl.includes('Product S/N verified; waiting 1 full second before Tab.')) throw new Error('Pinned VIN-verified structured OWL extraction failed.');
    if (!owlLogin.includes("OWL_URL = 'https://secure.freightliner.com/iwarranty/signOn'")) throw new Error('Pinned OWL login URL verification failed.');
    if (!vinLookup.includes("OWL = ROOT / 'owl_lookup.py'")) throw new Error('Pinned VIN lookup is not routed to OWL.');
    if (!runtime.includes('AUTO VIN could not be selected automatically') || !runtime.includes('Attached to already-open shared workbook')) throw new Error('Pinned DTNA runtime verification failed.');
    if (!database.includes("@app.post('/database/open-workbook')") || !database.includes('excel.Workbooks.Open') || !database.includes('workbook.Activate()')) throw new Error('Pinned Database Open Excel verification failed.');
    if (!database.includes('from database_cache import read_table') || database.includes('openpyxl')) throw new Error('Pinned Database viewer must remain lock-free.');
    if (!cache.includes("'DTNA' else 'vin-in-service.json'") || !cache.includes('Coverage Records JSON') || !cache.includes('Major Components JSON')) throw new Error('Pinned Database mirror verification failed.');
    if (!excelBridge.includes('collect_open_workbook') || !excelBridge.includes('GetRunningObjectTable')) throw new Error('Pinned Excel bridge verification failed.');

    const zip = new JSZip();
    const folder = zip.folder('Diehl_VIN_Local_Worker_v5_10');
    if (!folder) throw new Error('Could not create ZIP folder.');
    for (const file of fetched) folder.file(file.path.replace(/^worker\//, ''), file.text);

    folder.file('PACKAGE VERSION.txt', [
      `Diehl VIN Local Worker ${PACKAGE_VERSION}`,
      `Pinned package revision: ${PACKAGE_REF}`,
      'Expected launcher banner: DIEHL VIN - SETUP AND START v5.10',
      'VIN In-Service validates the submitted VIN on BOTH OWL Coverage Info and Major Components before completion.',
      'Coverage extraction: in-service status/date, mileage, customer/account, vehicle/model/build data and structured warranty rows.',
      'Major Components extraction: engine serial/model, Allison transmission serial/model and structured component rows.',
      'Raw structured OWL records are retained in hidden Excel audit columns.',
      'DTNA remains a separate Sales Order + Dealer Reporting AUTO VIN workflow.',
      'Shared workbook: DIEHL-VIN-PLATFORM WORKBOOK.xlsx',
      'Workbook sheets: VIN In-Service and DTNA',
      'Database viewer: lock-free verified local mirror with isolated sheet caches',
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
      '4. The launcher banner must say v5.10.',
      '5. VIN In-Service opens OWL at secure.freightliner.com/iwarranty/signOn.',
      '6. The worker fills Product S/N, verifies the value, waits one second, then presses Tab.',
      '7. The returned VIN must match before Coverage Info is accepted.',
      '8. Major Components is opened separately and must also match the same VIN.',
      '9. Successful results include normalized in-service, warranty, customer, engine and Allison fields plus structured audit data.',
      '10. Results are written and verified in the VIN In-Service worksheet before the batch item is complete.',
      '11. DTNA is a separate workflow writing only the DTNA worksheet.',
      '12. Database DTNA and VIN In-Service tabs remain isolated.',
    ].join('\r\n'));

    const body = await zip.generateAsync({type: 'arraybuffer', compression: 'DEFLATE', compressionOptions: {level: 6}});
    return new Response(body, {
      status: 200,
      headers: {
        'Content-Type': 'application/zip',
        'Content-Disposition': 'attachment; filename="Diehl_VIN_Local_Worker_v5_10.zip"',
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
