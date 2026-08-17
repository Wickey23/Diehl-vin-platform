import JSZip from 'jszip';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';
export const revalidate = 0;

const REPO = 'Wickey23/Diehl-vin-platform';
const PACKAGE_VERSION = '4.8';
const PACKAGE_REF = '90a5306cf6012189c606c8a14fe6731dca9cb5c8';
const FILES = [
  'worker/START DIEHL VIN.cmd',
  'worker/DiehlInitializer.py',
  'worker/service_v4.py',
  'worker/shared_workbook.py',
  'worker/workbook_organizer.py',
  'worker/vin_lookup.py',
  'worker/dtna_login_and_sync.py',
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
    const initializer = fetched.find(x => x.path.endsWith('DiehlInitializer.py'))?.text || '';
    const organizer = fetched.find(x => x.path.endsWith('workbook_organizer.py'))?.text || '';

    if (!launcher.includes('SETUP AND START v4.8')) throw new Error('Pinned v4.8 launcher verification failed.');
    if (!initializer.includes('Switching initialization to verified venv Python')) throw new Error('Pinned initializer verification failed.');
    if (!organizer.includes("VIN_SHEET = 'VIN In-Service'") || !organizer.includes("DTNA_SHEET = 'DTNA'")) {
      throw new Error('Pinned workbook organizer verification failed.');
    }

    const zip = new JSZip();
    const folder = zip.folder('Diehl_VIN_Local_Worker_v4_8');
    if (!folder) throw new Error('Could not create ZIP folder.');

    for (const file of fetched) folder.file(file.path.replace(/^worker\//, ''), file.text);

    folder.file('PACKAGE VERSION.txt', [
      `Diehl VIN Local Worker ${PACKAGE_VERSION}`,
      `Pinned package revision: ${PACKAGE_REF}`,
      'Expected launcher banner: DIEHL VIN - SETUP AND START v4.8',
      'Permanent runtime: %LocalAppData%\\DiehlVINWorker\\v4',
      'Python runtime: 3.12',
      'Shared workbook: DIEHL-VIN-PLATFORM WORKBOOK.xlsx',
      'Workbook sheets: VIN In-Service and DTNA',
      'No legacy-process cleanup is performed during startup.',
      'All worker files are included in this ZIP. START does not download worker files from GitHub.',
      'System Python prepares the venv, then initialization switches into the verified venv before Excel COM is used.',
      `Generated: ${new Date().toISOString()}`,
    ].join('\r\n'));

    folder.file('READ ME FIRST.txt', [
      `DIEHL VIN LOCAL WORKER v${PACKAGE_VERSION}`,
      '',
      '1. Extract the ENTIRE ZIP to a normal folder.',
      '2. Double-click START DIEHL VIN.cmd from that extracted folder.',
      '3. The banner must say DIEHL VIN - SETUP AND START v4.8.',
      '4. START copies the included audited files into LocalAppData\\DiehlVINWorker\\v4.',
      '5. It verifies/repairs the Python environment, including pythoncom/pywin32.',
      '6. It switches into .venv\\Scripts\\python.exe before Excel automation.',
      '7. It automatically locates DIEHL-VIN-PLATFORM WORKBOOK.xlsx in synced OneDrive.',
      '8. It organizes VIN In-Service and DTNA sheets and starts the worker.',
      '9. Initialize YOUR DTNA login from the site and complete your own MFA.',
      '',
      'The worker does not download program files during startup. Only Python itself may be downloaded if Python 3.12 is not already installed.',
    ].join('\r\n'));

    const body = await zip.generateAsync({type: 'arraybuffer', compression: 'DEFLATE', compressionOptions: {level: 6}});
    return new Response(body, {
      status: 200,
      headers: {
        'Content-Type': 'application/zip',
        'Content-Disposition': 'attachment; filename="Diehl_VIN_Local_Worker_v4_8.zip"',
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
