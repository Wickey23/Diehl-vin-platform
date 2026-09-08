'use client';

import {useEffect, useState} from 'react';
import { AppShell } from '../../components/app-shell';

const LOCAL_DB='http://127.0.0.1:8766';

type RunItem={id:string;type:string;filename:string;size:number;modified:string};

function sizeText(bytes:number){
  if(bytes<1024)return `${bytes} B`;
  if(bytes<1024*1024)return `${(bytes/1024).toFixed(1)} KB`;
  return `${(bytes/(1024*1024)).toFixed(1)} MB`;
}

export default function HistoryPage(){
  const [runs,setRuns]=useState<RunItem[]>([]);
  const [workbook,setWorkbook]=useState('');
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState('');

  async function load(){
    setLoading(true);setError('');
    try{
      const r=await fetch(`${LOCAL_DB}/runs`,{cache:'no-store'});
      if(!r.ok)throw new Error('Local worker could not return run history.');
      const data=await r.json();
      setRuns(data.runs||[]);setWorkbook(data.workbook||'');
    }catch(e:any){
      setRuns([]);setError(e?.message||'Could not load run history.');
    }finally{setLoading(false)}
  }

  useEffect(()=>{load()},[]);

  return <AppShell>
    <div className="page-title">
      <p className="eyebrow">RUN ARCHIVE</p>
      <h1>Export Runs</h1>
      <p>Every successful DTNA run from this computer is archived as its own Excel file.</p>
    </div>

    {workbook&&<div className="notice good"><b>Current source workbook:</b> {workbook}</div>}
    {error&&<div className="notice">{error} Make sure Local Worker is running, then try again.</div>}

    <section className="panel">
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:12,marginBottom:16}}>
        <div><h2 style={{margin:0}}>Saved DTNA Runs</h2><p style={{margin:'6px 0 0'}}>{runs.length} archived run{runs.length===1?'':'s'} on this computer.</p></div>
        <button onClick={load} disabled={loading}>{loading?'Loading…':'Refresh'}</button>
      </div>

      {!loading&&!runs.length&&!error&&<div className="check-empty">No archived DTNA runs yet. Complete a DTNA Sync and the Excel export will appear here automatically.</div>}

      <div className="timeline">
        {runs.map(run=><div className="timeline-item" key={run.id} style={{display:'flex',justifyContent:'space-between',gap:16,alignItems:'center'}}>
          <div>
            <b>{run.type} · {run.modified}</b>
            <div>{run.filename} · {sizeText(run.size)}</div>
          </div>
          <a className="button-primary" href={`${LOCAL_DB}/runs/download/${encodeURIComponent(run.filename)}`}>Download Excel</a>
        </div>)}
      </div>
    </section>
  </AppShell>
}
