'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState } from 'react';

const tabs = [
  { href: '/', label: 'Initializer' },
  { href: '/dtna', label: 'DTNA' },
  { href: '/vin-inservice', label: 'VIN In-Service' },
  { href: '/database', label: 'Database' },
];

const LATEST_WORKER_VERSION = '5.16';
const LATEST_WORKER_UPDATED = '08/19/2026 3:22 PM ET';
const RELEASE_NOTES = [
  'Fixes Start OWL Check appearing to do nothing: a newly submitted VIN batch now launches immediately in its own local execution thread instead of waiting for the legacy background scheduler.',
  'The VIN is moved to running immediately and the live OWL lookup is started for that exact batch.',
  'Abandoned older queued/running batches are still cancelled automatically so they cannot block a fresh VIN lookup.',
  'Coverage Info remains the authoritative source for In Service Date, In Service Distance/Mileage, Make, Base Model, Model, build/order/PDI dates, and warranty/extended coverage.',
  'Major Components uses Chassis S/N and exact ENGINE / MAIN TRANSMISSION rows for Cummins and Allison data.',
  'Product Registration is the authoritative source for registered and ordered customer account/name plus address, city, state, ZIP, phone, and email.',
  'Starting or restarting the worker does not open another Diehl VIN Platform website tab; keep using the tab already open.',
];

export function TopTabs() {
  const pathname = usePathname();
  const [showUpdateInfo, setShowUpdateInfo] = useState(false);

  return (
    <>
      <header className="workflow-tabs-wrap" style={{gap:16, flexWrap:'wrap'}}>
        <div className="workflow-tabs-brand">
          <strong>Diehl VIN Platform</strong>
          <span>Local DTNA + Excel worker</span>
        </div>

        <div aria-label={`Latest worker v${LATEST_WORKER_VERSION}, updated ${LATEST_WORKER_UPDATED}`} style={{display:'flex',alignItems:'center',gap:9,marginLeft:'auto',padding:'7px 10px',border:'1px solid #f5c26b',borderRadius:9,background:'#fff8e7',color:'#7a4b00',fontSize:12,lineHeight:1.25,whiteSpace:'nowrap'}}>
          <span style={{width:7,height:7,borderRadius:'50%',background:'#f59e0b',display:'inline-block',flex:'0 0 auto'}} />
          <span><b>Latest Worker v{LATEST_WORKER_VERSION}</b>{' · '}Updated {LATEST_WORKER_UPDATED}</span>
          <button type="button" onClick={() => setShowUpdateInfo(true)} aria-label="What's new in this worker update" title="What's new in this update" style={{width:20,height:20,borderRadius:'50%',border:'1px solid #d99a24',background:'#fff',color:'#7a4b00',fontSize:12,fontWeight:900,lineHeight:'18px',padding:0,cursor:'pointer',display:'inline-flex',alignItems:'center',justifyContent:'center'}}>i</button>
          <a href="/api/download-worker" style={{fontWeight:800,color:'#7a4b00',textDecoration:'underline',textUnderlineOffset:2}} title="Download the latest local worker package">Download update</a>
        </div>

        <nav className="workflow-tabs" aria-label="VIN platform sections">
          {tabs.map((tab) => {
            const active = tab.href === '/' ? pathname === '/' : pathname.startsWith(tab.href);
            return <Link key={tab.href} className={active ? 'active' : ''} href={tab.href}>{tab.label}</Link>;
          })}
        </nav>
      </header>

      {showUpdateInfo && (
        <div role="dialog" aria-modal="true" aria-labelledby="worker-update-title" onMouseDown={(e) => { if (e.target === e.currentTarget) setShowUpdateInfo(false); }} style={{position:'fixed',inset:0,zIndex:9999,background:'rgba(16,24,40,.38)',display:'flex',alignItems:'flex-start',justifyContent:'center',padding:'88px 20px 20px'}}>
          <div style={{width:'min(600px, 100%)',background:'#fff',border:'1px solid #e4e7ec',borderRadius:16,boxShadow:'0 20px 50px rgba(16,24,40,.22)',overflow:'hidden'}}>
            <div style={{display:'flex',justifyContent:'space-between',gap:20,alignItems:'flex-start',padding:'20px 22px 16px',borderBottom:'1px solid #eef2f6'}}>
              <div>
                <div style={{fontSize:12,fontWeight:800,letterSpacing:.8,color:'#b36a00',marginBottom:5}}>WORKER UPDATE</div>
                <h2 id="worker-update-title" style={{margin:0,fontSize:22,color:'#101828'}}>What’s new in v{LATEST_WORKER_VERSION}</h2>
                <div style={{marginTop:5,fontSize:13,color:'#667085'}}>Updated {LATEST_WORKER_UPDATED}</div>
              </div>
              <button type="button" onClick={() => setShowUpdateInfo(false)} aria-label="Close update details" style={{border:0,background:'transparent',fontSize:24,lineHeight:1,cursor:'pointer',color:'#667085'}}>×</button>
            </div>

            <div style={{padding:'18px 22px 8px'}}>
              <p style={{margin:'0 0 12px',color:'#475467',fontSize:14}}>This release changes Start OWL Check from a queued scheduler handoff to an immediate local execution path, while preserving the exact OWL data mappings already confirmed.</p>
              <ul style={{margin:'0 0 8px',paddingLeft:22,color:'#344054',fontSize:14,lineHeight:1.55}}>
                {RELEASE_NOTES.map((note) => <li key={note} style={{marginBottom:8}}>{note}</li>)}
              </ul>
            </div>

            <div style={{display:'flex',justifyContent:'flex-end',gap:10,padding:'14px 22px 20px'}}>
              <button type="button" onClick={() => setShowUpdateInfo(false)} style={{padding:'9px 14px',borderRadius:9,border:'1px solid #d0d5dd',background:'#fff',fontWeight:700,cursor:'pointer'}}>Close</button>
              <a href="/api/download-worker" style={{padding:'9px 14px',borderRadius:9,border:'1px solid #b36a00',background:'#b36a00',color:'#fff',fontWeight:800,textDecoration:'none'}}>Download v{LATEST_WORKER_VERSION}</a>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
