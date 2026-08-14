import JSZip from 'jszip';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const REPO = 'Wickey23/Diehl-vin-platform';
const BRANCH = 'main';
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
  const url = `https://raw.githubusercontent.com/${REPO}/${BRANCH}/${path.split('/').map(encodeURIComponent).join('/')}`;
  const response = await fetch(url, { cache: 'no-store' });
  if (!response.ok) throw new Error(`Could not fetch ${path} (${response.status})`);
  return response.text();
}

export async function GET() {
  try {
    const zip = new JSZip();
    const folder = zip.folder('Diehl_VIN_Local_Worker');
    if (!folder) throw new Error('Could not create ZIP folder.');

    await Promise.all(FILES.map(async (path) => {
      folder.file(path.replace(/^worker\//, ''), await fetchText(path));
    }));

    folder.file('READ ME FIRST.txt', [
      'DIEHL VIN LOCAL WORKER v4',
      '',
      'FIRST TIME ON A PC',
      '1. Extract this ZIP.',
      '2. Double-click START DIEHL VIN.cmd.',
      '3. Choose your existing Excel workbook once.',
      '4. The worker starts in the background and the website opens.',
      '',
      'AFTER THAT',
      'Just double-click START DIEHL VIN.cmd when you need to start/restart the local worker.',
      'The permanent install lives under LocalAppData\\DiehlVINWorker and reuses the same Python environment and workbook config.',
      '',
      'DTNA login/MFA, browser profile, and Excel remain local to this Windows computer.',
    ].join('\r\n'));

    const body = await zip.generateAsync({ type: 'arraybuffer', compression: 'DEFLATE', compressionOptions: { level: 6 } });
    return new Response(body, {
      status: 200,
      headers: {
        'Content-Type': 'application/zip',
        'Content-Disposition': 'attachment; filename="Diehl_VIN_Local_Worker_v4.zip"',
        'Cache-Control': 'no-store, max-age=0',
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Could not build local worker ZIP.';
    return Response.json({ error: message }, { status: 500 });
  }
}
