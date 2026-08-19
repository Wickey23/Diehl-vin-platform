'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const tabs = [
  { href: '/', label: 'Initializer' },
  { href: '/dtna', label: 'DTNA' },
  { href: '/vin-inservice', label: 'VIN In-Service' },
  { href: '/database', label: 'Database' },
];

const LATEST_WORKER_VERSION = '5.10';
const LATEST_WORKER_UPDATED = '08/19/2026 11:22 AM ET';

export function TopTabs() {
  const pathname = usePathname();

  return (
    <header className="workflow-tabs-wrap" style={{gap:16, flexWrap:'wrap'}}>
      <div className="workflow-tabs-brand">
        <strong>Diehl VIN Platform</strong>
        <span>Local DTNA + Excel worker</span>
      </div>

      <div
        aria-label={`Latest worker v${LATEST_WORKER_VERSION}, updated ${LATEST_WORKER_UPDATED}`}
        style={{
          display:'flex',
          alignItems:'center',
          gap:10,
          marginLeft:'auto',
          padding:'7px 10px',
          border:'1px solid #f5c26b',
          borderRadius:9,
          background:'#fff8e7',
          color:'#7a4b00',
          fontSize:12,
          lineHeight:1.25,
          whiteSpace:'nowrap',
        }}
      >
        <span style={{width:7,height:7,borderRadius:'50%',background:'#f59e0b',display:'inline-block',flex:'0 0 auto'}} />
        <span><b>Latest Worker v{LATEST_WORKER_VERSION}</b>{' · '}Updated {LATEST_WORKER_UPDATED}</span>
        <a href="/api/download-worker" style={{fontWeight:800,color:'#7a4b00',textDecoration:'underline',textUnderlineOffset:2}} title="Download the latest local worker package">Download update</a>
      </div>

      <nav className="workflow-tabs" aria-label="VIN platform sections">
        {tabs.map((tab) => {
          const active = tab.href === '/' ? pathname === '/' : pathname.startsWith(tab.href);
          return <Link key={tab.href} className={active ? 'active' : ''} href={tab.href}>{tab.label}</Link>;
        })}
      </nav>
    </header>
  );
}
