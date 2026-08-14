'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';

export default function InitializerPage() {
  const [workerUrl,setWorkerUrl]=useState('');
  const [workerKey,setWorkerKey]=useState('');
  const [status,setStatus]=useState('Not connected yet');
  const [checking,setChecking]=useState(false);

  useEffect(()=>{
    setWorkerUrl(localStorage.getItem('diehlWorkerUrl')||'');
    setWorkerKey(localStorage.getItem('diehlWorkerKey')||'');
  },[]);

  async function testConnection(){
    setChecking(true);
    try{
      const r=await fetch(workerUrl.replace(/\/$/,'')+'/health',{headers:{'x-worker-key':workerKey}});
      const d=await r.json();
      if(!r.ok) throw new Error(d.detail||'Connection failed');
      localStorage.setItem('diehlWorkerUrl',workerUrl.trim().replace(/\/$/,''));
      localStorage.setItem('diehlWorkerKey',workerKey.trim());
      setStatus(`Connected to ${d.worker?.hostname||'Windows worker'} · workbook ${d.worker?.onedrive_status||'ready'}`);
    }catch(e:any){setStatus(e.message||'Connection failed')}finally{setChecking(false)}
  }

  return <main className="initializer-page">
    <section className="initializer-hero">
      <div><span className="kicker">FIRST-TIME SETUP</span><h1>Initialize this computer</h1><p>Install the local Diehl worker, DTNA browser automation, Excel/OneDrive support, and secure tunnel. After setup, this computer becomes the engine behind the DTNA and VIN In-Service tabs.</p></div>
      <a className="download-primary" href="/DiehlVINInitializer.bat" download>Download Windows Initializer</a>
    </section>

    <section className="setup-grid">
      <article className="setup-card featured"><div className="step-num">1</div><h2>Download and run the initializer</h2><p>The initializer creates the local worker folder, installs Python when needed, installs the worker packages, Playwright support, and Cloudflare Tunnel, and creates the local configuration file.</p><a className="button-primary" href="/DiehlVINInitializer.bat" download>Download initializer .BAT</a><p className="fine">Windows may ask for permission to install Python or Cloudflare Tunnel.</p></article>
      <article className="setup-card"><div className="step-num">2</div><h2>DTNA login remains local</h2><p>The worker opens the DTNA browser profile on this computer. Complete DTNA login/MFA when requested. The browser profile is reused on later runs.</p><Link className="button-secondary" href="/dtna">Open DTNA tab</Link></article>
      <article className="setup-card"><div className="step-num">3</div><h2>Excel stays the master database</h2><p><code>VIN_Master_Data.xlsx</code> remains the permanent record. The worker serializes workbook writes so multiple browser workers do not corrupt Excel or OneDrive.</p><Link className="button-secondary" href="/vin-inservice">Open VIN In-Service</Link></article>
    </section>

    <section className="connection-card">
      <div><span className="kicker">WORKER CONNECTION</span><h2>Connect this browser to the initialized computer</h2><p>After the initializer starts the secure tunnel, copy the HTTPS worker URL and access key shown in the worker window or connection-info file.</p></div>
      <div className="connection-fields"><label>Worker HTTPS URL<input value={workerUrl} onChange={e=>setWorkerUrl(e.target.value)} placeholder="https://xxxxx.trycloudflare.com"/></label><label>Access key<input type="password" value={workerKey} onChange={e=>setWorkerKey(e.target.value)} placeholder="Worker access key"/></label><button onClick={testConnection} disabled={checking||!workerUrl||!workerKey}>{checking?'Checking…':'Save & test connection'}</button></div>
      <div className="connection-status">{status}</div>
    </section>

    <section className="installed-list"><h2>What the initializer installs</h2><div className="installed-items"><span>Python virtual environment</span><span>FastAPI worker service</span><span>Excel / OneDrive support</span><span>Playwright DTNA automation</span><span>Persistent DTNA browser profile</span><span>Cloudflare HTTPS tunnel</span><span>Local resumable job queue</span><span>1–8 isolated browser slots</span></div></section>
  </main>;
}
