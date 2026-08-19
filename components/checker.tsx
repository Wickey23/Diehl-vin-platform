'use client';
import {useEffect,useMemo,useState} from 'react';

type Item={id:string;vin:string;status:string;attempts:number;result:any;error_message?:string};
type Batch={id:string;status:string;total_vins:number;lookup_mode:string;created_at:string;options:any};
type Worker={worker_id:string;hostname:string;dtna_status:string;master_workbook:string;last_seen:string;details:any};

const LOCAL='http://127.0.0.1:8765';
const REQUIRED_WORKER='5.16';
const modes=[['in_service_customer','In-Service + Customer — recommended'],['fast_in_service','Fast In-Service — date and mileage only'],['full_warranty','Full Warranty Audit — coverage + components']];

function versionParts(v:string){return String(v||'').split('.').map(x=>Number(x)||0)}
function versionAtLeast(actual:string,required:string){const a=versionParts(actual),b=versionParts(required);for(let i=0;i<Math.max(a.length,b.length);i++){const av=a[i]||0,bv=b[i]||0;if(av>bv)return true;if(av<bv)return false}return true}

export default function Checker(){
  const[text,setText]=useState('');const[mode,setMode]=useState('in_service_customer');const[workers,setWorkers]=useState(1);const[batch,setBatch]=useState<Batch|null>(null);const[items,setItems]=useState<Item[]>([]);const[worker,setWorker]=useState<Worker|null>(null);const[workerVersion,setWorkerVersion]=useState('');const[online,setOnline]=useState(false);const[busy,setBusy]=useState(false);const[msg,setMsg]=useState('Ready to check in OWL');
  const vins=useMemo(()=>[...new Set(text.split(/[\s,;]+/).map(x=>x.trim().toUpperCase()).filter(x=>x))],[text]);
  const currentWorker=online&&versionAtLeast(workerVersion,REQUIRED_WORKER);

  async function local(path:string,init:RequestInit={}){
    const r=await fetch(LOCAL+path,{...init,cache:'no-store',headers:{'content-type':'application/json',...(init.headers||{})}});
    const d=await r.json().catch(()=>({}));
    if(!r.ok)throw new Error(d.detail||d.error||'Local worker request failed');
    return d;
  }

  async function workerReachable(){
    const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),1200);
    try{const r=await fetch(LOCAL+'/openapi.json',{cache:'no-store',signal:controller.signal});return r.ok}catch{return false}finally{clearTimeout(timer)}
  }

  async function healthDetails(){
    const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),1200);
    try{const r=await fetch(LOCAL+'/health',{cache:'no-store',signal:controller.signal});if(!r.ok)return null;return await r.json()}catch{return null}finally{clearTimeout(timer)}
  }

  async function refresh(id=batch?.id){
    const reachable=await workerReachable();
    if(!reachable){setWorker(null);setWorkerVersion('');setOnline(false);setMsg('Local Diehl worker is not running. Press START DIEHL VIN on this computer.');return}
    setOnline(true);const h=await healthDetails();if(h?.worker)setWorker(h.worker);if(h?.version)setWorkerVersion(String(h.version));
    if(h?.version&&!versionAtLeast(String(h.version),REQUIRED_WORKER))setMsg(`Worker v${h.version} is running, but VIN In-Service requires v${REQUIRED_WORKER} or newer. Download the update, STOP ALL DIEHL, then START DIEHL VIN.`);
    if(id){try{const d=await local('/batches/'+id);if(d.batch){setBatch(d.batch);setItems(d.items||[])}}catch(e:any){setMsg(e.message||'Worker is running, but batch status could not be loaded.')}}
  }

  useEffect(()=>{local('/batches/resumable').then(d=>{if(d.batch){setBatch(d.batch);refresh(d.batch.id)}}).catch(()=>{});refresh()},[]);
  useEffect(()=>{const t=setInterval(()=>refresh(),1000);return()=>clearInterval(t)},[batch?.id]);

  async function start(){
    setBusy(true);setMsg('Checking local worker version…');
    try{
      const h=await healthDetails();const actual=String(h?.version||'');
      if(!actual)throw new Error('Could not read the local worker version. Restart START DIEHL VIN.');
      setWorkerVersion(actual);
      if(!versionAtLeast(actual,REQUIRED_WORKER))throw new Error(`This computer is running worker v${actual}. Start OWL Check requires v${REQUIRED_WORKER} or newer. Download the latest worker, run STOP ALL DIEHL, then START DIEHL VIN.`);
      setMsg('Starting live OWL lookup on this computer…');
      const d=await local('/batches',{method:'POST',body:JSON.stringify({vins:text,lookupMode:mode,workers,batchSize:100,retryRounds:3,batchPause:.5,retryPause:3})});
      if(d.execution!=='direct')throw new Error(`The local worker did not accept direct OWL execution. It appears stale even though it reports v${actual}. Reinstall the latest worker package.`);
      setBatch({id:d.batchId,status:'direct_running',total_vins:d.total,lookup_mode:mode,created_at:new Date().toISOString(),options:{execution:'direct'}});setItems([]);setText('');setMsg('OWL launch accepted — waiting for the local browser to open…');
      await new Promise(r=>setTimeout(r,250));await refresh(d.batchId)
    }catch(e:any){setMsg(e.message)}finally{setBusy(false)}
  }

  async function retry(){if(!batch)return;await local(`/batches/${batch.id}/retry`,{method:'POST'});setMsg('Errors queued for a fresh OWL retry');refresh()}
  async function cancel(){if(!batch)return;await local(`/batches/${batch.id}/cancel`,{method:'POST'});setMsg('Batch cancelled');refresh()}
  async function openOwl(){try{await local('/owl/open',{method:'POST'});setMsg('OWL opened at Freightliner Online Warranty Link. Complete your login/MFA if requested; leave the OWL Home page visible.')}catch(e:any){setMsg(e.message)}}

  function exportCsv(){
    if(!items.length)return;
    const esc=(v:any)=>'"'+String(v??'').replaceAll('"','""')+'"';
    const headers=['VIN','Status','In-Service Date','Mileage','Customer','Registered Customer','Warranty Status','Engine Serial Number','Allison Transmission Serial Number','Source','Error'];
    const lines=[headers.join(','),...items.map(i=>[i.vin,i.status,i.result?.inServiceDate,i.result?.mileage,i.result?.customerName,i.result?.registeredCustomerName,i.result?.warrantyStatus,i.result?.engineSerialNumber,i.result?.allisonTransmissionSerialNumber,i.result?.source,i.error_message].map(esc).join(','))];
    const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([lines.join('\n')],{type:'text/csv'}));a.download='vin-results.csv';a.click();URL.revokeObjectURL(a.href)
  }

  const done=items.filter(i=>i.status==='complete').length,errors=items.filter(i=>i.status==='error').length,running=items.filter(i=>i.status==='running').length,pct=batch?Math.round(((done+errors)/Math.max(1,batch.total_vins))*100):0;

  return <div className="checker">
    <div className="hero"><div><div className="brandline">VIN IN-SERVICE CHECKER · FREIGHTLINER / OWL</div><h1>VIN In-Service</h1><p>Each VIN is checked in OWL Coverage Info / Check Coverage, Major Components, and Product Registration, then written to the shared Excel database. Your Freightliner/OWL session stays local.</p></div><div className="pill">{online?`● This computer ready · v${workerVersion||'?'}`:'○ Initializer required'}</div></div>
    <div className="layout">
      <section className="card"><div className="cardhead"><span>VIN list</span><span className="muted">{vins.length} VINs</span></div><div className="pad">
        <div className="group"><label>Lookup mode</label><select value={mode} onChange={e=>setMode(e.target.value)}>{modes.map(m=><option key={m[0]} value={m[0]}>{m[1]}</option>)}</select></div>
        <label>Paste VINs</label><textarea value={text} onChange={e=>setText(e.target.value)} placeholder="One VIN per line, or separated by commas"/>
        <div className="row" style={{marginTop:12}}><button className="primary wide" disabled={busy||!vins.length||!currentWorker} onClick={start}>{busy?'Starting…':'Start OWL Check'}</button><button className="ghost" onClick={()=>setText('')}>Clear</button></div>
        {online&&!currentWorker?<p className="help" style={{marginTop:8,color:'#b42318'}}>Worker v{workerVersion||'?'} is too old. VIN In-Service requires v{REQUIRED_WORKER}+.</p>:null}
        <div className="divider"/>
        <label>Parallel OWL browser workers</label><select value={workers} onChange={e=>setWorkers(+e.target.value)}>{[1,2,3,4,5,6,7,8].map(n=><option key={n}>{n}</option>)}</select>
        <div className="workerbox"><b>This computer · Worker v{workerVersion||'?'}</b><p className="help">{online?`${worker?.hostname||'Local worker'} · ${worker?.master_workbook||'Worker connected'}`:'Press START DIEHL VIN on this computer.'}</p><button className="ghost" onClick={openOwl} disabled={!online}>Open OWL / Login</button></div>
      </div></section>

      <section className="card results"><div className="cardhead"><span>Results</span><span className="muted">{batch?`${done} verified · ${errors} errors · ${running} running`:'No active batch'}</span></div>
        <div className="actions"><button className="ghost" onClick={retry} disabled={!errors}>Retry Errors</button><button className="danger" onClick={cancel} disabled={!batch||batch.status==='complete'||batch.status==='cancelled'}>Cancel</button><button className="ghost" onClick={exportCsv} disabled={!items.length}>Export CSV</button></div>
        <div className="statusbar"><span>{msg}</span><b>{batch?`${pct}%`:''}</b></div><div className="progress"><span style={{width:pct+'%'}}/></div>
        {!items.length?<div className="empty"><div><b>No VINs checked yet</b><p>Paste VINs and press Start OWL Check.</p></div></div>:<div className="tablewrap"><table><thead><tr><th>VIN</th><th>Status</th><th>In-Service Date</th><th>Mileage</th><th>Customer</th><th>Warranty</th><th>Engine Serial</th><th>Allison Serial</th><th>Attempts</th></tr></thead><tbody>{items.map(i=><tr key={i.id}><td>{i.vin}</td><td className={i.status==='complete'?'ok':i.status==='error'?'err':'run'}>{i.status}{i.error_message?<div className="help">{i.error_message}</div>:null}</td><td>{i.result?.inServiceDate||'—'}</td><td>{i.result?.mileage||'—'}</td><td>{i.result?.customerName||'—'}</td><td>{i.result?.warrantyStatus||'—'}</td><td>{i.result?.engineSerialNumber||'—'}</td><td>{i.result?.allisonTransmissionSerialNumber||'—'}</td><td>{i.attempts||0}</td></tr>)}</tbody></table></div>}
      </section>
    </div>
  </div>
}
