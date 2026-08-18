'use client';

import Link from 'next/link';
import {useEffect,useState} from 'react';

const LOCAL='http://127.0.0.1:8765';
const LOCAL_DB='http://127.0.0.1:8766';
const LOGIN_KEY='diehl-dtna-login-initialized-v1';

type Check={id:string;label:string;status:'ok'|'warning'|'missing';detail:string};

export default function Initializer(){
  const [worker,setWorker]=useState<any>(null);
  const [checks,setChecks]=useState<Check[]>([]);
  const [workerReady,setWorkerReady]=useState(false);
  const [dtnaReady,setDtnaReady]=useState(false);
  const [checking,setChecking]=useState(false);
  const [stopping,setStopping]=useState(false);
  const [message,setMessage]=useState('Checking this computer…');

  async function check(){
    setChecking(true);
    try{
      const p=await fetch(`${LOCAL}/ping`,{cache:'no-store'});
      if(!p.ok) throw new Error('Worker not responding');
      const h=await fetch(`${LOCAL}/health`,{cache:'no-store'});
      if(!h.ok) throw new Error('Worker not responding');
      const hd=await h.json();
      const s=await fetch(`${LOCAL}/initializer/status`,{cache:'no-store'});
      if(!s.ok) throw new Error('Could not read initializer status');
      const sd=await s.json();
      const login=typeof window!=='undefined'&&localStorage.getItem(LOGIN_KEY)==='yes';
      setWorker(hd.worker||null);setChecks(sd.checks||[]);setWorkerReady(!!sd.ready);setDtnaReady(login);
      setMessage(!sd.ready?'The worker is connected, but the shared workbook still needs attention.':login?'This computer and your DTNA login are initialized.':'Worker and shared workbook are ready. Now initialize YOUR DTNA login.');
    }catch{
      setWorker(null);setChecks([]);setWorkerReady(false);setDtnaReady(false);
      setMessage('Worker not detected. Download the local worker below, extract it, and double-click START DIEHL VIN.cmd once.');
    }finally{setChecking(false)}
  }

  useEffect(()=>{check();const t=setInterval(check,5000);return()=>clearInterval(t)},[]);

  async function initializeDtna(){
    try{
      setMessage('Opening DTNA locally. Sign in with YOUR account and complete MFA.');
      const r=await fetch(`${LOCAL}/dtna/open`,{method:'POST',cache:'no-store'});
      if(!r.ok) throw new Error('Could not open DTNA');
      if(typeof window!=='undefined')localStorage.setItem(LOGIN_KEY,'yes');
      setDtnaReady(true);
      setMessage('DTNA opened. Complete YOUR username/password/MFA in that window. Your session stays local to this Windows user.');
    }catch{setMessage('Could not open DTNA. Confirm the local worker is running, then try again.')}
  }

  async function stopAllRunning(){
    setStopping(true);
    setMessage('Stopping Diehl local services…');
    try{
      const r=await fetch(`${LOCAL_DB}/control/stop-all`,{method:'POST',cache:'no-store'});
      if(!r.ok) throw new Error('Stop control unavailable');
      setWorker(null);setChecks([]);setWorkerReady(false);
      setMessage('All running Diehl local services were stopped. Now run START DIEHL VIN.cmd to start the current version.');
    }catch{
      setMessage('This older worker cannot be stopped from the website yet. Run STOP ALL DIEHL.cmd from the newest worker package, then run START DIEHL VIN.cmd.');
    }finally{
      setStopping(false);
      setTimeout(()=>check(),1800);
    }
  }

  const ready=workerReady&&dtnaReady;

  return <main className="initializer-page">
    <section className="initializer-hero">
      <div><span className="kicker">THIS COMPUTER</span><h1>Diehl VIN Initializer</h1><p>Each employee initializes their own Windows computer and their own DTNA session. The shared workbook is common; DTNA credentials, cookies, and MFA session are not.</p></div>
      <div className={'readiness '+(ready?'ready':'')}>{ready?'READY':'SETUP REQUIRED'}</div>
    </section>

    {!workerReady&&<section className="download-card">
      <div><span className="kicker">STEP 1 · ONE-TIME SETUP</span><h2>Download the local worker</h2><p>Download the ZIP, extract it, and double-click <b>START DIEHL VIN.cmd</b>. It installs/updates the permanent runtime, finds the shared OneDrive workbook, starts the local worker, and opens this site.</p></div>
      <div className="download-actions"><a className="download-primary" href="/api/download-worker">Download Local Worker</a><small>After download: Extract → double-click START DIEHL VIN.cmd</small></div>
    </section>}

    {workerReady&&!dtnaReady&&<section className="download-card">
      <div><span className="kicker">STEP 2 · REQUIRED FOR EACH EMPLOYEE</span><h2>Initialize your DTNA login</h2><p>Sign in with <b>your own DTNA account</b> and complete MFA. The local worker package does not contain another employee’s credentials, cookies, or browser profile.</p></div>
      <div className="download-actions"><button className="download-primary" onClick={initializeDtna}>Initialize My DTNA Login</button><small>DTNA opens locally on this PC. Complete your login/MFA there.</small></div>
    </section>}

    <section className="connection-card">
      <div><span className="kicker">LOCAL STATUS</span><h2>{worker?`Connected to ${worker.hostname}`:'Worker not detected'}</h2><p>{message}</p>{worker?.master_workbook&&<p><b>Shared workbook:</b> {worker.master_workbook}</p>}</div>
      <div className="row" style={{gap:10,flexWrap:'wrap'}}>
        <button onClick={check} disabled={checking}>{checking?'Checking…':'Check again'}</button>
        <button onClick={stopAllRunning} disabled={stopping} style={{background:'#b42318',color:'#fff',border:'1px solid #b42318'}}>{stopping?'Stopping…':'Stop All Running'}</button>
        {workerReady&&<button className="button-secondary" onClick={initializeDtna}>{dtnaReady?'Open / Refresh My DTNA Login':'Initialize My DTNA Login'}</button>}
      </div>
    </section>

    <section className="prereq-card">
      <div className="prereq-head"><div><span className="kicker">SYSTEM CHECK</span><h2>Everything needed on this PC</h2></div></div>
      <div className="check-list">
        {checks.length?checks.map(c=><div className={'check-row '+c.status} key={c.id}><span className="check-icon">{c.status==='ok'?'✓':c.status==='warning'?'!':'×'}</span><div><b>{c.label}</b><small>{c.detail}</small></div><span className="check-state">{c.status==='ok'?'Ready':c.status==='warning'?'Check':'Missing'}</span></div>):<div className="check-empty">Download the local worker above and run START DIEHL VIN.cmd once on this Windows computer.</div>}
        {workerReady&&<div className={'check-row '+(dtnaReady?'ok':'warning')}><span className="check-icon">{dtnaReady?'✓':'!'}</span><div><b>Your DTNA login</b><small>{dtnaReady?'Initialized for this browser/Windows user.':'Required before DTNA Sync or VIN lookup.'}</small></div><span className="check-state">{dtnaReady?'Ready':'Login required'}</span></div>}
      </div>
    </section>

    <section className="setup-grid">
      <article className="setup-card featured"><div className="step-num">1</div><h2>Download + run once</h2><p>The launcher installs the local worker and connects the shared workbook.</p></article>
      <article className="setup-card"><div className="step-num">2</div><h2>Initialize your DTNA login</h2><p>Every employee signs into DTNA with their own username/password/MFA.</p></article>
      <article className="setup-card"><div className="step-num">3</div><h2>Use the platform</h2><p>The shared workbook is common, while each user’s DTNA session stays local to their Windows account.</p></article>
    </section>

    <section style={{display:'flex',justifyContent:'center',gap:12,margin:'24px 0 40px'}}>
      <Link className="button-primary" aria-disabled={!ready} href={ready?'/vin-inservice':'/'} style={!ready?{pointerEvents:'none',opacity:.45}:{}}>Start</Link>
      <Link className="button-secondary" href="/dtna">DTNA</Link>
    </section>
  </main>
}
