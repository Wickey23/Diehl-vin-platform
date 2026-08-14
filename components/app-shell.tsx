import { Activity, Database, FileSpreadsheet, RefreshCw, Search, Truck, Users, Wrench } from "lucide-react";
import Link from "next/link";

export function AppShell({ children }: { children: React.ReactNode }) {
  return <main className="shell">
    <aside className="sidebar">
      <Link href="/" className="brand"><div className="mark">D</div><div><strong>Diehl</strong><span>VIN Platform</span></div></Link>
      <nav>
        <Link href="/"><Database size={18}/> Dashboard</Link>
        <Link href="/vehicles"><Truck size={18}/> Vehicles</Link>
        <Link href="/lookup"><Search size={18}/> VIN Lookup</Link>
        <Link href="/sync"><RefreshCw size={18}/> DTNA Sync</Link>
        <Link href="/history"><Activity size={18}/> Change History</Link>
        <Link href="/import"><FileSpreadsheet size={18}/> Import / Export</Link>
        <Link href="/admin"><Users size={18}/> Admin</Link>
      </nav>
      <div className="worker"><Wrench size={18}/><div><b>DTNA Worker</b><span>Secure connector ready</span></div></div>
    </aside>
    <section className="content">{children}</section>
  </main>;
}
