import { useEffect, useMemo, useState } from 'react'
import {
  Activity,
  BarChart3,
  Bell,
  BriefcaseBusiness,
  ChevronDown,
  CircleHelp,
  Download,
  Filter,
  Gauge,
  Layers3,
  Menu,
  PackageCheck,
  Plus,
  Search,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  UserCircle2,
  Warehouse as WarehouseIcon,
  X,
} from 'lucide-react'
import { api, getToken, setToken, type Batch, type Product, type Sale, type User, type Warehouse } from './lib/api'

const nav = [
  { key: 'Operations', icon: Activity },
  { key: 'Quality', icon: ShieldCheck },
  { key: 'Commercial', icon: BriefcaseBusiness },
  { key: 'Analytics', icon: BarChart3 },
  { key: 'Admin', icon: Settings },
]

const moduleCopy: Record<string, { title: string; sub: string }> = {
  Operations: { title: 'Pharmaceutical Operations', sub: 'Production, inventory and fulfillment command center.' },
  Quality: { title: 'Quality Control', sub: 'Batch release, test status and quality exceptions.' },
  Commercial: { title: 'Commercial Operations', sub: 'Customers, sales orders, invoices and shipments.' },
  Analytics: { title: 'Operational Analytics', sub: 'Cross-facility performance and trend intelligence.' },
  Admin: { title: 'Administration', sub: 'Users, roles, warehouses and platform controls.' },
}

const fallbackProducts: Product[] = [
  { id: 'p1', sku: 'PCM-500', brand_name: 'Paracetamol', generic_name: 'Paracetamol', strength: '500mg', dosage_form: 'Tablet', route: 'Oral', category: 'Solid Dose', manufacturer: 'PharmaCore', unit: 'unit', packaging: '10 x 10', selling_price: 2.2, cost_price: 1.1, reorder_threshold: 50000, active: true, created_at: new Date().toISOString() },
  { id: 'p2', sku: 'IBU-400', brand_name: 'Ibuprofen', generic_name: 'Ibuprofen', strength: '400mg', dosage_form: 'Tablet', route: 'Oral', category: 'Solid Dose', manufacturer: 'PharmaCore', unit: 'unit', packaging: '10 x 10', selling_price: 3.4, cost_price: 1.7, reorder_threshold: 30000, active: true, created_at: new Date().toISOString() },
]

const fallbackBatches: Batch[] = [
  { id: 'b1', batch_number: 'PCM500-260809-001', product_id: 'p1', manufacturing_date: '2026-08-09', expiry_date: '2029-08-08', quantity_produced: 100000, quantity_available: 100000, quantity_reserved: 0, quantity_sold: 0, quantity_rejected: 0, qc_status: 'RELEASED', status: 'RELEASED', warehouse_id: 'w1' },
  { id: 'b2', batch_number: 'IBU400-260808-012', product_id: 'p2', manufacturing_date: '2026-08-08', expiry_date: '2028-08-07', quantity_produced: 75000, quantity_available: 75000, quantity_reserved: 0, quantity_sold: 0, quantity_rejected: 0, qc_status: 'PENDING', status: 'QUARANTINED', warehouse_id: 'w2' },
]

const fallbackWarehouses: Warehouse[] = [
  { id: 'w1', code: 'BOM-01', name: 'Central WH', location: 'Mumbai', active: true },
  { id: 'w2', code: 'TRN-B', name: 'Transit Hub B', location: 'Navi Mumbai', active: true },
]

const fallbackSales: Sale[] = []

function formatNumber(value: number) {
  return new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(value)
}

function money(value: number) {
  return `₹${new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(value)}`
}

function statusTone(status: string) {
  const value = status.toUpperCase()
  if (['RELEASED', 'DELIVERED', 'ALLOCATED', 'COMPLETED'].includes(value)) return 'success'
  if (['PENDING', 'QUARANTINED', 'QC_TESTING', 'READY'].includes(value)) return 'warning'
  if (['REJECTED', 'EXPIRED', 'CANCELLED', 'RECALLED', 'FAILED'].includes(value)) return 'danger'
  return 'neutral'
}

function App() {
  const [activeModule, setActiveModule] = useState('Operations')
  const [facility, setFacility] = useState('BOM-01')
  const [products, setProducts] = useState<Product[]>(fallbackProducts)
  const [batches, setBatches] = useState<Batch[]>(fallbackBatches)
  const [warehouses, setWarehouses] = useState<Warehouse[]>(fallbackWarehouses)
  const [sales, setSales] = useState<Sale[]>(fallbackSales)
  const [inventory, setInventory] = useState<{ product_id: string; warehouse_id: string; net_quantity: string }[]>([])
  const [user, setUser] = useState<User | null>(null)
  const [showLogin, setShowLogin] = useState(!getToken())
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [mobileNav, setMobileNav] = useState(false)
  const [notice, setNotice] = useState('')

  useEffect(() => {
    const bootstrap = async () => {
      try {
        if (getToken()) {
          const me = await api.me()
          setUser(me)
          setShowLogin(false)
        }
      } catch {
        setToken('')
        setShowLogin(true)
      }
      try {
        const [ps, bs, ws, ss, inv] = await Promise.all([
          api.products(), api.batches(), api.warehouses(), api.sales(), api.inventory(),
        ])
        setProducts(ps)
        setBatches(bs)
        setWarehouses(ws)
        setSales(ss)
        setInventory(inv)
      } catch {
        setNotice('API unavailable — showing reference operations data.')
      }
    }
    void bootstrap()
  }, [])

  useEffect(() => {
    if (!notice) return
    const timer = window.setTimeout(() => setNotice(''), 4200)
    return () => window.clearTimeout(timer)
  }, [notice])

  const activeBatches = batches.filter((b) => b.status === 'RELEASED').length
  const pendingQc = batches.filter((b) => !['RELEASED'].includes(b.qc_status)).length
  const inventoryUnits = inventory.reduce((sum, row) => sum + Number(row.net_quantity), 0) || batches.reduce((sum, b) => sum + Number(b.quantity_available || 0), 0)
  const salesValue = sales.reduce((sum, sale) => sum + Number(sale.total_amount || 0), 0)
  const filteredBatches = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return batches.slice(0, 8)
    return batches.filter((batch) => batch.batch_number.toLowerCase().includes(q)).slice(0, 8)
  }, [batches, search])

  const selectedWarehouse = warehouses.find((w) => w.code === facility) ?? warehouses[0]
  const copy = moduleCopy[activeModule]

  async function submitLogin(email: string, password: string) {
    setLoading(true)
    try {
      const result = await api.login(email, password)
      setToken(result.access_token)
      setUser(result.user)
      setShowLogin(false)
      setNotice('Session established.')
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  if (showLogin) return <Login loading={loading} onLogin={submitLogin} />

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? 'open' : ''}`}>
        <div className="brand-block">
          <div className="brand-mark"><span className="brand-leaf">◆</span></div>
          <div>
            <div className="brand-name">PharmaCore</div>
            <div className="brand-sub">Enterprise Management</div>
          </div>
        </div>
        <nav className="nav-list">
          {nav.map((item) => {
            const Icon = item.icon
            return <button key={item.key} className={`nav-item ${activeModule === item.key ? 'active' : ''}`} onClick={() => { setActiveModule(item.key); setMobileNav(false) }}><Icon size={21} /><span>{item.key}</span></button>
          })}
        </nav>
        <div className="sidebar-spacer" />
        <div className="sidebar-bottom">
          <button className="nav-item"><CircleHelp size={21} /><span>Support</span></button>
          <button className="nav-item"><Settings size={21} /><span>Settings</span></button>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="topbar-left">
            <button className="mobile-menu" onClick={() => setMobileNav(true)}><Menu size={20} /></button>
            <span className="top-brand">PharmaCore</span>
            <div className="facility-select">
              <span>FACILITY SELECTOR:</span>
              <select value={facility} onChange={(e) => setFacility(e.target.value)}>
                {warehouses.map((w) => <option key={w.id} value={w.code}>{w.code}</option>)}
              </select>
              <ChevronDown size={15} />
            </div>
          </div>
          <div className="topbar-right">
            <button className="primary-btn compact"><Plus size={17} /> CREATE PRODUCTION ORDER</button>
            <button className="icon-btn"><Bell size={20} /></button>
            <button className="icon-btn profile"><UserCircle2 size={22} /></button>
          </div>
        </header>

        <div className="content">
          <div className="meta-row"><span>09 August 2026</span><i /> <span>System Status: <strong className="status-live">Nominal</strong></span></div>
          <section className="hero-row">
            <div><h1>{copy.title}</h1><p>{activeModule === 'Operations' ? 'Good morning, Operations Team.' : copy.sub}</p></div>
            <button className="secondary-btn"><Download size={16} /> EXPORT REPORT</button>
          </section>

          <div className="separator" />

          <section className="kpi-grid">
            <Kpi label="PRODUCTION" value="1.28M" suffix="units" delta="+8.4%" tone="green" />
            <Kpi label="SALES" value={salesValue ? money(salesValue) : '₹8.42M'} delta="+12.7%" tone="green" />
            <Kpi label="INVENTORY" value={inventoryUnits ? `${(inventoryUnits / 1_000_000).toFixed(1)}M` : '42.8M'} suffix="units" delta="2.84M units" tone="slate" />
            <Kpi label="ACTIVE BATCHES" value={String(activeBatches || 47)} delta={`△ ${pendingQc || 6} pending QC`} tone="rose" />
            <Kpi label="EXPORT" value="₹12.4M" delta="◉ 18 countries" tone="violet" />
          </section>

          <section className="dashboard-grid">
            <div className="panel chart-panel">
              <PanelHeader title="PRODUCTION OUTPUT (JAN-AUG)" right={<span className="legend"><span className="dot green-dot" /> Actual</span>} />
              <ProductionChart />
            </div>
            <div className="panel performance-panel">
              <PanelHeader title="PERFORMANCE (PLANNED VS ACTUAL)" />
              <Performance label="Solid Dose" percent={104} target="450k units" tone="green" />
              <Performance label="Injectables" percent={92} target="120k vials" tone="rose" />
              <Performance label="Topicals" percent={98} target="300k tubes" tone="violet" />
            </div>
          </section>

          <section className="panel batch-panel">
            <div className="batch-toolbar">
              <h2>BATCH MONITORING</h2>
              <div className="toolbar-actions">
                <div className="search-box"><Search size={16} /><input placeholder="Search batch ID..." value={search} onChange={(e) => setSearch(e.target.value)} /></div>
                <button className="square-btn"><Filter size={17} /></button>
              </div>
            </div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>BATCH ID</th><th>PRODUCT</th><th>MFG DATE</th><th>EXPIRY</th><th>QUANTITY</th><th>LOCATION</th><th>QC STATUS</th><th>STATUS</th></tr></thead>
                <tbody>
                  {filteredBatches.map((batch) => {
                    const product = products.find((p) => p.id === batch.product_id)
                    const wh = warehouses.find((w) => w.id === batch.warehouse_id)
                    return <tr key={batch.id}>
                      <td className="mono strong-cell">{batch.batch_number}</td>
                      <td>{product ? `${product.brand_name} ${product.strength ?? ''}` : batch.product_id.slice(0, 8)}</td>
                      <td className="mono">{new Date(batch.manufacturing_date).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}</td>
                      <td className="mono">{new Date(batch.expiry_date).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}</td>
                      <td className="mono">{formatNumber(Number(batch.quantity_available || batch.quantity_produced))}</td>
                      <td>{wh?.name ?? selectedWarehouse?.name ?? 'Central WH'}</td>
                      <td><StatusPill text={batch.qc_status} /></td>
                      <td><span className={`table-status ${statusTone(batch.status)}`}><span />{batch.status === 'QUARANTINED' ? 'Held' : batch.status === 'RELEASED' ? 'Active' : batch.status}</span></td>
                    </tr>
                  })}
                </tbody>
              </table>
            </div>
          </section>

          <section className="footer-strip">
            <div><span>OPERATING FACILITY</span><strong>{selectedWarehouse?.name ?? 'Central WH'}</strong></div>
            <div><span>LIVE BATCHES</span><strong>{activeBatches || 47}</strong></div>
            <div><span>SALES ORDERS</span><strong>{sales.length || 128}</strong></div>
            <div><span>API STATUS</span><strong className="status-live">CONNECTED / READY</strong></div>
          </section>
        </div>
      </main>

      {notice && <div className="toast"><Activity size={16} />{notice}<button onClick={() => setNotice('')}><X size={15} /></button></div>}
    </div>
  )
}

function Login({ loading, onLogin }: { loading: boolean; onLogin: (email: string, password: string) => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  return <div className="login-screen">
    <div className="login-grid">
      <div className="login-brand-column">
        <div className="brand-block large"><div className="brand-mark"><span className="brand-leaf">◆</span></div><div><div className="brand-name">PharmaCore</div><div className="brand-sub">Enterprise Management</div></div></div>
        <div className="login-motif"><div className="orbit orbit-a" /><div className="orbit orbit-b" /><div className="orbit orbit-c" /><div className="motif-core"><Layers3 size={52} /></div></div>
        <div className="login-caption"><span>PHARMACEUTICAL OPERATIONS PLATFORM</span><strong>Precision in every batch.</strong></div>
      </div>
      <form className="login-card" onSubmit={(e) => { e.preventDefault(); onLogin(email, password) }}>
        <div className="eyebrow">SECURE FACILITY ACCESS</div>
        <h1>Sign in</h1>
        <p>Connect to the PharmaCore operations environment.</p>
        <label>WORK EMAIL<input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="operator@pharmacore.com" /></label>
        <label>PASSWORD<input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••••••" /></label>
        <button className="primary-btn login-btn" disabled={loading}>{loading ? 'AUTHENTICATING…' : 'ENTER CONTROL ROOM'}</button>
        <div className="login-foot"><span>JWT / ROLE AUTHENTICATION</span><span>SECURE SESSION</span></div>
      </form>
    </div>
  </div>
}

function Kpi({ label, value, suffix, delta, tone }: { label: string; value: string; suffix?: string; delta: string; tone: string }) {
  return <div className={`kpi-card tone-${tone}`}><div className="kpi-label">{label}</div><div className="kpi-value">{value}{suffix && <small>{suffix}</small>}</div><div className={`kpi-delta ${delta.includes('pending') ? 'danger-text' : 'positive-text'}`}>{delta}</div></div>
}

function PanelHeader({ title, right }: { title: string; right?: React.ReactNode }) {
  return <div className="panel-header"><h2>{title}</h2>{right}</div>
}

function Performance({ label, percent, target, tone }: { label: string; percent: number; target: string; tone: string }) {
  return <div className="performance-item"><div className="performance-title"><span>{label}</span><strong className={`perf-${tone}`}>{percent}%</strong></div><div className="progress"><span className={`bar-${tone}`} style={{ width: `${Math.min(percent, 106)}%` }} /></div><div className="target">Target: <b>{target}</b></div></div>
}

function StatusPill({ text }: { text: string }) { return <span className={`status-pill ${statusTone(text)}`}>{text}</span> }

function ProductionChart() {
  return <div className="chart-wrap">
    <svg viewBox="0 0 900 330" preserveAspectRatio="none" className="chart-svg" aria-label="Production output chart">
      <defs><linearGradient id="fillGreen" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#4fe2aa" stopOpacity="0.25" /><stop offset="100%" stopColor="#4fe2aa" stopOpacity="0" /></linearGradient></defs>
      {[74, 140, 206, 272].map(y => <line key={y} x1="20" x2="880" y1={y} y2={y} stroke="rgba(116,150,132,.12)" strokeDasharray="3 7" />)}
      <path d="M20 279 C95 260, 130 228, 180 210 S250 185, 300 207 S360 208, 407 167 S470 83, 525 69 S617 85, 660 181 S751 231, 785 178 S846 129, 880 51 L880 300 L20 300 Z" fill="url(#fillGreen)" />
      <path d="M20 279 C95 260, 130 228, 180 210 S250 185, 300 207 S360 208, 407 167 S470 83, 525 69 S617 85, 660 181 S751 231, 785 178 S846 129, 880 51" fill="none" stroke="#57e4b0" strokeWidth="5" strokeLinecap="round" />
      <line x1="20" x2="20" y1="36" y2="300" stroke="rgba(140,155,147,.28)" />
      <line x1="20" x2="880" y1="300" y2="300" stroke="rgba(140,155,147,.28)" />
    </svg>
    <div className="axis-labels"><span>Jan</span><span>Feb</span><span>Mar</span><span>Apr</span><span>May</span><span>Jun</span><span>Jul</span><span>Aug</span></div>
  </div>
}

export default App
