'use client';

import Link from 'next/link';
import {useEffect,useState} from 'react';

const LOCAL='http://127.0.0.1:8765';

type Check={id:string;label:string;status:'ok'|'warning'|'missing';detail:string};

export default function Initializer(){
  const [worker,setWorker]=useState<any>(null);
  const [checks,setChecks]=useState<Check[]>([]);
  const [ready,setReady]=useState(false);
  const [checking,setChecking]=useState(false);
  const [message,setMessage]=useState('Checking this computer…');

  async function check(){
    setChecking(true);
    try{
      const h=await fetch(`${LOCAL}/health`,{cache:'no-store'});
      if(!h.ok) throw new Error('Worker not responding');
      const hd=await h.json();
      const s=await fetch(`${LOCAL}/initializer/status`,{cache:'no-store'});
      if(!s.ok) throw new Error('Could not read initializer status');
      const sd=await s.json();
      setWorker(hd.worker||null);setChecks(sd.checks||[]);setReady(!!sd.ready);
      setMessage(sd.ready?'This computer is initialized. Press Start.':'The worker is installed, but one or more required items need attention.');
    }catch{
      setWorker(null);setChecks([]);setReady(false);
      setMessage('Worker not detected. Download the local worker below, extract it, and double-click START DIEHL VIN.cmd once.');
    }finally{setChecking(false)}
  }

  useEffect(()=>{check();const t=setInterval(check,5000);return()=>clearInterval(t)},[]);

  async function chooseWorkbook(){
    try{await fetch(`${LOCAL}/workbook/select`,{method:'POST'});setMessage('The Excel workbook picker opened on this computer. Choose the workbook, then press Check again.')}catch{setMessage('Worker is not available on this computer.')}
  }

  return <main className="initializer-page">
    <section className="initializer-hero">
      <div><span className="kicker">THIS COMPUTER</span><h1>Diehl VIN Initializer</h1><p>Each user initializes their own Windows computer once. After that, the website automatically uses the DTNA session and Excel workbook on that same computer.</p></div>
      <div className={'readiness '+(ready?'ready':'')}>{ready?'READY':'SETUP REQUIRED'}</div>
    </section>

    {!ready&&<section className="download-card">
      <div><span className="kicker">ONE-TIME SETUP</span><h2>Download the local worker</h2><p>Download one ZIP from this website. Extract it, then double-click <b>START DIEHL VIN.cmd</b>. The launcher handles first-time setup, workbook selection, worker startup, duplicate-worker detection, and opens this site automatically.</p></div>
      <div className="download-actions"><a className="download-primary" href="/api/download-worker">Download Local Worker</a><small>After download: Extract → double-click START DIEHL VIN.cmd</small></div>
    </section>}

    <section className="connection-card">
      <div><span className="kicker">AUTOMATIC LOCAL DETECTION</span><h2>{worker?`Connected to ${worker.hostname}`:'Worker not detected'}</h2><p>{message}</p>{worker?.master_workbook&&<p><b>Active workbook:</b> {worker.master_workbook}</p>}</div>
      <div className="row"><button onClick={check} disabled={checking}>{checking?'Checking…':'Check again'}</button><button className="button-secondary" onClick={chooseWorkbook} disabled={!worker}>Change workbook</button></div>
    </section>

    <section className="prereq-card">
      <div className="prereq-head"><div><span className="kicker">SYSTEM CHECK</span><h2>Everything needed on this PC</h2></div></div>
      <div className="check-list">
        {checks.length?checks.map(c=><div className={'check-row '+c.status} key={c.id}><span className="check-icon">{c.status==='ok'?'✓':c.status==='warning'?'!':'×'}</span><div><b>{c.label}</b><small>{c.detail}</small></div><span className="check-state">{c.status==='ok'?'Ready':c.status==='warning'?'Check':'Missing'}</span></div>):<div className="check-empty">Download the local worker above and run START DIEHL VIN.cmd once on this Windows computer.</div>}
      </div>
    </section>

    <section className="setup-grid">
      <article className="setup-card featured"><div className="step-num">1</div><h2>Download + run once</h2><p>Download from this page, extract the ZIP, and double-click START DIEHL VIN.cmd. No command prompt typing is required.</p></article>
      <article className="setup-card"><div className="step-num">2</div><h2>Then just press Start</h2><p>The launcher remembers the workbook and opens this site. If the worker is already running, it simply opens the website.</p></article>
      <article className="setup-card"><div className="step-num">3</div><h2>Use your own DTNA + Excel</h2><p>DTNA login/MFA and workbook stay on this computer.</p></article>
    </section>

    <section style={{display:'flex',justifyContent:'center',gap:12,margin:'24px 0 40px'}}>
      <Link className="button-primary" aria-disabled={!ready} href={ready?'/vin-inservice':'/'} style={!ready?{pointerEvents:'none',opacity:.45}:{}}>Start</Link>
      <Link className="button-secondary" href="/dtna">DTNA</Link>
    </section>
  </main>
}
