import JSZip from 'jszip';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';
export const revalidate = 0;

const REPO = 'Wickey23/Diehl-vin-platform';
const BRANCH = 'main';
const PACKAGE_VERSION = '4.1';
const FILES = [
  'worker/START DIEHL VIN.cmd',
  'worker/DiehlInitializer.py',
  'worker/service_v4.py',
  'worker/configure_workbook.py',
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
    headers: {
      'Cache-Control': 'no-cache, no-store, max-age=0',
      'Pragma': 'no-cache',
    },
  });
  if (!response.ok) throw new Error(`Could not fetch ${path} (${response.status})`);
  const text = await response.text();
  if (path.endsWith('START DIEHL VIN.cmd') && !text.includes('DIEHL VIN - START v4')) {
    throw new Error('GitHub returned a stale launcher. Please try the download again.');
  }
  return text;
}

export async function GET() {
  try {
    const zip = new JSZip();
    const folder = zip.folder('Diehl_VIN_Local_Worker_v4_1');
    if (!folder) throw new Error('Could not create ZIP folder.');

    const fetched = await Promise.all(FILES.map(async (path) => ({
      path,
      text: await fetchText(path),
    })));

    for (const file of fetched) {
      folder.file(file.path.replace(/^worker\//, ''), file.text);
    }

    folder.file('PACKAGE VERSION.txt', [
      `Diehl VIN Local Worker ${PACKAGE_VERSION}`,
      'Expected launcher banner: DIEHL VIN - START v4',
      'Runtime folder: %LocalAppData%\\DiehlVINWorker\\v4',
      'Required Python runtime: 3.12',
      `Generated: ${new Date().toISOString()}`,
    ].join('\r\n'));

    folder.file('READ ME FIRST.txt', [
      `DIEHL VIN LOCAL WORKER v${PACKAGE_VERSION}`,
      '',
      'FIRST TIME ON A PC',
      '1. Extract this ZIP.',
      '2. Double-click START DIEHL VIN.cmd.',
      '3. The first line must say DIEHL VIN - START v4.',
      '4. Choose your existing Excel workbook if asked.',
      '5. The worker starts in the background and the website opens.',
      '',
      'The v4 runtime is isolated under LocalAppData\\DiehlVINWorker\\v4.',
      'Older locked .venv folders are ignored.',
      'Python 3.12 is used explicitly; Python 3.14 is not used.',
    ].join('\r\n'));

    const body = await zip.generateAsync({ type: 'arraybuffer', compression: 'DEFLATE', compressionOptions: { level: 6 } });
    return new Response(body, {
      status: 200,
      headers: {
        'Content-Type': 'application/zip',
        'Content-Disposition': 'attachment; filename="Diehl_VIN_Local_Worker_v4_1.zip"',
        'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
        'Pragma': 'no-cache',
        'Expires': '0',
        'X-Diehl-Worker-Package': PACKAGE_VERSION,
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Could not build local worker ZIP.';
    return Response.json({ error: message }, { status: 500, headers: { 'Cache-Control': 'no-store' } });
  }
}
