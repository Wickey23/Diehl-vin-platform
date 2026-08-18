'use client';

import {useEffect, useMemo, useState} from 'react';

const LOCAL_DB='http://127.0.0.1:8766';
const SHEETS=['DTNA','VIN In-Service'] as const;

type SheetName=typeof SHEETS[number];
type Row=Record<string, unknown>;
type Payload={
  sheet:string;
  workbook:string;
  headers:string[];
  rows:Row[];
  rowCount:number;
  returned?:number;
  exists:boolean;
};

export default function DatabasePage(){
  const [sheet,setSheet]=useState<SheetName>('DTNA');
  const [data,setData]=useState<Payload|null>(null);
  const [query,setQuery]=useState('');
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState('');

  async function load(target:SheetName=sheet){
    setLoading(true);setError('');
    try{
      const ping=await fetch(`${LOCAL_DB}/ping`,{cache:'no-store'});
      if(!ping.ok) throw new Error('Database viewer is not running. Press START DIEHL VIN first.');
      const r=await fetch(`${LOCAL_DB}/database/${encodeURIComponent(target)}?limit=10000`,{cache:'no-store'});
      const payload=await r.json().catch(()=>({}));
      if(!r.ok) throw new Error(payload.detail||'Could not read the shared Excel database.');
      setData(payload);
    }catch(e:any){
      setData(null);setError(e?.message||'Could not read the shared Excel database.');
    }finally{setLoading(false)}
  }

  useEffect(()=>{load(sheet)},[sheet]);

  const rows=useMemo(()=>{
    const all=data?.rows||[];
    const q=query.trim().toLowerCase();
    if(!q)return all;
    return all.filter(row=>Object.values(row).some(v=>String(v??'').toLowerCase().includes(q)));
  },[data,query]);

  return <main style={{maxWidth:1600,margin:'0 auto',padding:'32px 24px 56px'}}>
    <section style={{display:'flex',justifyContent:'space-between',gap:24,alignItems:'flex-start',marginBottom:24,flexWrap:'wrap'}}>
      <div>
        <div style={{fontSize:12,fontWeight:800,letterSpacing:1.2,color:'#667085',marginBottom:8}}>SHARED EXCEL DATABASE</div>
        <h1 style={{fontSize:34,lineHeight:1.1,margin:'0 0 10px'}}>Database</h1>
        <p style={{margin:0,color:'#667085',maxWidth:760}}>Read-only view of <b>DIEHL-VIN-PLATFORM WORKBOOK.xlsx</b>. Data shown here comes directly from the locally synced shared workbook; editing still happens through the DTNA and VIN In-Service workflows.</p>
      </div>
      <button onClick={()=>load(sheet)} disabled={loading} style={{padding:'11px 18px',borderRadius:10,border:'1px solid #d0d5dd',background:'#fff',fontWeight:700,cursor:'pointer'}}>{loading?'Refreshing…':'Refresh database'}</button>
    </section>

    <section style={{background:'#fff',border:'1px solid #e4e7ec',borderRadius:16,overflow:'hidden',boxShadow:'0 1px 2px rgba(16,24,40,.05)'}}>
      <div style={{display:'flex',justifyContent:'space-between',gap:16,alignItems:'center',padding:16,borderBottom:'1px solid #e4e7ec',flexWrap:'wrap'}}>
        <div style={{display:'flex',gap:8}}>
          {SHEETS.map(s=><button key={s} onClick={()=>setSheet(s)} style={{padding:'9px 14px',borderRadius:9,border:s===sheet?'1px solid #101828':'1px solid #d0d5dd',background:s===sheet?'#101828':'#fff',color:s===sheet?'#fff':'#344054',fontWeight:700,cursor:'pointer'}}>{s}</button>)}
        </div>
        <input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search any column…" style={{minWidth:280,padding:'10px 12px',borderRadius:9,border:'1px solid #d0d5dd',outline:'none'}} />
      </div>

      {error&&<div style={{margin:16,padding:14,borderRadius:10,background:'#fef3f2',color:'#b42318',fontWeight:600}}>{error}</div>}

      {!error&&data&&<>
        <div style={{display:'flex',gap:24,padding:'12px 16px',fontSize:13,color:'#667085',borderBottom:'1px solid #e4e7ec',flexWrap:'wrap'}}>
          <span><b style={{color:'#101828'}}>{data.rowCount.toLocaleString()}</b> total rows</span>
          <span><b style={{color:'#101828'}}>{rows.length.toLocaleString()}</b> visible</span>
          <span style={{overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap',maxWidth:800}}>{data.workbook}</span>
        </div>

        {!data.exists?<div style={{padding:28,color:'#667085'}}>The <b>{sheet}</b> sheet has not been created yet. It will appear after that workflow writes data.</div>:
        <div style={{overflow:'auto',maxHeight:'68vh'}}>
          <table style={{borderCollapse:'separate',borderSpacing:0,minWidth:'100%',width:'max-content',fontSize:13}}>
            <thead style={{position:'sticky',top:0,zIndex:2,background:'#f9fafb'}}>
              <tr>{data.headers.map(h=><th key={h} style={{textAlign:'left',padding:'11px 12px',borderBottom:'1px solid #e4e7ec',borderRight:'1px solid #eef2f6',whiteSpace:'nowrap',fontWeight:800,color:'#344054'}}>{h}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((row,i)=><tr key={i}>{data.headers.map(h=><td key={h} style={{padding:'9px 12px',borderBottom:'1px solid #f0f2f5',borderRight:'1px solid #f5f6f7',verticalAlign:'top',maxWidth:340,whiteSpace:'pre-wrap',color:'#344054'}}>{String(row[h]??'')}</td>)}</tr>)}
              {!rows.length&&<tr><td colSpan={Math.max(1,data.headers.length)} style={{padding:28,color:'#667085'}}>No rows match your search.</td></tr>}
            </tbody>
          </table>
        </div>}
      </>}
    </section>
  </main>
}
