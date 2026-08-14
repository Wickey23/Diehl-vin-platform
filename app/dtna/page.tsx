'use client';

import {useEffect,useState} from 'react';

const LOCAL='http://127.0.0.1:8765';

export default function DtnaPage(){
  const [worker,setWorker]=useState<any>(null);
  const [status,setStatus]=useState<any>(null);
  const [online,setOnline]=useState(false);
  const [msg,setMsg]=useState('Checking this computer…');

  async function local(path:string,init:RequestInit={}){
    const r=await fetch(LOCAL+path,{...init,cache:'no-store',headers:{'content-type':'application/json',...(init.headers||{})}});
    const d=await r.json().catch(()=>({}));
    if(!r.ok)throw new Error(d.detail||d.error||'Local worker request failed');
    return d;
  }

  async function refresh(){
    try{
      const h=await local('/health');
      const s=await local('/dtna/status');
      setWorker(h.worker||null);setStatus(s);setOnline(true);setMsg('DTNA worker is ready on this computer.');
    }catch{
      setWorker(null);setStatus(null);setOnline(false);setMsg('Run the Diehl initializer once on this Windows computer.');
    }
  }

  useEffect(()=>{refresh();const t=setInterval(refresh,4000);return()=>clearInterval(t)},[]);

  async function run(path:string,success:string){
    try{setMsg('Starting locally…');await local(path,{method:'POST'});setMsg(success);setTimeout(refresh,1200)}catch(e:any){setMsg(e.message)}
  }

  return <main className="dtna-page">
    <section className="dtna-hero">
      <div><span className="kicker">FREIGHTLINER / DTNA</span><h1>DTNA Sales Order + AUTO VIN</h1><p>The browser, login/MFA, profile, and Excel files stay on this Windows computer. The website only tells the local worker what to start.</p></div>
      <div className={'dtna-live '+(online?'running':'')}>{online?'● This computer ready':'○ Initializer required'}</div>
    </section>
    <section className="dtna-actions">
      <button onClick={()=>run('/dtna/open','DTNA login browser opened locally.')} disabled={!online}>Open / Login to DTNA</button>
      <button className="primary-action" onClick={()=>run('/dtna/sync','Sales Order + AUTO VIN sync started locally.')} disabled={!online}>Start DTNA Sync</button>
      <button onClick={refresh}>Refresh</button>
    </section>
    <div className="dtna-message">{msg}</div>
    <section className="dtna-grid">
      <article className="dtna-card"><h2>This computer</h2><dl><dt>Computer</dt><dd>{worker?.hostname||'—'}</dd><dt>Workbook</dt><dd>{worker?.master_workbook||'—'}</dd><dt>DTNA status</dt><dd>{worker?.dtna_status||'—'}</dd><dt>Persistent profile</dt><dd>{status?.profile||'—'}</dd></dl></article>
      <article className="dtna-card"><h2>How it works</h2><p>Initialize this computer once. After that, pressing Start here launches the local DTNA automation using the saved browser profile. If DTNA requests MFA, finish it in the browser window; the profile remains local for future runs.</p></article>
    </section>
  </main>
}
