'use client';

import {useEffect,useState} from 'react';

const WORKER='http://127.0.0.1:8765';
const CONTROL='http://127.0.0.1:8766';
const LOGIN_KEY='diehl-dtna-login-initialized-v1';

export default function DtnaPage(){
  const [worker,setWorker]=useState<any>(null);
  const [status,setStatus]=useState<any>(null);
  const [online,setOnline]=useState(false);
  const [loginInitialized,setLoginInitialized]=useState(false);
  const [msg,setMsg]=useState('Checking this computer…');

  async function local(base:string,path:string,init:RequestInit={}){
    const r=await fetch(base+path,{...init,cache:'no-store',headers:{'content-type':'application/json',...(init.headers||{})}});
    const d=await r.json().catch(()=>({}));
    if(!r.ok)throw new Error(d.detail||d.error||'Local worker request failed');
    return d;
  }

  async function refresh(){
    try{
      const p=await fetch(WORKER+'/ping',{cache:'no-store'});
      const c=await fetch(CONTROL+'/ping',{cache:'no-store'});
      if(!p.ok||!c.ok) throw new Error('Worker not responding');
      const h=await local(WORKER,'/health');
      const s=await local(CONTROL,'/dtna/status');
      const initialized=typeof window!=='undefined'&&localStorage.getItem(LOGIN_KEY)==='yes';
      setWorker(h.worker||null);setStatus(s);setOnline(true);setLoginInitialized(initialized);
      setMsg(initialized?'This computer is connected and your DTNA login has been initialized.':'This worker is connected. Initialize YOUR DTNA login before using DTNA Sync.');
    }catch{
      setWorker(null);setStatus(null);setOnline(false);setLoginInitialized(false);setMsg('Run the current Diehl initializer once on this Windows computer.');
    }
  }

  useEffect(()=>{refresh();const t=setInterval(refresh,4000);return()=>clearInterval(t)},[]);

  async function initializeLogin(){
    try{
      setMsg('Opening DTNA locally through the fixed runtime. Sign in with YOUR DTNA username/password and complete MFA.');
      await local(CONTROL,'/dtna/open',{method:'POST'});
      if(typeof window!=='undefined')localStorage.setItem(LOGIN_KEY,'yes');
      setLoginInitialized(true);
      setMsg('DTNA login window opened. Complete YOUR login/MFA there. This PC will keep that session locally for future runs.');
    }catch(e:any){setMsg(e.message)}
  }

  function resetLogin(){
    if(typeof window!=='undefined')localStorage.removeItem(LOGIN_KEY);
    setLoginInitialized(false);
    setMsg('DTNA login initialization was reset for this browser. Press Initialize My DTNA Login to sign in again.');
  }

  async function runSync(){
    if(!loginInitialized){setMsg('Initialize YOUR DTNA login first.');return}
    try{
      setMsg('Starting Sales Order + AUTO VIN sync through the fixed DTNA runtime…');
      await local(CONTROL,'/dtna/sync',{method:'POST'});
      setMsg('Sales Order + AUTO VIN sync started locally. Successful completion writes the DTNA sheet in the shared Excel database.');
    }catch(e:any){setMsg(e.message)}
  }

  return <main className="dtna-page">
    <section className="dtna-hero">
      <div><span className="kicker">FREIGHTLINER / DTNA</span><h1>DTNA Sales Order + AUTO VIN</h1><p>Every employee uses their own local DTNA login/MFA. DTNA credentials, cookies, and browser profile stay on that Windows user account and are never included in the downloaded worker package.</p></div>
      <div className={'dtna-live '+(online&&loginInitialized?'running':'')}>{!online?'○ Initializer required':loginInitialized?'● Your DTNA login initialized':'○ DTNA login required'}</div>
    </section>

    {online&&!loginInitialized&&<section className="download-card">
      <div><span className="kicker">REQUIRED FOR EACH USER</span><h2>Initialize your DTNA login</h2><p>Do not use another employee’s saved DTNA session. Open DTNA locally and sign in with <b>your own</b> DTNA username/password and MFA. The session stays only in your Windows profile.</p></div>
      <div className="download-actions"><button className="download-primary" onClick={initializeLogin}>Initialize My DTNA Login</button><small>Complete login/MFA in the DTNA browser window that opens.</small></div>
    </section>}

    <section className="dtna-actions">
      <button onClick={initializeLogin} disabled={!online}>{loginInitialized?'Open / Refresh My DTNA Login':'Initialize My DTNA Login'}</button>
      <button className="primary-action" onClick={runSync} disabled={!online||!loginInitialized}>Start DTNA Sync</button>
      <button onClick={refresh}>Refresh</button>
      <button onClick={resetLogin} disabled={!online}>Reset DTNA Login Setup</button>
    </section>
    <div className="dtna-message">{msg}</div>
    <section className="dtna-grid">
      <article className="dtna-card"><h2>This computer</h2><dl><dt>Computer</dt><dd>{worker?.hostname||'—'}</dd><dt>Workbook</dt><dd>{worker?.master_workbook||'—'}</dd><dt>DTNA login</dt><dd>{loginInitialized?'Initialized for this user':'Required'}</dd><dt>Persistent profile</dt><dd>{status?.profile||'—'}</dd><dt>DTNA runtime</dt><dd>{status?.runtime||'—'}</dd></dl></article>
      <article className="dtna-card"><h2>Per-user security</h2><p>The worker package contains no DTNA cookies or credentials. Each Windows user initializes their own local browser profile. If DTNA expires the session or requests MFA again, use <b>Open / Refresh My DTNA Login</b> and complete authentication locally.</p></article>
    </section>
  </main>
}
