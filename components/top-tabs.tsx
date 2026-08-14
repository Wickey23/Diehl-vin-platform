'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const tabs = [
  { href: '/', label: 'Initializer' },
  { href: '/dtna', label: 'DTNA' },
  { href: '/vin-inservice', label: 'VIN In-Service' },
];

export function TopTabs() {
  const pathname = usePathname();
  return (
    <header className="workflow-tabs-wrap">
      <div className="workflow-tabs-brand">
        <strong>Diehl VIN Platform</strong>
        <span>Local DTNA + Excel worker</span>
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
