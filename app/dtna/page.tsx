'use client';

import { useEffect, useState } from 'react';

type DtnaStatus={status?:string;lastRun?:string;orderCount?:string;vinCount?:string;inServiceDateCount?:string;changeCount?:string;loginProfile?:string;message?:string;running?:boolean};

export default function DtnaPage(){
  const[url,setUrl]=useState('');const[key,setKey]=useState('');const[status,setStatus]=useState<DtnaStatus>({});const[msg,setMsg]=useState('Connect the Windows worker to begin.');const[busy,setBusy]=useState(false);
  useEffect(()=>{setUrl(localStorage.getItem('diehlWorkerUrl')||'');setKey(localStorage.getItem('diehlWorkerKey')||'')},[]);
  async function wf(path:string,init:RequestInit={}){if(!url||!key)throw new Error('Run the Initializer and connect the Windows worker first.');const r=await fetch(url.replace(/\/$/,'')+path,{...init,headers:{'content-type':'application/json','x-worker-key':key,...(init.headers||{})}});const d=await r.json().catch(()=>({}));if(!r.ok)throw new Error(d.detail||d.error||'Worker request failed');return d}
  async function refresh(){try{const d=await wf('/dtna/status');setStatus(d);setMsg(d.running?'DTNA automation is running.':'DTNA worker is ready.')}catch(e:any){setMsg(e.message)}}
  useEffect(()=>{if(url&&key)refresh()},[url,key]);
  useEffect(()=>{const t=setInterval(()=>{if(url&&key)refresh()},4000);return()=>clearInterval(t)},[url,key]);
  async function action(path:string,label:string){setBusy(true);try{const d=await wf(path,{method:'POST'});setMsg(d.message||label);setTimeout(refresh,1200)}catch(e:any){setMsg(e.message)}finally{setBusy(false)}}
  return <main className="dtna-page">
    <section className="dtna-hero"><div><span className="kicker">FREIGHTLINER / DTNA</span><h1>DTNA Sales Order + AUTO VIN</h1><p>This page controls the local DTNA automation. DTNA login and MFA stay on the initialized Windows computer; downloaded Sales Order and AUTO VIN data is written locally.</p></div><div className={'dtna-live '+(status.running?'running':'')}>{status.running?'● DTNA running':'○ Ready'}</div></section>
    <section className="dtna-actions"><button onClick={()=>action('/dtna/open','DTNA browser opened')} disabled={busy}>Open / Login to DTNA</button><button className="primary-action" onClick={()=>action('/dtna/sync','DTNA sync started')} disabled={busy}>Run Sales Order + AUTO VIN Sync</button><button onClick={refresh} disabled={busy}>Refresh status</button></section>
    <div className="dtna-message">{msg}</div>
    <section className="dtna-stats"><article><span>Status</span><strong>{status.status||'Not run yet'}</strong></article><article><span>Orders</span><strong>{status.orderCount||'—'}</strong></article><article><span>VINs matched</span><strong>{status.vinCount||'—'}</strong></article><article><span>In-Service dates</span><strong>{status.inServiceDateCount||'—'}</strong></article><article><span>Changes</span><strong>{status.changeCount||'—'}</strong></article></section>
    <section className="dtna-grid"><article className="dtna-card"><h2>How this tab runs</h2><ol><li>Opens the persistent Edge/Chromium DTNA profile.</li><li>You complete login or MFA when DTNA requires it.</li><li>The worker downloads Sales Order rows using the logged-in browser session.</li><li>Dealer Reporting opens and selects the saved <b>AUTO VIN</b> template.</li><li>The widest Order Received Date range is selected.</li><li>VIN and In-Service Date are merged with Sales Order records.</li><li>Excel output and change history are updated locally.</li></ol></article><article className="dtna-card"><h2>Local DTNA state</h2><dl><dt>Last run</dt><dd>{status.lastRun||'—'}</dd><dt>Browser profile</dt><dd>{status.loginProfile||'Created after first run'}</dd><dt>Last message</dt><dd>{status.message||'—'}</dd></dl><p className="dtna-note">If DTNA requests MFA, the local browser window will remain open for you. After authentication, the automation continues from the same session.</p></article></section>
  </main>
}
