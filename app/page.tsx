'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';

type Check={id:string;label:string;status:'ok'|'warning'|'missing';detail:string};

export default function InitializerPage() {
  const [workerUrl,setWorkerUrl]=useState('');
  const [workerKey,setWorkerKey]=useState('');
  const [status,setStatus]=useState('Looking for the Diehl Windows worker');
  const [checking,setChecking]=useState(false);
  const [checks,setChecks]=useState<Check[]>([]);
  const [ready,setReady]=useState(false);
  const [summary,setSummary]=useState('Run the separate Diehl initializer on this computer, then connect it here.');

  useEffect(()=>{
    const u=localStorage.getItem('diehlWorkerUrl')||'';
    const k=localStorage.getItem('diehlWorkerKey')||'';
    setWorkerUrl(u);setWorkerKey(k);
    if(u&&k) testConnection(u,k);
  },[]);

  async function testConnection(urlArg=workerUrl,keyArg=workerKey){
    setChecking(true);
    try{
      const base=urlArg.trim().replace(/\/$/,'');
      const headers={'x-worker-key':keyArg.trim()};
      const hr=await fetch(base+'/health',{headers});const hd=await hr.json();
      if(!hr.ok) throw new Error(hd.detail||'Diehl initializer/worker was not detected');
      const sr=await fetch(base+'/initializer/status',{headers});const sd=await sr.json();
      if(!sr.ok) throw new Error(sd.detail||'Could not inspect the initialized computer');
      localStorage.setItem('diehlWorkerUrl',base);localStorage.setItem('diehlWorkerKey',keyArg.trim());
      setWorkerUrl(base);setChecks(sd.checks||[]);setReady(!!sd.ready);setSummary(sd.summary||'Checks complete');
      setStatus(`Initializer detected on ${hd.worker?.hostname||'this Windows computer'} · ${hd.worker?.onedrive_status||'workbook status unknown'}`);
    }catch(e:any){setChecks([]);setReady(false);setSummary('The website could not find a running Diehl initializer/worker with these connection details.');setStatus(e.message||'Initializer not detected')}finally{setChecking(false)}
  }

  const icon=(s:Check['status'])=>s==='ok'?'✓':s==='warning'?'!':'×';

  return <main className="initializer-page">
    <section className="initializer-hero">
      <div><span className="kicker">LOCAL SYSTEM CHECK</span><h1>Diehl Initializer</h1><p>The initializer is installed separately on the Windows computer. This site does not install or modify your computer; it only detects the running worker and checks that DTNA, Excel, OneDrive, Outlook and browser automation are available.</p></div>
      <div className={'readiness '+(ready?'ready':'')}>{ready?'READY TO USE':'NOT DETECTED / CHECK REQUIRED'}</div>
    </section>

    <section className="connection-card">
      <div><span className="kicker">WORKER CONNECTION</span><h2>Find the installed initializer</h2><p>Run the Diehl initializer package you received. It creates a connection-info file containing the HTTPS worker URL and access key. Enter them once here; this browser remembers them.</p></div>
      <div className="connection-fields"><label>Worker HTTPS URL<input value={workerUrl} onChange={e=>setWorkerUrl(e.target.value)} placeholder="https://xxxxx.trycloudflare.com"/></label><label>Access key<input type="password" value={workerKey} onChange={e=>setWorkerKey(e.target.value)} placeholder="Worker access key"/></label><button onClick={()=>testConnection()} disabled={checking||!workerUrl||!workerKey}>{checking?'Checking…':'Detect & check'}</button></div>
      <div className="connection-status">{status}</div>
    </section>

    <section className="prereq-card">
      <div className="prereq-head"><div><span className="kicker">SYSTEM CHECK</span><h2>Installed components</h2></div><button onClick={()=>testConnection()} disabled={checking||!workerUrl||!workerKey}>Re-run checks</button></div>
      <p className="prereq-summary">{summary}</p>
      <div className="check-list">
        {checks.length?checks.map(c=><div className={'check-row '+c.status} key={c.id}><span className="check-icon">{icon(c.status)}</span><div><b>{c.label}</b><small>{c.detail}</small></div><span className="check-state">{c.status==='ok'?'Ready':c.status==='warning'?'Check':'Missing'}</span></div>):<div className="check-empty">No local initializer detected yet. Start the installed Diehl worker, then enter its URL and key above.</div>}
      </div>
    </section>

    <section className="setup-grid">
      <article className="setup-card featured"><div className="step-num">1</div><h2>Initializer</h2><p>Installed and run separately on the DTNA Windows computer. The website only verifies it; there are no software downloads or installers hosted in the site.</p></article>
      <article className="setup-card"><div className="step-num">2</div><h2>DTNA</h2><p>Once the initializer is detected, use this tab for DTNA login/MFA, Sales Order and AUTO VIN.</p><Link className="button-secondary" href="/dtna">Open DTNA</Link></article>
      <article className="setup-card"><div className="step-num">3</div><h2>VIN In-Service</h2><p>Use the separate VIN batch checker after the worker and master Excel workbook pass the system check.</p><Link className="button-secondary" href="/vin-inservice">Open VIN In-Service</Link></article>
    </section>
  </main>;
}
