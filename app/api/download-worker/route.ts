import JSZip from 'jszip';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const REPO = 'Wickey23/Diehl-vin-platform';
const BRANCH = 'main';
const FILES = [
  'worker/START DIEHL VIN.cmd',
  'worker/DiehlInitializer.py',
  'worker/server.py',
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

    await Promise.all(
      FILES.map(async (path) => {
        const name = path.replace(/^worker\//, '');
        folder.file(name, await fetchText(path));
      })
    );

    const readme = [
      'DIEHL VIN LOCAL WORKER',
      '',
      'FIRST TIME',
      '1. Extract this ZIP to a normal folder.',
      '2. Double-click START DIEHL VIN.cmd.',
      '3. Choose your existing Excel workbook when asked.',
      '4. The worker starts and the Diehl VIN website opens automatically.',
      '',
      'LATER',
      'Double-click START DIEHL VIN.cmd only if the worker is not already running.',
      'If the worker is already running, the launcher simply opens the website.',
      '',
      'The worker remains local to this computer. DTNA login/MFA and Excel stay local.',
    ].join('\r\n');
    folder.file('READ ME FIRST.txt', readme);

    const body = await zip.generateAsync({ type: 'arraybuffer', compression: 'DEFLATE', compressionOptions: { level: 6 } });

    return new Response(body, {
      status: 200,
      headers: {
        'Content-Type': 'application/zip',
        'Content-Disposition': 'attachment; filename="Diehl_VIN_Local_Worker.zip"',
        'Cache-Control': 'no-store, max-age=0',
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Could not build local worker ZIP.';
    return Response.json({ error: message }, { status: 500 });
  }
}
