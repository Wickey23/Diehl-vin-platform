import JSZip from 'jszip';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';
export const revalidate = 0;

const REPO = 'Wickey23/Diehl-vin-platform';
const BRANCH = 'main';
const PACKAGE_VERSION = '4.5';
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

async function fetchText(path: string) {
  const encodedPath = path.split('/').map(encodeURIComponent).join('/');
  const bust = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const url = `https://raw.githubusercontent.com/${REPO}/${BRANCH}/${encodedPath}?diehl=${bust}`;
  const response = await fetch(url, {
    cache: 'no-store',
    headers: {'Cache-Control': 'no-cache, no-store, max-age=0', 'Pragma': 'no-cache'},
  });
  if (!response.ok) throw new Error(`Could not fetch ${path} (${response.status})`);
  const text = await response.text();
  if (path.endsWith('START DIEHL VIN.cmd') && !text.includes('SETUP AND START v4.5')) {
    throw new Error('GitHub returned a stale launcher. Please try the download again.');
  }
  if (path.endsWith('shared_workbook.py') && !text.includes('DIEHL-VIN-PLATFORM WORKBOOK.xlsx')) {
    throw new Error('Shared workbook discovery module is stale or incomplete.');
  }
  if (path.endsWith('workbook_organizer.py') && (!text.includes("VIN_SHEET = 'VIN In-Service'") || !text.includes("DTNA_SHEET = 'DTNA'"))) {
    throw new Error('Workbook organizer is stale or incomplete.');
  }
  return text;
}

export async function GET() {
  try {
    const zip = new JSZip();
    const folder = zip.folder('Diehl_VIN_Local_Worker_v4_5');
    if (!folder) throw new Error('Could not create ZIP folder.');

    const fetched = await Promise.all(FILES.map(async (path) => ({path, text: await fetchText(path)})));
    for (const file of fetched) folder.file(file.path.replace(/^worker\//, ''), file.text);

    folder.file('PACKAGE VERSION.txt', [
      `Diehl VIN Local Worker ${PACKAGE_VERSION}`,
      'Expected launcher banner: DIEHL VIN - SETUP AND START v4.5',
      'Permanent runtime: %LocalAppData%\\DiehlVINWorker\\v4',
      'Python runtime: 3.12',
      'Shared workbook: DIEHL-VIN-PLATFORM WORKBOOK.xlsx',
      'Workbook sheets: VIN In-Service and DTNA',
      'No legacy-process cleanup is performed during startup.',
      'Each Windows user initializes their own DTNA login/MFA locally.',
      `Generated: ${new Date().toISOString()}`,
    ].join('\r\n'));

    folder.file('READ ME FIRST.txt', [
      `DIEHL VIN LOCAL WORKER v${PACKAGE_VERSION}`,
      '',
      '1. Extract this ZIP.',
      '2. Double-click START DIEHL VIN.cmd.',
      '3. The banner must say DIEHL VIN - SETUP AND START v4.5.',
      '4. START downloads/verifies the current supported worker files into LocalAppData.',
      '5. The worker automatically locates DIEHL-VIN-PLATFORM WORKBOOK.xlsx in synced OneDrive.',
      '6. The workbook is organized into VIN In-Service and DTNA sheets.',
      '7. After the worker connects, initialize YOUR DTNA login from the site and complete your own MFA.',
      '',
      'Startup currently performs NO old-process cleanup. We will add that later after the core flow is stable.',
      'If setup fails, the window remains open and displays the exact failing step.',
    ].join('\r\n'));

    const body = await zip.generateAsync({type: 'arraybuffer', compression: 'DEFLATE', compressionOptions: {level: 6}});
    return new Response(body, {
      status: 200,
      headers: {
        'Content-Type': 'application/zip',
        'Content-Disposition': 'attachment; filename="Diehl_VIN_Local_Worker_v4_5.zip"',
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
