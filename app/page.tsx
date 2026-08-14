'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';

type Check={id:string;label:string;status:'ok'|'warning'|'missing';detail:string};

export default function InitializerPage() {
  const [workerUrl,setWorkerUrl]=useState('');
  const [workerKey,setWorkerKey]=useState('');
  const [status,setStatus]=useState('Not connected yet');
  const [checking,setChecking]=useState(false);
  const [checks,setChecks]=useState<Check[]>([]);
  const [ready,setReady]=useState(false);
  const [summary,setSummary]=useState('Run the initializer, then connect this browser.');

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
      if(!hr.ok) throw new Error(hd.detail||'Connection failed');
      const sr=await fetch(base+'/initializer/status',{headers});const sd=await sr.json();
      if(!sr.ok) throw new Error(sd.detail||'Could not inspect prerequisites');
      localStorage.setItem('diehlWorkerUrl',base);localStorage.setItem('diehlWorkerKey',keyArg.trim());
      setWorkerUrl(base);setChecks(sd.checks||[]);setReady(!!sd.ready);setSummary(sd.summary||'Checks complete');
      setStatus(`Connected to ${hd.worker?.hostname||'Windows worker'} · ${hd.worker?.onedrive_status||'workbook status unknown'}`);
    }catch(e:any){setChecks([]);setReady(false);setSummary('Worker is not connected, so this browser cannot verify local prerequisites.');setStatus(e.message||'Connection failed')}finally{setChecking(false)}
  }

  const icon=(s:Check['status'])=>s==='ok'?'✓':s==='warning'?'!':'×';

  return <main className="initializer-page">
    <section className="initializer-hero">
      <div><span className="kicker">FIRST-TIME SETUP</span><h1>Initialize this computer</h1><p>This is the first screen on purpose. It checks the local Windows worker and verifies the pieces needed for DTNA and VIN In-Service before you start using either workflow.</p></div>
      <a className="download-primary" href="/DiehlVINInitializer.bat" download>Download Windows Initializer</a>
    </section>

    <section className="connection-card">
      <div><span className="kicker">WORKER CONNECTION</span><h2>Connect and run system checks</h2><p>The initializer starts the local worker and secure tunnel. Paste the HTTPS worker URL and access key shown in <code>connection-info.txt</code>.</p></div>
      <div className="connection-fields"><label>Worker HTTPS URL<input value={workerUrl} onChange={e=>setWorkerUrl(e.target.value)} placeholder="https://xxxxx.trycloudflare.com"/></label><label>Access key<input type="password" value={workerKey} onChange={e=>setWorkerKey(e.target.value)} placeholder="Worker access key"/></label><button onClick={()=>testConnection()} disabled={checking||!workerUrl||!workerKey}>{checking?'Checking…':'Save & run checks'}</button></div>
      <div className="connection-status">{status}</div>
    </section>

    <section className="prereq-card">
      <div className="prereq-head"><div><span className="kicker">SYSTEM CHECK</span><h2>Required local components</h2></div><div className={'readiness '+(ready?'ready':'')}>{ready?'READY TO USE':'SETUP REQUIRED'}</div></div>
      <p className="prereq-summary">{summary}</p>
      <div className="check-list">
        {checks.length?checks.map(c=><div className={'check-row '+c.status} key={c.id}><span className="check-icon">{icon(c.status)}</span><div><b>{c.label}</b><small>{c.detail}</small></div><span className="check-state">{c.status==='ok'?'Ready':c.status==='warning'?'Check':'Missing'}</span></div>):<div className="check-empty">Connect the worker above to inspect this Windows computer.</div>}
      </div>
      <div className="check-actions"><button onClick={()=>testConnection()} disabled={checking||!workerUrl||!workerKey}>Re-run checks</button><a className="button-secondary" href="/DiehlVINInitializer.bat" download>Repair / reinstall components</a></div>
    </section>

    <section className="setup-grid">
      <article className="setup-card featured"><div className="step-num">1</div><h2>Run the initializer once</h2><p>It creates the local worker folder, Python virtual environment, worker packages, Playwright browser support, DTNA automation files, and Cloudflare Tunnel.</p><a className="button-primary" href="/DiehlVINInitializer.bat" download>Download initializer .BAT</a></article>
      <article className="setup-card"><div className="step-num">2</div><h2>DTNA</h2><p>Sales Order and AUTO VIN live in their own tab. DTNA login/MFA stays in the persistent local browser profile.</p><Link className="button-secondary" href="/dtna">Open DTNA tab</Link></article>
      <article className="setup-card"><div className="step-num">3</div><h2>VIN In-Service</h2><p>The VIN batch checker has its own tab and uses <code>VIN_Master_Data.xlsx</code> as the permanent business record.</p><Link className="button-secondary" href="/vin-inservice">Open VIN In-Service tab</Link></article>
    </section>
  </main>;
}
