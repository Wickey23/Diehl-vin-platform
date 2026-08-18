import JSZip from 'jszip';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';
export const revalidate = 0;

const REPO = 'Wickey23/Diehl-vin-platform';
const PACKAGE_VERSION = '5.4';
const PACKAGE_REF = '80ce5c386cb2889a13fd49f042850c87221ef6d8';
const FILES = [
  'worker/START DIEHL VIN.cmd',
  'worker/STOP ALL DIEHL.cmd',
  'worker/DiehlInitializer.py',
  'worker/service_v4.py',
  'worker/database_service.py',
  'worker/shared_workbook.py',
  'worker/workbook_organizer.py',
  'worker/vin_lookup.py',
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
    const runtime = fetched.find(x => x.path.endsWith('dtna_runtime.py'))?.text || '';
    const vinLookup = fetched.find(x => x.path.endsWith('vin_lookup.py'))?.text || '';
    const database = fetched.find(x => x.path.endsWith('database_service.py'))?.text || '';

    if (!launcher.includes('SETUP AND START v5.4')) throw new Error('Pinned v5.4 launcher verification failed.');
    if (!stopper.includes('DIEHL VIN - STOP ALL RUNNING')) throw new Error('Pinned Stop All utility verification failed.');
    if (!initializer.includes('Database viewer connected on 127.0.0.1:8766')) throw new Error('Pinned initializer verification failed.');
    if (!runtime.includes('AUTO VIN could not be selected automatically') || !runtime.includes("base.PAYLOAD['orderToReview'] = True") || !runtime.includes('Attached to already-open shared workbook')) {
      throw new Error('Pinned DTNA runtime verification failed.');
    }
    if (!vinLookup.includes("SYNC=ROOT/'dtna_runtime.py'")) throw new Error('Pinned VIN lookup runtime verification failed.');
    if (!database.includes("version='1.3'") || !database.includes('/control/stop-all') || !database.includes('/dtna/sync') || !database.includes('DTNA_RUNTIME') || database.includes('from openpyxl import load_workbook')) {
      throw new Error('Pinned unified DTNA/database control verification failed.');
    }

    const zip = new JSZip();
    const folder = zip.folder('Diehl_VIN_Local_Worker_v5_4');
    if (!folder) throw new Error('Could not create ZIP folder.');

    for (const file of fetched) folder.file(file.path.replace(/^worker\//, ''), file.text);

    folder.file('PACKAGE VERSION.txt', [
      `Diehl VIN Local Worker ${PACKAGE_VERSION}`,
      `Pinned package revision: ${PACKAGE_REF}`,
      'Expected launcher banner: DIEHL VIN - SETUP AND START v5.4',
      'Permanent runtime: %LocalAppData%\\DiehlVINWorker\\v4',
      'Python runtime: 3.12',
      'Shared workbook: DIEHL-VIN-PLATFORM WORKBOOK.xlsx',
      'Workbook sheets: VIN In-Service and DTNA',
      'Main worker: 127.0.0.1:8765',
      'Database + DTNA control service: 127.0.0.1:8766',
      'All website DTNA launches route through dtna_runtime.py.',
      'STOP ALL DIEHL.cmd safely stops only verified Diehl local services.',
      'Database viewer reads through Excel COM only and never opens the xlsx directly with openpyxl.',
      'DTNA Excel writer attaches to an already-open shared workbook and retries OneDrive locks.',
      'VIN In-Service refresh uses the same fixed DTNA runtime.',
      'Successful VIN results are written and verified in the shared Excel database.',
      `Generated: ${new Date().toISOString()}`,
    ].join('\r\n'));

    folder.file('READ ME FIRST.txt', [
      `DIEHL VIN LOCAL WORKER v${PACKAGE_VERSION}`,
      '',
      '1. Extract the ENTIRE ZIP to a normal folder.',
      '2. Double-click STOP ALL DIEHL.cmd to stop an older Diehl worker if one is running.',
      '3. Double-click START DIEHL VIN.cmd.',
      '4. The banner must say DIEHL VIN - SETUP AND START v5.4.',
      '5. START copies the included audited files into LocalAppData\\DiehlVINWorker\\v4.',
      '6. The worker uses the shared DIEHL-VIN-PLATFORM WORKBOOK.xlsx database.',
      '7. You may leave the shared workbook open in Excel. Database reads and DTNA writes attach through Excel.',
      '8. Initialize YOUR DTNA login from the site and complete your own MFA.',
      '9. DTNA Sync and VIN In-Service both use the same fixed dtna_runtime.py path.',
      '10. The website Database tab reads DTNA and VIN In-Service through the local Excel COM service.',
      '',
      'Successful VIN results are not marked complete until the Excel database write succeeds.',
    ].join('\r\n'));

    const body = await zip.generateAsync({type: 'arraybuffer', compression: 'DEFLATE', compressionOptions: {level: 6}});
    return new Response(body, {
      status: 200,
      headers: {
        'Content-Type': 'application/zip',
        'Content-Disposition': 'attachment; filename="Diehl_VIN_Local_Worker_v5_4.zip"',
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
