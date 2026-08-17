import JSZip from 'jszip';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';
export const revalidate = 0;

const REPO = 'Wickey23/Diehl-vin-platform';
const LAUNCHER_REF = '726ff049cd47c26b122921410b8056f81671745c';
const PACKAGE_VERSION = '4.6';

async function fetchLauncher() {
  const url = `https://raw.githubusercontent.com/${REPO}/${LAUNCHER_REF}/worker/START%20DIEHL%20VIN.cmd`;
  const response = await fetch(url, {
    cache: 'no-store',
    headers: {'Cache-Control': 'no-cache, no-store, max-age=0', 'Pragma': 'no-cache'},
  });
  if (!response.ok) throw new Error(`Could not fetch verified launcher (${response.status})`);
  const text = await response.text();
  if (!text.includes('SETUP AND START v4.6')) throw new Error('Verified v4.6 launcher could not be loaded.');
  if (!text.includes('WORKER_REF=2a1b3a35b20465b9da2fc9d0d2f4850dd8d9f9b3')) throw new Error('Launcher worker revision verification failed.');
  return text;
}

export async function GET() {
  try {
    const launcher = await fetchLauncher();
    const zip = new JSZip();
    const folder = zip.folder('Diehl_VIN_Local_Worker_v4_6');
    if (!folder) throw new Error('Could not create ZIP folder.');

    folder.file('START DIEHL VIN.cmd', launcher);
    folder.file('PACKAGE VERSION.txt', [
      `Diehl VIN Local Worker ${PACKAGE_VERSION}`,
      `Launcher revision: ${LAUNCHER_REF}`,
      'Pinned worker revision: 2a1b3a35b20465b9da2fc9d0d2f4850dd8d9f9b3',
      'Expected launcher banner: DIEHL VIN - SETUP AND START v4.6',
      'Permanent runtime: %LocalAppData%\\DiehlVINWorker\\v4',
      'Python runtime: 3.12',
      'Shared workbook: DIEHL-VIN-PLATFORM WORKBOOK.xlsx',
      'Workbook sheets: VIN In-Service and DTNA',
      'No legacy-process cleanup is performed during startup.',
      'The launcher downloads one pinned, verified worker revision; it does not use mutable main.',
      `Generated: ${new Date().toISOString()}`,
    ].join('\r\n'));

    folder.file('READ ME FIRST.txt', [
      `DIEHL VIN LOCAL WORKER v${PACKAGE_VERSION}`,
      '',
      '1. Extract this ZIP.',
      '2. Double-click START DIEHL VIN.cmd.',
      '3. The banner must say DIEHL VIN - SETUP AND START v4.6.',
      '4. START installs the pinned worker into LocalAppData\\DiehlVINWorker\\v4.',
      '5. It verifies/repairs the Python environment, including pythoncom/pywin32.',
      '6. It automatically locates DIEHL-VIN-PLATFORM WORKBOOK.xlsx in synced OneDrive.',
      '7. It organizes VIN In-Service and DTNA sheets and starts the worker.',
      '8. Initialize YOUR DTNA login from the site and complete your own MFA.',
      '',
      'The ZIP intentionally contains only the launcher and instructions. The launcher is the single source of truth.',
    ].join('\r\n'));

    const body = await zip.generateAsync({type: 'arraybuffer', compression: 'DEFLATE', compressionOptions: {level: 6}});
    return new Response(body, {
      status: 200,
      headers: {
        'Content-Type': 'application/zip',
        'Content-Disposition': 'attachment; filename="Diehl_VIN_Local_Worker_v4_6.zip"',
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
