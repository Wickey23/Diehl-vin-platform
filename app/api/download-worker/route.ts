import JSZip from 'jszip';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';
export const revalidate = 0;

const REPO = 'Wickey23/Diehl-vin-platform';
const PACKAGE_VERSION = '5.16';
const PACKAGE_REF = '13eaa75ce1c6c9535908addbb6da129ecb3cf2c8';
const FILES = [
  'worker/START DIEHL VIN.cmd',
  'worker/STOP ALL DIEHL.cmd',
  'worker/DiehlInitializer.py',
  'worker/DiehlInitializer_v514.py',
  'worker/service_v4.py',
  'worker/service_v5.py',
  'worker/service_v7.py',
  'worker/database_service.py',
  'worker/database_cache.py',
  'worker/excel_bridge.py',
  'worker/shared_workbook.py',
  'worker/workbook_organizer.py',
  'worker/vin_lookup.py',
  'worker/owl_lookup.py',
  'worker/owl_lookup_v2.py',
  'worker/owl_lookup_v3.py',
  'worker/owl_lookup_v4.py',
  'worker/owl_lookup_v5.py',
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
    const initializer = get('DiehlInitializer_v514.py');
    const serviceV7 = get('service_v7.py');
    const owlConfirmed = get('owl_lookup_v4.py');
    const owlExact = get('owl_lookup_v5.py');
    const owlLogin = get('owl_login.py');
    const vinLookup = get('vin_lookup.py');
    const runtime = get('dtna_runtime.py');
    const database = get('database_service.py');
    const cache = get('database_cache.py');
    const excelBridge = get('excel_bridge.py');

    if (!launcher.includes('SETUP AND START v5.16') || !launcher.includes('service_v7.py')) throw new Error('Pinned v5.16 launcher verification failed.');
    if (!launcher.includes('launches the new VIN batch immediately')) throw new Error('Pinned launcher does not document immediate OWL execution.');
    if (!stopper.includes('service_v5\\.py') || !stopper.includes('DIEHL VIN - STOP ALL RUNNING')) throw new Error('Pinned Stop All utility verification failed.');
    if (!initializer.includes("EXPECTED_WORKER_VERSION = '5.16'") || !initializer.includes('base.webbrowser.open = lambda')) throw new Error('Pinned v5.16 initializer verification failed.');
    if (!serviceV7.includes("service.base.VERSION = '5.16'")) throw new Error('Pinned v5.16 service version verification failed.');
    if (!serviceV7.includes('_process_batch_now') || !serviceV7.includes("status='direct_running'") || !serviceV7.includes('threading.Thread')) throw new Error('Pinned v5.16 immediate batch execution verification failed.');
    if (!serviceV7.includes('DIRECT START') || !serviceV7.includes('Launch') && !serviceV7.includes('Launching OWL now')) throw new Error('Pinned v5.16 OWL launch logging verification failed.');
    if (!owlConfirmed.includes("['Chassis S/N']") || !owlConfirmed.includes("component == 'MAIN TRANSMISSION'")) throw new Error('Pinned exact Major Components mapping verification failed.');
    if (!owlConfirmed.includes("component == 'ENGINE'") || !owlConfirmed.includes("'ALI', 'ALLISON'")) throw new Error('Pinned Cummins/Allison row mapping verification failed.');
    if (!owlExact.includes("['In Service Distance']") || !owlExact.includes('product_registration_lookup')) throw new Error('Pinned Coverage/Product Registration mapping verification failed.');
    if (!owlExact.includes('Registered Customer Name') || !owlExact.includes('Ordered Customer Account')) throw new Error('Pinned customer data mapping verification failed.');
    if (!owlLogin.includes("OWL_URL = 'https://secure.freightliner.com/iwarranty/signOn'")) throw new Error('Pinned OWL login URL verification failed.');
    if (!vinLookup.includes("OWL = ROOT / 'owl_lookup_v5.py'")) throw new Error('Pinned VIN lookup is not routed to exact OWL flow.');
    if (!runtime.includes('AUTO VIN could not be selected automatically') || !runtime.includes('Attached to already-open shared workbook')) throw new Error('Pinned DTNA runtime verification failed.');
    if (!database.includes("@app.post('/database/open-workbook')") || !database.includes('workbook.Activate()')) throw new Error('Pinned Database Open Excel verification failed.');
    if (!database.includes('from database_cache import read_table') || database.includes('openpyxl')) throw new Error('Pinned Database viewer must remain lock-free.');
    if (!cache.includes("'DTNA' else 'vin-in-service.json'")) throw new Error('Pinned Database mirror isolation verification failed.');
    if (!excelBridge.includes('collect_open_workbook') || !excelBridge.includes('GetRunningObjectTable')) throw new Error('Pinned Excel bridge verification failed.');

    const zip = new JSZip();
    const folder = zip.folder('Diehl_VIN_Local_Worker_v5_16');
    if (!folder) throw new Error('Could not create ZIP folder.');
    for (const file of fetched) folder.file(file.path.replace(/^worker\//, ''), file.text);

    folder.file('PACKAGE VERSION.txt', [
      `Diehl VIN Local Worker ${PACKAGE_VERSION}`,
      `Pinned package revision: ${PACKAGE_REF}`,
      'Start OWL Check now starts the submitted VIN batch immediately in a dedicated local thread instead of waiting for the legacy scheduler.',
      'The VIN item is marked running immediately and the live OWL subprocess is started for that exact batch.',
      'Abandoned older queued/running batches are cancelled automatically.',
      'Coverage Info is authoritative for in-service date, in-service distance/mileage, model/build dates, and warranty/extended coverage.',
      'Major Components uses Chassis S/N and exact ENGINE / MAIN TRANSMISSION rows for Cummins and Allison serials.',
      'Product Registration is authoritative for registered/ordered customer account, name, address, city, state, ZIP, phone, and email.',
      'Worker startup does not open another Diehl VIN Platform website tab.',
      'Left Quick Search remains forbidden.',
      'DTNA remains a separate Sales Order + Dealer Reporting AUTO VIN workflow.',
      'Shared workbook: DIEHL-VIN-PLATFORM WORKBOOK.xlsx',
      `Generated: ${new Date().toISOString()}`,
    ].join('\r\n'));

    folder.file('READ ME FIRST.txt', [
      `DIEHL VIN LOCAL WORKER v${PACKAGE_VERSION}`,
      '',
      '1. Extract the ENTIRE ZIP to a normal folder.',
      '2. Double-click STOP ALL DIEHL.cmd.',
      '3. Double-click START DIEHL VIN.cmd.',
      '4. The launcher banner must say v5.16.',
      '5. Keep the Diehl VIN Platform website tab already open.',
      '6. Press Start OWL Check. The VIN should move to running immediately and OWL should launch.',
      '7. Coverage Info -> Product S/N -> VIN -> Tab -> wait for populated data.',
      '8. Major Components -> Chassis S/N -> VIN -> Tab -> exact ENGINE / MAIN TRANSMISSION rows.',
      '9. Product Registration -> Customer section -> registered/ordered customer details.',
      '10. Successful results are written and verified in the VIN In-Service worksheet.',
    ].join('\r\n'));

    const body = await zip.generateAsync({type: 'arraybuffer', compression: 'DEFLATE', compressionOptions: {level: 6}});
    return new Response(body, {
      status: 200,
      headers: {
        'Content-Type': 'application/zip',
        'Content-Disposition': 'attachment; filename="Diehl_VIN_Local_Worker_v5_16.zip"',
        'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
        'Pragma': 'no-cache',
        'Expires': '0',
        'X-Diehl-Worker-Package': PACKAGE_VERSION,
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Could not build local worker ZIP.';
    return Response.json({error: message}, {status: 500, headers: {'Cache-Control':'no-store'}});
  }
}
