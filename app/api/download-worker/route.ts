import JSZip from 'jszip';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';
export const revalidate = 0;

// v5.16.2 canonical package. The restored normal worker remains unchanged;
// START LOCAL DTNA.cmd is an optional independent localhost workflow.
const REPO = 'Wickey23/Diehl-vin-platform';
const PACKAGE_VERSION = '5.16.2';
const PACKAGE_REF = 'main';
const FILES = [
  'worker/START DIEHL VIN.cmd',
  'worker/START LOCAL DTNA.cmd',
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
  'worker/local_dtna_app.py',
  'worker/requirements.txt',
  'worker/README_LOCAL.txt',
];

async function fetchPinned(path: string) {
  const encodedPath = path.split('/').map(encodeURIComponent).join('/');
  const url = `https://raw.githubusercontent.com/${REPO}/${PACKAGE_REF}/${encodedPath}`;
  const response = await fetch(url, {cache: 'no-store'});
  if (!response.ok) throw new Error(`Could not fetch ${path} (${response.status})`);
  return await response.text();
}

export async function GET() {
  try {
    const fetched = await Promise.all(FILES.map(async path => ({path, text: await fetchPinned(path)})));
    const get = (name: string) => fetched.find(x => x.path.endsWith(name))?.text || '';

    const launcher = get('START DIEHL VIN.cmd');
    const localLauncher = get('START LOCAL DTNA.cmd');
    const stopper = get('STOP ALL DIEHL.cmd');
    const baseInitializer = get('DiehlInitializer.py');
    const wrapperInitializer = get('DiehlInitializer_v514.py');
    const service = get('service_v7.py');
    const dtnaRuntime = get('dtna_runtime.py');
    const localDtna = get('local_dtna_app.py');

    if (!launcher.includes('SETUP AND START v5.16.2')) throw new Error('Launcher is not v5.16.2.');
    if (!localLauncher.includes('DIEHL LOCAL DTNA WRITER')) throw new Error('Local DTNA launcher is missing.');
    if (!stopper.includes('service_v7\\.py')) throw new Error('STOP ALL does not recognize service_v7.py.');
    if (!baseInitializer.includes("SERVICE = ROOT / 'service_v7.py'")) throw new Error('Base initializer is not routed to service_v7.py.');
    if (!baseInitializer.includes("EXPECTED_WORKER_VERSION = '5.16.2'")) throw new Error('Base initializer is not locked to v5.16.2.');
    if (!wrapperInitializer.includes("EXPECTED_WORKER_VERSION = '5.16.2'")) throw new Error('Wrapper initializer is not v5.16.2.');
    if (!service.includes("service.base.VERSION = '5.16.2'")) throw new Error('Service is not v5.16.2.');
    if (!dtnaRuntime.includes("row['lastChangeTime'] = run_time")) throw new Error('DTNA run-time stamping fix is missing.');
    if (!dtnaRuntime.includes('DIEHL_DTNA_WORKBOOK')) throw new Error('Local workbook override is missing.');
    if (!localDtna.includes('Choose Workbook')) throw new Error('Local DTNA workbook selector UI is missing.');

    const zip = new JSZip();
    const folder = zip.folder('Diehl_VIN_Local_Worker_v5_16_2');
    if (!folder) throw new Error('Could not create ZIP folder.');
    for (const file of fetched) folder.file(file.path.replace(/^worker\//, ''), file.text);

    folder.file('PACKAGE VERSION.txt', [
      'Diehl VIN Local Worker 5.16.2',
      `Package source: ${PACKAGE_REF}`,
      'The restored normal worker behavior remains available through START DIEHL VIN.cmd.',
      'Optional localhost DTNA mode is available through START LOCAL DTNA.cmd.',
      'Localhost DTNA lets you choose an exact .xlsx/.xlsm workbook and an existing worksheet.',
      'DTNA lastChangeTime is stamped with the date/time of each successful DTNA run for every row.',
    ].join('\r\n'));

    folder.file('READ ME FIRST.txt', [
      'DIEHL VIN LOCAL WORKER v5.16.2',
      '',
      'NORMAL MODE:',
      'Run START DIEHL VIN.cmd to use the restored shared-workbook platform.',
      '',
      'LOCALHOST DTNA MODE:',
      '1. Double-click START LOCAL DTNA.cmd.',
      '2. Your browser opens http://127.0.0.1:8770.',
      '3. Click Choose Workbook and select an existing .xlsx or .xlsm file.',
      '4. Choose an existing worksheet from that workbook.',
      '5. Click Run DTNA + Write Excel.',
      '6. DTNA writes directly back into that exact workbook and existing sheet.',
    ].join('\r\n'));

    const body = await zip.generateAsync({type:'arraybuffer',compression:'DEFLATE',compressionOptions:{level:6}});
    return new Response(body,{status:200,headers:{
      'Content-Type':'application/zip',
      'Content-Disposition':'attachment; filename="Diehl_VIN_Local_Worker_v5_16_2.zip"',
      'Cache-Control':'no-store, no-cache, must-revalidate, max-age=0',
      'X-Diehl-Worker-Package':PACKAGE_VERSION,
      'X-Diehl-Package-Revision':PACKAGE_REF,
    }});
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Could not build local worker ZIP.';
    return Response.json({error:message},{status:500,headers:{'Cache-Control':'no-store'}});
  }
}
