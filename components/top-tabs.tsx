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

const LATEST_WORKER_VERSION = '5.13';
const LATEST_WORKER_UPDATED = '08/19/2026 1:29 PM ET';
const RELEASE_NOTES = [
  'Coverage Info now enters the VIN only in the main Product S/N field, verifies it, presses Tab, and waits for actual OWL vehicle information to populate before extracting.',
  'Major Components now uses the correct Chassis S/N field shown on the live OWL page — not Product S/N and never the left Quick Search box.',
  'Major Components independently clears Chassis S/N, enters the full VIN, verifies it, presses Tab, and waits for the matching chassis/component data before reading anything.',
  'The requested VIN must match the populated Chassis S/N before Major Components data is accepted, preventing stale data from a prior vehicle.',
  'The Major Components table must populate with Component, MFG, Model, and Component S/N before engine or Allison information is extracted.',
  'Coverage mapping now uses the exact live OWL labels confirmed in testing: In Service Distance, In Service Date, Cab Start Date, Build Date, Base Model, Model, Order Date, Customer Name, Unit #, PDI Date, First Service Date, Special Conditions, and PDI Submitting Location.',
  'There is no fixed one-second delay; the worker reacts as soon as OWL has actually populated stable result data.',
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

        <div
          aria-label={`Latest worker v${LATEST_WORKER_VERSION}, updated ${LATEST_WORKER_UPDATED}`}
          style={{display:'flex',alignItems:'center',gap:9,marginLeft:'auto',padding:'7px 10px',border:'1px solid #f5c26b',borderRadius:9,background:'#fff8e7',color:'#7a4b00',fontSize:12,lineHeight:1.25,whiteSpace:'nowrap'}}
        >
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
              <p style={{margin:'0 0 12px',color:'#475467',fontSize:14}}>This release corrects the live OWL VIN-entry sequence on both pages and locks the Coverage mapping to the fields confirmed in the live interface.</p>
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
