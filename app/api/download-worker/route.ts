import JSZip from 'jszip';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';
export const revalidate = 0;

const REPO = 'Wickey23/Diehl-vin-platform';
const PACKAGE_VERSION = '5.5';
const PACKAGE_REF = '9a1a787e1f18921f599f1497e9625874f4dae470';
const FILES = [
  'worker/START DIEHL VIN.cmd',
  'worker/STOP ALL DIEHL.cmd',
  'worker/DiehlInitializer.py',
  'worker/service_v4.py',
  'worker/service_v5.py',
  'worker/database_service.py',
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

    const launcher = fetched.find(x => x.path.endsWith('START DIEHL VIN.cmd'))?.text || '';
    const stopper = fetched.find(x => x.path.endsWith('STOP ALL DIEHL.cmd'))?.text || '';
    const initializer = fetched.find(x => x.path.endsWith('DiehlInitializer.py'))?.text || '';
    const serviceV5 = fetched.find(x => x.path.endsWith('service_v5.py'))?.text || '';
    const owl = fetched.find(x => x.path.endsWith('owl_lookup.py'))?.text || '';
    const owlLogin = fetched.find(x => x.path.endsWith('owl_login.py'))?.text || '';
    const vinLookup = fetched.find(x => x.path.endsWith('vin_lookup.py'))?.text || '';
    const runtime = fetched.find(x => x.path.endsWith('dtna_runtime.py'))?.text || '';
    const database = fetched.find(x => x.path.endsWith('database_service.py'))?.text || '';

    if (!launcher.includes('SETUP AND START v5.5') || !launcher.includes('owl_login.py')) throw new Error('Pinned v5.5 launcher verification failed.');
    if (!stopper.includes('DIEHL VIN - STOP ALL RUNNING')) throw new Error('Pinned Stop All utility verification failed.');
    if (!initializer.includes("EXPECTED_WORKER_VERSION = '5.5'") || !initializer.includes("'vinInServiceSource': 'OWL'")) throw new Error('Pinned v5.5 initializer verification failed.');
    if (!serviceV5.includes("base.VERSION = '5.5'") || !serviceV5.includes('/owl/open') || !serviceV5.includes('force_live_owl_lookup')) throw new Error('Pinned OWL worker service verification failed.');
    if (!owl.includes('OWL VIN search did not become ready') || !owl.includes("'source': 'OWL'")) throw new Error('Pinned OWL browser automation verification failed.');
    if (!owlLogin.includes('OWL login/browser opened for this Windows user.')) throw new Error('Pinned OWL login launcher verification failed.');
    if (!vinLookup.includes("OWL = ROOT / 'owl_lookup.py'")) throw new Error('Pinned VIN lookup is not routed to OWL.');
    if (!runtime.includes('AUTO VIN could not be selected automatically') || !runtime.includes('Attached to already-open shared workbook')) throw new Error('Pinned DTNA runtime verification failed.');
    if (!database.includes('/control/stop-all') || !database.includes('/dtna/sync') || database.includes('from openpyxl import load_workbook')) throw new Error('Pinned database control verification failed.');

    const zip = new JSZip();
    const folder = zip.folder('Diehl_VIN_Local_Worker_v5_5');
    if (!folder) throw new Error('Could not create ZIP folder.');
    for (const file of fetched) folder.file(file.path.replace(/^worker\//, ''), file.text);

    folder.file('PACKAGE VERSION.txt', [
      `Diehl VIN Local Worker ${PACKAGE_VERSION}`,
      `Pinned package revision: ${PACKAGE_REF}`,
      'Expected launcher banner: DIEHL VIN - SETUP AND START v5.5',
      'VIN In-Service source: OWL (live lookup for every submitted VIN)',
      'DTNA source: Sales Order + Dealer Reporting AUTO VIN',
      'Shared workbook: DIEHL-VIN-PLATFORM WORKBOOK.xlsx',
      'Workbook sheets: VIN In-Service and DTNA',
      'Main worker: 127.0.0.1:8765',
      'Database + DTNA control service: 127.0.0.1:8766',
      'Successful OWL results are written and verified in VIN In-Service before completion.',
      `Generated: ${new Date().toISOString()}`,
    ].join('\r\n'));

    folder.file('READ ME FIRST.txt', [
      `DIEHL VIN LOCAL WORKER v${PACKAGE_VERSION}`,
      '',
      '1. Extract the ENTIRE ZIP to a normal folder.',
      '2. Double-click STOP ALL DIEHL.cmd to stop an older Diehl worker.',
      '3. Double-click START DIEHL VIN.cmd.',
      '4. The banner must say DIEHL VIN - SETUP AND START v5.5.',
      '5. VIN In-Service performs live OWL lookups. It does NOT use the DTNA Sales Order cache as a substitute.',
      '6. Use Open OWL / Login on VIN In-Service to initialize your own OWL/DTNA session and MFA.',
      '7. Each submitted VIN is refreshed in OWL even if it already exists in Excel.',
      '8. Each successful OWL result is written to the shared VIN In-Service worksheet and verified before completion.',
      '9. DTNA remains the separate Sales Order + AUTO VIN workflow and writes the DTNA worksheet.',
      '10. The Database tab is read-only and reflects the shared workbook.',
    ].join('\r\n'));

    const body = await zip.generateAsync({type: 'arraybuffer', compression: 'DEFLATE', compressionOptions: {level: 6}});
    return new Response(body, {
      status: 200,
      headers: {
        'Content-Type': 'application/zip',
        'Content-Disposition': 'attachment; filename="Diehl_VIN_Local_Worker_v5_5.zip"',
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
