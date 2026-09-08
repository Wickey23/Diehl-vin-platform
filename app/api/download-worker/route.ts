import JSZip from 'jszip';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';
export const revalidate = 0;

const REPO = 'Wickey23/Diehl-vin-platform';
const PACKAGE_VERSION = '5.16.3';
const PACKAGE_REF = 'main';
const FILES = [
  'worker/START DIEHL VIN.cmd',
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
  'worker/run_exports.py',
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
    const stopper = get('STOP ALL DIEHL.cmd');
    const baseInitializer = get('DiehlInitializer.py');
    const wrapperInitializer = get('DiehlInitializer_v514.py');
    const service = get('service_v7.py');
    const dtnaRuntime = get('dtna_runtime.py');
    const sharedWorkbook = get('shared_workbook.py');
    const runExports = get('run_exports.py');

    if (!launcher.includes('SETUP AND START v5.16.3')) throw new Error('Launcher is not v5.16.3.');
    if (!launcher.includes('run_exports.py')) throw new Error('Launcher does not install run_exports.py.');
    if (!stopper.includes('service_v7\\.py')) throw new Error('STOP ALL does not recognize service_v7.py.');
    if (!baseInitializer.includes("SERVICE = ROOT / 'service_v7.py'")) throw new Error('Base initializer is not routed to service_v7.py.');
    if (!baseInitializer.includes("EXPECTED_WORKER_VERSION = '5.16.3'")) throw new Error('Base initializer is not locked to v5.16.3.');
    if (!baseInitializer.includes("'workbookMode': 'per-computer-onedrive-source'")) throw new Error('Per-computer workbook mode is missing.');
    if (!wrapperInitializer.includes("EXPECTED_WORKER_VERSION = '5.16.3'")) throw new Error('Wrapper initializer is not v5.16.3.');
    if (!service.includes("service.base.VERSION = '5.16.3'")) throw new Error('Service is not v5.16.3.');
    if (!dtnaRuntime.includes('save_dtna_run')) throw new Error('DTNA run archive hook is missing.');
    if (!sharedWorkbook.includes('DIEHL-VIN-SOURCE_')) throw new Error('Per-computer source workbook naming is missing.');
    if (!runExports.includes('DTNA_RUN_')) throw new Error('Run export module is incomplete.');

    const zip = new JSZip();
    const folder = zip.folder('Diehl_VIN_Local_Worker_v5_16_3');
    if (!folder) throw new Error('Could not create ZIP folder.');
    for (const file of fetched) folder.file(file.path.replace(/^worker\//, ''), file.text);

    folder.file('PACKAGE VERSION.txt', [
      'Diehl VIN Local Worker 5.16.3',
      `Package source: ${PACKAGE_REF}`,
      'Each PC creates and writes to its own OneDrive source workbook.',
      'DTNA and VIN In-Service use that per-computer workbook as the configured database target.',
      'Every successful DTNA run is archived as a downloadable Excel file.',
      'DTNA lastChangeTime is stamped with the date/time of each successful DTNA run.',
    ].join('\r\n'));

    folder.file('READ ME FIRST.txt', [
      'DIEHL VIN LOCAL WORKER v5.16.3',
      '',
      'This build uses a per-computer OneDrive source workbook.',
      '1. Extract the entire ZIP.',
      '2. Run STOP ALL DIEHL.cmd.',
      '3. Run START DIEHL VIN.cmd.',
      '4. Refresh the VIN Platform. It must display worker v5.16.3.',
      '5. The worker creates/uses DIEHL-VIN-SOURCE_<computer>_<user>.xlsx in OneDrive.',
      '6. Every successful DTNA sync is also archived for download from Export Runs.',
    ].join('\r\n'));

    const body = await zip.generateAsync({type:'arraybuffer',compression:'DEFLATE',compressionOptions:{level:6}});
    return new Response(body,{status:200,headers:{
      'Content-Type':'application/zip',
      'Content-Disposition':'attachment; filename="Diehl_VIN_Local_Worker_v5_16_3.zip"',
      'Cache-Control':'no-store, no-cache, must-revalidate, max-age=0',
      'X-Diehl-Worker-Package':PACKAGE_VERSION,
      'X-Diehl-Package-Revision':PACKAGE_REF,
    }});
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Could not build local worker ZIP.';
    return Response.json({error:message},{status:500,headers:{'Cache-Control':'no-store'}});
  }
}
