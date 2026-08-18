'use client';

import {useEffect,useMemo,useRef,useState} from 'react';

const LOCAL_DB='http://127.0.0.1:8766';
const SHEETS=['DTNA','VIN In-Service'] as const;
type SheetName=typeof SHEETS[number];
type Row=Record<string,unknown>;
type Payload={sheet:string;workbook:string;headers:string[];rows:Row[];rowCount:number;returned?:number;exists:boolean;readMode?:string;source?:string};

export default function DatabasePage(){
  const [sheet,setSheet]=useState<SheetName>('DTNA');
  const [dataBySheet,setDataBySheet]=useState<Partial<Record<SheetName,Payload>>>({});
  const [query,setQuery]=useState('');
  const [loadingSheet,setLoadingSheet]=useState<SheetName|null>(null);
  const [errorBySheet,setErrorBySheet]=useState<Partial<Record<SheetName,string>>>({});
  const [lastRefresh,setLastRefresh]=useState<Partial<Record<SheetName,string>>>({});
  const requestId=useRef(0);
  const controller=useRef<AbortController|null>(null);

  const data=dataBySheet[sheet]||null;
  const error=errorBySheet[sheet]||'';
  const loading=loadingSheet===sheet;

  async function load(target:SheetName){
    const id=++requestId.current;
    controller.current?.abort();
    const abort=new AbortController();
    controller.current=abort;
    setLoadingSheet(target);
    setErrorBySheet(prev=>({...prev,[target]:''}));
    try{
      const stamp=Date.now();
      const ping=await fetch(`${LOCAL_DB}/ping?_=${stamp}`,{cache:'no-store',signal:abort.signal,headers:{'Cache-Control':'no-cache','Pragma':'no-cache'}});
      if(!ping.ok)throw new Error('Database viewer is not running. Press START DIEHL VIN first.');
      const r=await fetch(`${LOCAL_DB}/database/${encodeURIComponent(target)}?limit=10000&_=${stamp}`,{cache:'no-store',signal:abort.signal,headers:{'Cache-Control':'no-cache','Pragma':'no-cache'}});
      const payload=await r.json().catch(()=>({}));
      if(!r.ok)throw new Error(payload.detail||'Could not read the database mirror.');
      if(id!==requestId.current||target!==sheet)return;
      if(payload.sheet!==target)throw new Error(`Database service returned ${payload.sheet||'an unknown sheet'} while ${target} was requested.`);
      setDataBySheet(prev=>({...prev,[target]:payload}));
      setLastRefresh(prev=>({...prev,[target]:new Date().toLocaleTimeString()}));
    }catch(e:any){
      if(e?.name==='AbortError')return;
      if(id!==requestId.current)return;
      setErrorBySheet(prev=>({...prev,[target]:e?.message||'Could not read the database mirror.'}));
    }finally{
      if(id===requestId.current)setLoadingSheet(null);
    }
  }

  useEffect(()=>{void load(sheet);return()=>controller.current?.abort()},[sheet]);

  const rows=useMemo(()=>{
    const all=data?.rows||[];
    const q=query.trim().toLowerCase();
    if(!q)return all;
    return all.filter(row=>Object.values(row).some(v=>String(v??'').toLowerCase().includes(q)));
  },[data,query]);

  function chooseSheet(target:SheetName){
    if(target===sheet)return;
    controller.current?.abort();
    requestId.current++;
    setQuery('');
    setSheet(target);
  }

  return <main style={{maxWidth:1600,margin:'0 auto',padding:'32px 24px 56px'}}>
    <section style={{display:'flex',justifyContent:'space-between',gap:24,alignItems:'flex-start',marginBottom:24,flexWrap:'wrap'}}>
      <div>
        <div style={{fontSize:12,fontWeight:800,letterSpacing:1.2,color:'#667085',marginBottom:8}}>SHARED EXCEL DATABASE</div>
        <h1 style={{fontSize:34,lineHeight:1.1,margin:'0 0 10px'}}>Database</h1>
        <p style={{margin:0,color:'#667085',maxWidth:800}}>Read-only view of <b>DIEHL-VIN-PLATFORM WORKBOOK.xlsx</b>. DTNA and VIN In-Service are kept as separate datasets. The website reads a verified local mirror created only after successful Excel saves, so viewing data cannot lock the workbook.</p>
      </div>
      <div style={{display:'flex',flexDirection:'column',alignItems:'flex-end',gap:6}}>
        <button onClick={()=>void load(sheet)} disabled={loading} style={{padding:'11px 18px',borderRadius:10,border:'1px solid #d0d5dd',background:loading?'#f2f4f7':'#fff',fontWeight:700,cursor:loading?'wait':'pointer'}}>{loading?'Refreshing…':'Refresh database'}</button>
        {lastRefresh[sheet]&&<small style={{color:'#667085'}}>Last refreshed {lastRefresh[sheet]}</small>}
      </div>
    </section>

    <section style={{background:'#fff',border:'1px solid #e4e7ec',borderRadius:16,overflow:'hidden',boxShadow:'0 1px 2px rgba(16,24,40,.05)'}}>
      <div style={{display:'flex',justifyContent:'space-between',gap:16,alignItems:'center',padding:16,borderBottom:'1px solid #e4e7ec',flexWrap:'wrap'}}>
        <div style={{display:'flex',gap:8}}>
          {SHEETS.map(s=><button key={s} onClick={()=>chooseSheet(s)} style={{padding:'9px 14px',borderRadius:9,border:s===sheet?'1px solid #101828':'1px solid #d0d5dd',background:s===sheet?'#101828':'#fff',color:s===sheet?'#fff':'#344054',fontWeight:700,cursor:'pointer'}}>{s}</button>)}
        </div>
        <input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search any column…" style={{minWidth:280,padding:'10px 12px',borderRadius:9,border:'1px solid #d0d5dd',outline:'none'}}/>
      </div>

      {loading&&<div style={{margin:16,padding:14,borderRadius:10,background:'#f9fafb',color:'#475467',fontWeight:600}}>Refreshing {sheet} only…</div>}
      {!loading&&error&&<div style={{margin:16,padding:14,borderRadius:10,background:'#fef3f2',color:'#b42318',fontWeight:600}}>{error}<div style={{marginTop:10}}><button onClick={()=>void load(sheet)} style={{padding:'8px 12px',borderRadius:8,border:'1px solid #fda29b',background:'#fff',fontWeight:700,cursor:'pointer'}}>Try again</button></div></div>}

      {!loading&&!error&&data&&<>
        <div style={{display:'flex',gap:24,padding:'12px 16px',fontSize:13,color:'#667085',borderBottom:'1px solid #e4e7ec',flexWrap:'wrap'}}>
          <span><b style={{color:'#101828'}}>{data.rowCount.toLocaleString()}</b> total rows</span>
          <span><b style={{color:'#101828'}}>{rows.length.toLocaleString()}</b> visible</span>
          <span>Dataset: <b style={{color:'#101828'}}>{data.sheet}</b></span>
          {data.readMode&&<span>View source: <b style={{color:'#101828'}}>{data.readMode}</b></span>}
          {data.source&&<span>{data.source}</span>}
          <span style={{overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap',maxWidth:700}}>{data.workbook}</span>
        </div>
        {!data.exists?<div style={{padding:28,color:'#667085'}}>No successful <b>{sheet}</b> write has been mirrored yet. Run that workflow first.</div>:<div style={{overflow:'auto',maxHeight:'68vh'}}>
          <table style={{borderCollapse:'separate',borderSpacing:0,minWidth:'100%',width:'max-content',fontSize:13}}>
            <thead style={{position:'sticky',top:0,zIndex:2,background:'#f9fafb'}}><tr>{data.headers.map(h=><th key={h} style={{textAlign:'left',padding:'11px 12px',borderBottom:'1px solid #e4e7ec',borderRight:'1px solid #eef2f6',whiteSpace:'nowrap',fontWeight:800,color:'#344054'}}>{h}</th>)}</tr></thead>
            <tbody>{rows.map((row,i)=><tr key={`${sheet}-${i}`}>{data.headers.map(h=><td key={h} style={{padding:'9px 12px',borderBottom:'1px solid #f0f2f5',borderRight:'1px solid #f5f6f7',verticalAlign:'top',maxWidth:340,whiteSpace:'pre-wrap',color:'#344054'}}>{String(row[h]??'')}</td>)}</tr>)}{!rows.length&&<tr><td colSpan={Math.max(1,data.headers.length)} style={{padding:28,color:'#667085'}}>No rows match your search.</td></tr>}</tbody>
          </table>
        </div>}
      </>}
    </section>
  </main>
}
