import JSZip from 'jszip';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';
export const revalidate = 0;

const REPO = 'Wickey23/Diehl-vin-platform';
const PACKAGE_VERSION = '5.9';
const PACKAGE_REF = '0702706105789f25b6b0e75a0b80bfcd6171290c';
const FILES = [
  'worker/START DIEHL VIN.cmd',
  'worker/STOP ALL DIEHL.cmd',
  'worker/DiehlInitializer.py',
  'worker/service_v4.py',
  'worker/service_v5.py',
  'worker/database_service.py',
  'worker/database_cache.py',
  'worker/excel_bridge.py',
  'worker/shared_workbook.py',
  'worker/workbook_organizer.py',
  'worker/vin_lookup.py',
  'worker/owl_lookup.py',
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
  if (!response.ok) throw new Error(`Could not fetch pinned package file ${path} (${response.status})`);
  const text = await response.text();
  if (!text || text.length < 10) throw new Error(`Pinned package file ${path} is empty or incomplete.`);
  return text;
}

export async function GET() {
  try {
    const fetched = await Promise.all(FILES.map(async path => ({path, text: await fetchPinned(path)})));
    const get = (name: string) => fetched.find(x => x.path.endsWith(name))?.text || '';

    const launcher = get('START DIEHL VIN.cmd');
    const stopper = get('STOP ALL DIEHL.cmd');
    const initializer = get('DiehlInitializer.py');
    const serviceV5 = get('service_v5.py');
    const owl = get('owl_lookup.py');
    const owlLogin = get('owl_login.py');
    const vinLookup = get('vin_lookup.py');
    const runtime = get('dtna_runtime.py');
    const database = get('database_service.py');
    const cache = get('database_cache.py');
    const excelBridge = get('excel_bridge.py');

    if (!launcher.includes('SETUP AND START v5.9') || !launcher.includes('database_cache.py') || !launcher.includes('excel_bridge.py')) throw new Error('Pinned v5.9 launcher verification failed.');
    if (!stopper.includes('service_v5\\.py') || !stopper.includes('DIEHL VIN - STOP ALL RUNNING')) throw new Error('Pinned Stop All utility verification failed.');
    if (!initializer.includes("'vinInServiceSource': 'OWL'")) throw new Error('Pinned initializer verification failed.');
    if (!serviceV5.includes('Engine Serial Number') || !serviceV5.includes('Allison Transmission Serial Number') || !serviceV5.includes('force_live_owl_lookup')) throw new Error('Pinned OWL worker service verification failed.');
    if (!owl.includes("OWL_SIGNON_URL = 'https://secure.freightliner.com/iwarranty/signOn'") || !owl.includes('WarrantyDetailsGoToServlet?FromInd=Home') || !owl.includes('ProductMaintenanceServlet?ActionType=AddNewSideNav&FromInd=SideNav')) throw new Error('Pinned exact OWL URLs verification failed.');
    if (!owl.includes('following-sibling::td[1]') || !owl.includes('Product S/N fill attempt') || !owl.includes('page.wait_for_timeout(1000)') || !owl.includes('1 second elapsed and Product S/N still verified; pressing Tab now.')) throw new Error('Pinned resilient OWL Product S/N flow verification failed.');
    if (!owlLogin.includes("OWL_URL = 'https://secure.freightliner.com/iwarranty/signOn'")) throw new Error('Pinned OWL login URL verification failed.');
    if (!vinLookup.includes("OWL = ROOT / 'owl_lookup.py'")) throw new Error('Pinned VIN lookup is not routed to OWL.');
    if (!runtime.includes('AUTO VIN could not be selected automatically') || !runtime.includes('Attached to already-open shared workbook')) throw new Error('Pinned DTNA runtime verification failed.');
    if (!database.includes("@app.post('/database/open-workbook')") || !database.includes('excel.Workbooks.Open') || !database.includes('workbook.Activate()')) throw new Error('Pinned Database Open Excel verification failed.');
    if (!database.includes('from database_cache import read_table') || database.includes('openpyxl')) throw new Error('Pinned Database viewer must remain lock-free.');
    if (!cache.includes("'DTNA' else 'vin-in-service.json'") || !cache.includes('Engine Serial Number')) throw new Error('Pinned Database mirror isolation verification failed.');
    if (!excelBridge.includes('collect_open_workbook') || !excelBridge.includes('GetRunningObjectTable')) throw new Error('Pinned Excel bridge verification failed.');

    const zip = new JSZip();
    const folder = zip.folder('Diehl_VIN_Local_Worker_v5_9');
    if (!folder) throw new Error('Could not create ZIP folder.');
    for (const file of fetched) folder.file(file.path.replace(/^worker\//, ''), file.text);

    folder.file('PACKAGE VERSION.txt', [
      `Diehl VIN Local Worker ${PACKAGE_VERSION}`,
      `Pinned package revision: ${PACKAGE_REF}`,
      'Expected launcher banner: DIEHL VIN - SETUP AND START v5.9',
      'OWL Product S/N flow: find adjacent input, type VIN, verify field, wait 1 full second, verify again, then press Tab',
      'VIN In-Service source: OWL Coverage Info / Check Coverage + Major Components',
      'OWL entry: https://secure.freightliner.com/iwarranty/signOn',
      'OWL Coverage: WarrantyDetailsGoToServlet?FromInd=Home',
      'OWL Major Components: ProductMaintenanceServlet?ActionType=AddNewSideNav&FromInd=SideNav',
      'DTNA source: Sales Order + Dealer Reporting AUTO VIN',
      'Shared workbook: DIEHL-VIN-PLATFORM WORKBOOK.xlsx',
      'Workbook sheets: VIN In-Service and DTNA',
      'Database viewer: lock-free verified local mirror with isolated sheet caches',
      'Database Open Excel: opens/activates the exact configured shared workbook',
      'Main worker: 127.0.0.1:8765',
      'Database + DTNA control service: 127.0.0.1:8766',
      `Generated: ${new Date().toISOString()}`,
    ].join('\r\n'));

    folder.file('READ ME FIRST.txt', [
      `DIEHL VIN LOCAL WORKER v${PACKAGE_VERSION}`,
      '',
      '1. Extract the ENTIRE ZIP to a normal folder.',
      '2. Double-click STOP ALL DIEHL.cmd to stop older Diehl services.',
      '3. Double-click START DIEHL VIN.cmd.',
      '4. The launcher banner must say v5.9.',
      '5. VIN In-Service opens OWL at secure.freightliner.com/iwarranty/signOn.',
      '6. Product S/N is found from its actual table cell and adjacent input.',
      '7. The VIN is typed and verified, then the worker waits exactly one full second before pressing Tab.',
      '8. Coverage Info uses the exact WarrantyDetailsGoToServlet page supplied for in-service/warranty information.',
      '9. Major Components uses the exact ProductMaintenanceServlet page supplied for engine/Allison serial numbers.',
      '10. Successful OWL results are written and verified in the VIN In-Service worksheet.',
      '11. DTNA is a separate Sales Order + AUTO VIN workflow writing only the DTNA worksheet.',
      '12. Database DTNA and VIN In-Service tabs are isolated and read from separate lock-free mirrors.',
      '13. Open Excel activates or opens DIEHL-VIN-PLATFORM WORKBOOK.xlsx itself, not a blank workbook.',
    ].join('\r\n'));

    const body = await zip.generateAsync({type: 'arraybuffer', compression: 'DEFLATE', compressionOptions: {level: 6}});
    return new Response(body, {
      status: 200,
      headers: {
        'Content-Type': 'application/zip',
        'Content-Disposition': 'attachment; filename="Diehl_VIN_Local_Worker_v5_9.zip"',
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
