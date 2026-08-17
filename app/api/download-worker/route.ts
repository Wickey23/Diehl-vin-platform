import JSZip from 'jszip';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';
export const revalidate = 0;

const REPO = 'Wickey23/Diehl-vin-platform';
const LAUNCHER_REF = '3de65851ba92825489f007cef3ba3025f75d397b';
const PACKAGE_VERSION = '4.7';
const WORKER_REF = '1204c6e6e1db28c0d790ea298f31ee2389ee3ecc';

async function fetchLauncher() {
  const url = `https://raw.githubusercontent.com/${REPO}/${LAUNCHER_REF}/worker/START%20DIEHL%20VIN.cmd`;
  const response = await fetch(url, {
    cache: 'no-store',
    headers: {'Cache-Control': 'no-cache, no-store, max-age=0', 'Pragma': 'no-cache'},
  });
  if (!response.ok) throw new Error(`Could not fetch verified launcher (${response.status})`);
  const text = await response.text();
  if (!text.includes('SETUP AND START v4.7')) throw new Error('Verified v4.7 launcher could not be loaded.');
  if (!text.includes(`WORKER_REF=${WORKER_REF}`)) throw new Error('Launcher worker revision verification failed.');
  return text;
}

export async function GET() {
  try {
    const launcher = await fetchLauncher();
    const zip = new JSZip();
    const folder = zip.folder('Diehl_VIN_Local_Worker_v4_7');
    if (!folder) throw new Error('Could not create ZIP folder.');

    folder.file('START DIEHL VIN.cmd', launcher);
    folder.file('PACKAGE VERSION.txt', [
      `Diehl VIN Local Worker ${PACKAGE_VERSION}`,
      `Launcher revision: ${LAUNCHER_REF}`,
      `Pinned worker revision: ${WORKER_REF}`,
      'Expected launcher banner: DIEHL VIN - SETUP AND START v4.7',
      'Permanent runtime: %LocalAppData%\\DiehlVINWorker\\v4',
      'Python runtime: 3.12',
      'Shared workbook: DIEHL-VIN-PLATFORM WORKBOOK.xlsx',
      'Workbook sheets: VIN In-Service and DTNA',
      'No legacy-process cleanup is performed during startup.',
      'System Python bootstraps/repairs the venv, then initialization relaunches inside the verified venv before Excel COM is used.',
      `Generated: ${new Date().toISOString()}`,
    ].join('\r\n'));

    folder.file('READ ME FIRST.txt', [
      `DIEHL VIN LOCAL WORKER v${PACKAGE_VERSION}`,
      '',
      '1. Extract this ZIP.',
      '2. Double-click START DIEHL VIN.cmd.',
      '3. The banner must say DIEHL VIN - SETUP AND START v4.7.',
      '4. START installs the pinned worker into LocalAppData\\DiehlVINWorker\\v4.',
      '5. It verifies/repairs the Python environment, including pythoncom/pywin32.',
      '6. It then switches initialization into .venv\\Scripts\\python.exe before touching Excel.',
      '7. It automatically locates DIEHL-VIN-PLATFORM WORKBOOK.xlsx in synced OneDrive.',
      '8. It organizes VIN In-Service and DTNA sheets and starts the worker.',
      '9. Initialize YOUR DTNA login from the site and complete your own MFA.',
      '',
      'The ZIP intentionally contains only the launcher and instructions. The launcher is the single source of truth.',
    ].join('\r\n'));

    const body = await zip.generateAsync({type: 'arraybuffer', compression: 'DEFLATE', compressionOptions: {level: 6}});
    return new Response(body, {
      status: 200,
      headers: {
        'Content-Type': 'application/zip',
        'Content-Disposition': 'attachment; filename="Diehl_VIN_Local_Worker_v4_7.zip"',
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
