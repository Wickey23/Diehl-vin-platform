'use client';
import {useEffect,useMemo,useState} from 'react';

type Item={id:string;vin:string;status:string;attempts:number;result:any;error_message?:string};
type Batch={id:string;status:string;total_vins:number;lookup_mode:string;created_at:string;options:any};
type Worker={worker_id:string;hostname:string;dtna_status:string;master_workbook:string;last_seen:string;details:any};

const LOCAL='http://127.0.0.1:8765';
const modes=[['in_service_customer','In-Service + Customer — recommended'],['fast_in_service','Fast In-Service — date and mileage only'],['full_warranty','Full Warranty Audit — all details']];

export default function Checker(){
  const[text,setText]=useState('');const[mode,setMode]=useState('in_service_customer');const[workers,setWorkers]=useState(1);const[batch,setBatch]=useState<Batch|null>(null);const[items,setItems]=useState<Item[]>([]);const[worker,setWorker]=useState<Worker|null>(null);const[online,setOnline]=useState(false);const[busy,setBusy]=useState(false);const[msg,setMsg]=useState('Ready to check');
  const vins=useMemo(()=>[...new Set(text.split(/[\s,;]+/).map(x=>x.trim().toUpperCase()).filter(x=>x))],[text]);

  async function local(path:string,init:RequestInit={}){
    const r=await fetch(LOCAL+path,{...init,cache:'no-store',headers:{'content-type':'application/json',...(init.headers||{})}});
    const d=await r.json().catch(()=>({}));
    if(!r.ok)throw new Error(d.detail||d.error||'Local worker request failed');
    return d;
  }

  async function refresh(id=batch?.id){
    try{
      const w=await local('/health');setWorker(w.worker||null);setOnline(true);
      if(id){const d=await local('/batches/'+id);if(d.batch){setBatch(d.batch);setItems(d.items||[])}}
    }catch(e:any){setWorker(null);setOnline(false);setMsg('Local Diehl worker is not running. Run the initializer once on this computer.')}
  }

  useEffect(()=>{local('/batches/resumable').then(d=>{if(d.batch){setBatch(d.batch);refresh(d.batch.id)}}).catch(()=>{});refresh()},[]);
  useEffect(()=>{const t=setInterval(()=>refresh(),2000);return()=>clearInterval(t)},[batch?.id]);

  async function start(){
    setBusy(true);setMsg('Starting on this computer…');
    try{
      const d=await local('/batches',{method:'POST',body:JSON.stringify({vins:text,lookupMode:mode,workers,batchSize:100,retryRounds:3,batchPause:.5,retryPause:3})});
      setBatch({id:d.batchId,status:'queued',total_vins:d.total,lookup_mode:mode,created_at:new Date().toISOString(),options:{}});setItems([]);setText('');setMsg('Started — this computer is processing the VINs');await refresh(d.batchId)
    }catch(e:any){setMsg(e.message)}finally{setBusy(false)}
  }

  async function retry(){if(!batch)return;await local(`/batches/${batch.id}/retry`,{method:'POST'});setMsg('Errors queued for retry');refresh()}
  async function cancel(){if(!batch)return;await local(`/batches/${batch.id}/cancel`,{method:'POST'});setMsg('Batch cancelled');refresh()}
  async function openDtna(){try{await local('/dtna/open',{method:'POST'});setMsg('DTNA opened locally. Complete login/MFA if requested.')}catch(e:any){setMsg(e.message)}}

  function exportCsv(){if(!items.length)return;const esc=(v:any)=>'"'+String(v??'').replaceAll('"','""')+'"';const lines=[['VIN','Status','In-Service Date','Mileage','Customer','Registered Customer','Error'].join(','),...items.map(i=>[i.vin,i.status,i.result?.inServiceDate,i.result?.mileage,i.result?.customerName,i.result?.registeredCustomerName,i.error_message].map(esc).join(','))];const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([lines.join('\n')],{type:'text/csv'}));a.download='vin-results.csv';a.click();URL.revokeObjectURL(a.href)}

  const done=items.filter(i=>i.status==='complete').length,errors=items.filter(i=>i.status==='error').length,running=items.filter(i=>i.status==='running').length,pct=batch?Math.round(((done+errors)/Math.max(1,batch.total_vins))*100):0;

  return <div className="checker">
    <div className="hero"><div><div className="brandline">VIN IN-SERVICE CHECKER · FREIGHTLINER / DTNA</div><h1>VIN In-Service</h1><p>The shared website uses the worker on this computer only. DTNA session and Excel remain local.</p></div><div className="pill">{online?'● This computer ready':'○ Initializer required'}</div></div>
    <div className="layout">
      <section className="card"><div className="cardhead"><span>VIN list</span><span className="muted">{vins.length} VINs</span></div><div className="pad">
        <div className="group"><label>Lookup mode</label><select value={mode} onChange={e=>setMode(e.target.value)}>{modes.map(m=><option key={m[0]} value={m[0]}>{m[1]}</option>)}</select></div>
        <label>Paste VINs</label><textarea value={text} onChange={e=>setText(e.target.value)} placeholder="One VIN per line, or separated by commas"/>
        <div className="row" style={{marginTop:12}}><button className="primary wide" disabled={busy||!vins.length||!online} onClick={start}>{busy?'Starting…':'Start'}</button><button className="ghost" onClick={()=>setText('')}>Clear</button></div>
        <div className="divider"/>
        <label>Parallel DTNA browser workers</label><select value={workers} onChange={e=>setWorkers(+e.target.value)}>{[1,2,3,4,5,6,7,8].map(n=><option key={n}>{n}</option>)}</select>
        <div className="workerbox"><b>This computer</b><p className="help">{online?`${worker?.hostname} · ${worker?.master_workbook||'No workbook selected'}`:'Run the initializer package once.'}</p><button className="ghost" onClick={openDtna} disabled={!online}>Open DTNA / Login</button></div>
      </div></section>

      <section className="card results"><div className="cardhead"><span>Results</span><span className="muted">{batch?`${done} verified · ${errors} errors · ${running} running`:'No active batch'}</span></div>
        <div className="actions"><button className="ghost" onClick={retry} disabled={!errors}>Retry Errors</button><button className="danger" onClick={cancel} disabled={!batch||batch.status==='complete'||batch.status==='cancelled'}>Cancel</button><button className="ghost" onClick={exportCsv} disabled={!items.length}>Export CSV</button></div>
        <div className="statusbar"><span>{msg}</span><b>{batch?`${pct}%`:''}</b></div><div className="progress"><span style={{width:pct+'%'}}/></div>
        {!items.length?<div className="empty"><div><b>No VINs checked yet</b><p>Paste VINs and press Start.</p></div></div>:<div className="tablewrap"><table><thead><tr><th>VIN</th><th>Status</th><th>In-Service Date</th><th>Mileage</th><th>Customer</th><th>Registered Customer</th><th>Attempts</th></tr></thead><tbody>{items.map(i=><tr key={i.id}><td>{i.vin}</td><td className={i.status==='complete'?'ok':i.status==='error'?'err':'run'}>{i.status}{i.error_message?<div className="help">{i.error_message}</div>:null}</td><td>{i.result?.inServiceDate||'—'}</td><td>{i.result?.mileage||'—'}</td><td>{i.result?.customerName||'—'}</td><td>{i.result?.registeredCustomerName||'—'}</td><td>{i.attempts||0}</td></tr>)}</tbody></table></div>}
      </section>
    </div>
  </div>
}
