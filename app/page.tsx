import { Activity, Database, FileSpreadsheet, RefreshCw, Search, Truck, Users, Wrench } from "lucide-react";

const demoRows = [
  { vin: "1FV••••••••0168", serial: "XE0168", model: "114SD", customer: "County Fleet", status: "Dealer Received", eta: "Received", updated: "Recently" },
  { vin: "1FV••••••••5274", serial: "XF5274", model: "M2 106", customer: "Municipal Fleet", status: "Scheduled", eta: "Sep 8", updated: "Recently" },
  { vin: "4UZ••••••••7651", serial: "XM7651", model: "Custom Chassis", customer: "Utility Fleet", status: "Scheduled", eta: "Sep 21", updated: "Recently" },
];

export default function Home() {
  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand"><div className="mark">D</div><div><strong>Diehl</strong><span>VIN Platform</span></div></div>
        <nav>
          <a className="active" href="#"><Database size={18}/> Dashboard</a>
          <a href="#vehicles"><Truck size={18}/> Vehicles</a>
          <a href="#lookup"><Search size={18}/> VIN Lookup</a>
          <a href="#sync"><RefreshCw size={18}/> DTNA Sync</a>
          <a href="#history"><Activity size={18}/> Change History</a>
          <a href="#import"><FileSpreadsheet size={18}/> Import / Export</a>
          <a href="#admin"><Users size={18}/> Admin</a>
        </nav>
        <div className="worker"><Wrench size={18}/><div><b>DTNA Worker</b><span>Integration boundary ready</span></div></div>
      </aside>

      <section className="content">
        <header className="topbar"><div><p className="eyebrow">OPERATIONS</p><h1>Fleet & VIN Dashboard</h1></div><button className="primary"><RefreshCw size={17}/> Sync DTNA</button></header>

        <section id="lookup" className="lookup-card">
          <div><p className="eyebrow">QUICK LOOKUP</p><h2>Find any vehicle</h2><p>Search full VIN, serial number, customer, sales order, or model.</p></div>
          <div className="searchbox"><Search size={20}/><input placeholder="Enter VIN or serial number…"/><button>Look up</button></div>
        </section>

        <section className="stats">
          <article><span>Vehicles</span><strong>—</strong><small>Connect database to populate</small></article>
          <article><span>DTNA Orders</span><strong>—</strong><small>Imported + synchronized</small></article>
          <article><span>In-Service Dates</span><strong>—</strong><small>Dealer Reporting enrichment</small></article>
          <article><span>Changes</span><strong>—</strong><small>Normalized real changes only</small></article>
        </section>

        <section id="vehicles" className="panel">
          <div className="panel-head"><div><p className="eyebrow">VEHICLES</p><h2>Current vehicle records</h2></div><div className="actions"><button>Upload Excel / CSV</button><button>Export Excel</button></div></div>
          <div className="table-wrap"><table><thead><tr><th>VIN</th><th>Serial</th><th>Model</th><th>Customer</th><th>Status</th><th>Projected / Actual</th><th>Updated</th></tr></thead><tbody>{demoRows.map((row) => <tr key={row.serial}><td className="mono">{row.vin}</td><td>{row.serial}</td><td>{row.model}</td><td>{row.customer}</td><td><span className="status">{row.status}</span></td><td>{row.eta}</td><td>{row.updated}</td></tr>)}</tbody></table></div>
          <p className="demo-note">Masked demonstration rows only. Production data will come from your secured database and DTNA worker.</p>
        </section>

        <section className="grid-two">
          <article id="history" className="panel compact"><p className="eyebrow">CHANGE HISTORY</p><h2>Clean event tracking</h2><p>The web version normalizes DTNA values before comparison, so formatting changes like “CURRENT: Jun 29 2026” → “Jun 29 2026” are not logged as real changes.</p><div className="event"><span className="dot"></span><div><b>Status changed</b><span>ETA at Destination → Dealer Received</span></div></div><div className="event"><span className="dot"></span><div><b>Projected delivery changed</b><span>Previous values remain available in history</span></div></div></article>
          <article id="sync" className="panel compact"><p className="eyebrow">DTNA INTEGRATION</p><h2>Vercel + secure worker</h2><p>The website stays on Vercel. Persistent browser/MFA automation runs in a separate worker and sends normalized order data through an authenticated API.</p><div className="flow"><span>DTNA</span><b>→</b><span>Worker</span><b>→</b><span>API</span><b>→</b><span>Database</span></div></article>
        </section>
      </section>
    </main>
  );
}
