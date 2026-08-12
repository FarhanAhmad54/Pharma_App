import { useMemo, useState } from 'react'
import { ArrowRightLeft, CheckCircle2, ClipboardCheck, FileText, Package, Plus, RefreshCw, Search, Send, ShieldAlert, Truck, Users, Warehouse } from 'lucide-react'
import { api, type Batch, type Product, type Sale, type Warehouse as WarehouseType } from './lib/api'

type Notice = (message: string) => void
const fmt = (value: number) => new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(value)
const money = (value: number) => `₹${new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(value)}`
const tone = (status: string) => {
  const v = status.toUpperCase()
  if (['RELEASED', 'DELIVERED', 'ALLOCATED', 'COMPLETED', 'READY'].includes(v)) return 'success'
  if (['PENDING', 'QUARANTINED', 'QC_TESTING', 'IN_PROGRESS', 'PREPARING'].includes(v)) return 'warning'
  if (['REJECTED', 'FAILED', 'EXPIRED', 'RECALLED', 'CANCELLED'].includes(v)) return 'danger'
  return 'neutral'
}

export function ModulePage({ module, products, batches, warehouses, sales, onRefresh, notice }: { module: string; products: Product[]; batches: Batch[]; warehouses: WarehouseType[]; sales: Sale[]; onRefresh: () => Promise<void>; notice: Notice }) {
  if (module === 'Quality') return <QualityPage batches={batches} onRefresh={onRefresh} notice={notice} />
  if (module === 'Commercial') return <CommercialPage sales={sales} notice={notice} />
  if (module === 'Analytics') return <AnalyticsPage products={products} batches={batches} sales={sales} warehouses={warehouses} />
  if (module === 'Admin') return <AdminPage warehouses={warehouses} products={products} />
  return <OperationsPage products={products} batches={batches} warehouses={warehouses} onRefresh={onRefresh} notice={notice} />
}

function OperationsPage({ products, batches, warehouses, onRefresh, notice }: { products: Product[]; batches: Batch[]; warehouses: WarehouseType[]; onRefresh: () => Promise<void>; notice: Notice }) {
  const [query, setQuery] = useState('')
  const [showProduct, setShowProduct] = useState(false)
  const [showProduction, setShowProduction] = useState(false)
  const filtered = useMemo(() => batches.filter(b => `${b.batch_number} ${b.product_id}`.toLowerCase().includes(query.toLowerCase())), [batches, query])
  return <>
    <div className="module-actions"><div className="search-box wide"><Search size={16} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search batches, product IDs…" /></div><button className="secondary-btn" onClick={() => void onRefresh()}><RefreshCw size={15} /> REFRESH</button><button className="secondary-btn" onClick={() => setShowProduct(true)}><Plus size={15} /> NEW PRODUCT</button><button className="primary-btn" onClick={() => setShowProduction(true)}><Plus size={15} /> NEW PRODUCTION ORDER</button></div>
    <div className="module-kpis"><MiniStat icon={<Package size={18} />} label="ACTIVE PRODUCTS" value={String(products.filter(p => p.active).length)} /><MiniStat icon={<Warehouse size={18} />} label="WAREHOUSES" value={String(warehouses.filter(w => w.active).length)} /><MiniStat icon={<ClipboardCheck size={18} />} label="RELEASED BATCHES" value={String(batches.filter(b => b.status === 'RELEASED').length)} /><MiniStat icon={<ShieldAlert size={18} />} label="QC EXCEPTIONS" value={String(batches.filter(b => b.qc_status !== 'RELEASED').length)} /></div>
    <section className="panel module-table-panel"><PanelTitle title="LIVE OPERATIONS REGISTER" subtitle="Production batches, stock state and release readiness." /><div className="table-wrap"><table><thead><tr><th>BATCH</th><th>PRODUCT</th><th>WAREHOUSE</th><th>AVAILABLE</th><th>RESERVED</th><th>EXPIRY</th><th>QC</th><th>STATUS</th></tr></thead><tbody>{filtered.slice(0, 14).map(batch => { const product = products.find(p => p.id === batch.product_id); const warehouse = warehouses.find(w => w.id === batch.warehouse_id); return <tr key={batch.id}><td className="mono strong-cell">{batch.batch_number}</td><td>{product ? `${product.brand_name} ${product.strength ?? ''}` : batch.product_id.slice(0, 8)}</td><td>{warehouse?.name ?? '—'}</td><td className="mono">{fmt(Number(batch.quantity_available))}</td><td className="mono">{fmt(Number(batch.quantity_reserved))}</td><td className="mono">{batch.expiry_date}</td><td><span className={`status-pill ${tone(batch.qc_status)}`}>{batch.qc_status}</span></td><td><span className={`table-status ${tone(batch.status)}`}><span />{batch.status}</span></td></tr> })}</tbody></table></div></section>
    {showProduct && <ProductModal onClose={() => setShowProduct(false)} onDone={async msg => { setShowProduct(false); notice(msg); await onRefresh() }} />}
    {showProduction && <ProductionModal products={products} warehouses={warehouses} onClose={() => setShowProduction(false)} onDone={async msg => { setShowProduction(false); notice(msg); await onRefresh() }} />}
  </>
}

function QualityPage({ batches, onRefresh, notice }: { batches: Batch[]; onRefresh: () => Promise<void>; notice: Notice }) {
  const [query, setQuery] = useState('')
  const filtered = batches.filter(b => `${b.batch_number} ${b.qc_status} ${b.status}`.toLowerCase().includes(query.toLowerCase()))
  async function act(batch: Batch, kind: 'pass' | 'fail' | 'release') {
    try {
      if (kind === 'release') await api.releaseBatch(batch.id)
      else await api.recordQC(batch.id, { reference_number: `QC-${Date.now()}`, test_date: new Date().toISOString().slice(0, 10), result: kind === 'pass' ? 'PASSED' : 'FAILED', notes: kind === 'pass' ? 'Routine release testing passed.' : 'Quality exception recorded.' })
      notice(`${batch.batch_number}: ${kind === 'release' ? 'released' : kind === 'pass' ? 'QC passed' : 'QC failed'}`)
      await onRefresh()
    } catch (error) { notice(error instanceof Error ? error.message : 'Quality action failed') }
  }
  return <>
    <div className="module-actions"><div className="search-box wide"><Search size={16} /><input placeholder="Search batch / QC state…" value={query} onChange={e => setQuery(e.target.value)} /></div><button className="secondary-btn" onClick={() => void onRefresh()}><RefreshCw size={15} /> REFRESH</button></div>
    <div className="module-kpis"><MiniStat icon={<ClipboardCheck size={18} />} label="PENDING QC" value={String(batches.filter(b => b.qc_status === 'PENDING').length)} /><MiniStat icon={<CheckCircle2 size={18} />} label="PASSED" value={String(batches.filter(b => b.qc_status === 'PASSED' || b.qc_status === 'RELEASED').length)} /><MiniStat icon={<ShieldAlert size={18} />} label="FAILED / REJECTED" value={String(batches.filter(b => ['FAILED', 'REJECTED'].includes(b.qc_status)).length)} /><MiniStat icon={<Package size={18} />} label="RELEASED" value={String(batches.filter(b => b.status === 'RELEASED').length)} /></div>
    <section className="panel module-table-panel"><PanelTitle title="QUALITY CONTROL REGISTER" subtitle="QC status is tied to batch release eligibility." /><div className="table-wrap"><table><thead><tr><th>BATCH</th><th>MFG</th><th>EXPIRY</th><th>QC STATUS</th><th>BATCH STATUS</th><th>AVAILABLE</th><th>ACTION</th></tr></thead><tbody>{filtered.map(batch => <tr key={batch.id}><td className="mono strong-cell">{batch.batch_number}</td><td className="mono">{batch.manufacturing_date}</td><td className="mono">{batch.expiry_date}</td><td><span className={`status-pill ${tone(batch.qc_status)}`}>{batch.qc_status}</span></td><td><span className={`status-pill ${tone(batch.status)}`}>{batch.status}</span></td><td className="mono">{fmt(Number(batch.quantity_available))}</td><td className="row-actions">{batch.qc_status !== 'PASSED' && batch.qc_status !== 'RELEASED' && <button className="table-action success" onClick={() => void act(batch, 'pass')}>PASS</button>}{batch.qc_status !== 'FAILED' && <button className="table-action danger" onClick={() => void act(batch, 'fail')}>FAIL</button>}{batch.qc_status === 'PASSED' && batch.status !== 'RELEASED' && <button className="table-action success" onClick={() => void act(batch, 'release')}>RELEASE</button>}</td></tr>)}</tbody></table></div></section>
  </>
}

function CommercialPage({ sales, notice }: { sales: Sale[]; notice: Notice }) {
  const total = sales.reduce((s, sale) => s + Number(sale.total_amount || 0), 0)
  return <>
    <div className="module-actions"><button className="primary-btn" onClick={() => notice('Sales order workflow is available from the backend API.') }><Plus size={15} /> NEW SALES ORDER</button><button className="secondary-btn" onClick={() => notice('Shipment lifecycle is available from the backend API.') }><Truck size={15} /> SHIPMENTS</button><button className="secondary-btn" onClick={() => notice('Export lifecycle is available from the backend API.') }><Send size={15} /> EXPORTS</button></div>
    <div className="module-kpis"><MiniStat icon={<FileText size={18} />} label="ORDERS" value={String(sales.length)} /><MiniStat icon={<Package size={18} />} label="ALLOCATED" value={String(sales.filter(s => s.status === 'ALLOCATED').length)} /><MiniStat icon={<Truck size={18} />} label="DISPATCHED" value={String(sales.filter(s => s.status === 'DISPATCHED').length)} /><MiniStat icon={<ArrowRightLeft size={18} />} label="BOOKED VALUE" value={money(total)} /></div>
    <section className="panel module-table-panel"><PanelTitle title="COMMERCIAL REGISTER" subtitle="Sales orders and downstream fulfillment status." /><div className="table-wrap"><table><thead><tr><th>ORDER</th><th>CUSTOMER</th><th>STATUS</th><th>CURRENCY</th><th>TOTAL</th><th>CREATED</th></tr></thead><tbody>{sales.length ? sales.map(sale => <tr key={sale.id}><td className="mono strong-cell">{sale.order_number}</td><td className="mono">{sale.customer_id.slice(0, 8)}</td><td><span className={`status-pill ${tone(sale.status)}`}>{sale.status}</span></td><td className="mono">{sale.currency}</td><td className="mono">{money(Number(sale.total_amount))}</td><td className="mono">{new Date(sale.created_at).toLocaleString('en-IN')}</td></tr>) : <tr><td colSpan={6} className="empty-state">No sales orders returned by the API.</td></tr>}</tbody></table></div></section>
  </>
}

function AnalyticsPage({ products, batches, sales, warehouses }: { products: Product[]; batches: Batch[]; sales: Sale[]; warehouses: WarehouseType[] }) {
  const byStatus = ['RELEASED', 'QUARANTINED', 'QC_TESTING', 'REJECTED', 'EXPIRED'].map(status => ({ status, value: batches.filter(b => b.status === status).length }))
  return <>
    <div className="module-kpis"><MiniStat icon={<Package size={18} />} label="PRODUCTS" value={String(products.length)} /><MiniStat icon={<Warehouse size={18} />} label="WAREHOUSES" value={String(warehouses.length)} /><MiniStat icon={<ClipboardCheck size={18} />} label="BATCHES" value={String(batches.length)} /><MiniStat icon={<FileText size={18} />} label="SALES VALUE" value={money(sales.reduce((s, sale) => s + Number(sale.total_amount || 0), 0))} /></div>
    <div className="analytics-grid"><section className="panel"><PanelTitle title="BATCH STATUS DISTRIBUTION" subtitle="Current batch state across the connected facilities." />{byStatus.map(row => <div className="metric-row" key={row.status}><span>{row.status}</span><div className="metric-track"><span style={{ width: `${Math.min(100, Math.max(8, row.value / Math.max(1, batches.length) * 100))}%` }} /></div><strong>{row.value}</strong></div>)}</section><section className="panel"><PanelTitle title="OPERATING SIGNALS" subtitle="Operational indicators derived from live API responses." /><div className="signal-grid"><Signal title="RELEASE RATE" value={`${batches.length ? Math.round(batches.filter(b => b.status === 'RELEASED').length / batches.length * 100) : 0}%`} /><Signal title="QC BACKLOG" value={String(batches.filter(b => b.qc_status !== 'RELEASED').length)} /><Signal title="ACTIVE FACILITIES" value={String(warehouses.filter(w => w.active).length)} /><Signal title="AVG ORDER VALUE" value={sales.length ? money(sales.reduce((s, sale) => s + Number(sale.total_amount || 0), 0) / sales.length) : '₹0'} /></div></section></div>
  </>
}

function AdminPage({ warehouses, products }: { warehouses: WarehouseType[]; products: Product[] }) {
  return <>
    <div className="module-kpis"><MiniStat icon={<Users size={18} />} label="ROLE MODEL" value="10" /><MiniStat icon={<Warehouse size={18} />} label="WAREHOUSES" value={String(warehouses.length)} /><MiniStat icon={<Package size={18} />} label="PRODUCT RECORDS" value={String(products.length)} /><MiniStat icon={<ShieldAlert size={18} />} label="SECURITY" value="RLS ACTIVE" /></div>
    <div className="admin-grid"><section className="panel"><PanelTitle title="FACILITIES" subtitle="Warehouse master data available to the signed-in operator." />{warehouses.map(w => <div className="admin-row" key={w.id}><div><strong>{w.code}</strong><span>{w.name} · {w.location ?? 'Location not set'}</span></div><span className={`status-pill ${w.active ? 'success' : 'neutral'}`}>{w.active ? 'ACTIVE' : 'INACTIVE'}</span></div>)}</section><section className="panel"><PanelTitle title="ACCESS MODEL" subtitle="Frontend visibility follows the backend role model." /><div className="role-list">{['SUPER_ADMIN','ADMIN','PRODUCTION_MANAGER','QUALITY_MANAGER','INVENTORY_MANAGER','WAREHOUSE_MANAGER','SALES_MANAGER','ACCOUNTANT','AUDITOR','VIEWER'].map(role => <div key={role} className="role-chip"><ShieldAlert size={14} />{role}</div>)}</div></section></div>
  </>
}

function ProductModal({ onClose, onDone }: { onClose: () => void; onDone: (message: string) => void }) {
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState({ sku: '', brand_name: '', generic_name: '', dosage_form: 'Tablet', strength: '', route: 'Oral', category: 'Solid Dose', unit: 'unit', packaging: '', selling_price: '0', cost_price: '0', reorder_threshold: '0' })
  return <Modal title="NEW PRODUCT" onClose={onClose}><form className="form-grid" onSubmit={async e => { e.preventDefault(); setBusy(true); try { await api.createProduct({ ...form, selling_price: Number(form.selling_price), cost_price: Number(form.cost_price), reorder_threshold: Number(form.reorder_threshold) }); onDone('Product created successfully.') } catch (error) { onDone(error instanceof Error ? error.message : 'Product creation failed') } finally { setBusy(false) } }}><Field label="SKU"><input value={form.sku} required onChange={e => setForm({ ...form, sku: e.target.value })} /></Field><Field label="BRAND NAME"><input value={form.brand_name} required onChange={e => setForm({ ...form, brand_name: e.target.value })} /></Field><Field label="GENERIC NAME"><input value={form.generic_name} required onChange={e => setForm({ ...form, generic_name: e.target.value })} /></Field><Field label="STRENGTH"><input value={form.strength} onChange={e => setForm({ ...form, strength: e.target.value })} /></Field><Field label="DOSAGE FORM"><input value={form.dosage_form} onChange={e => setForm({ ...form, dosage_form: e.target.value })} /></Field><Field label="CATEGORY"><input value={form.category} onChange={e => setForm({ ...form, category: e.target.value })} /></Field><Field label="SELLING PRICE"><input type="number" min="0" value={form.selling_price} onChange={e => setForm({ ...form, selling_price: e.target.value })} /></Field><Field label="COST PRICE"><input type="number" min="0" value={form.cost_price} onChange={e => setForm({ ...form, cost_price: e.target.value })} /></Field><div className="modal-actions"><button type="button" className="secondary-btn" onClick={onClose}>CANCEL</button><button className="primary-btn" disabled={busy}>{busy ? 'CREATING…' : 'CREATE PRODUCT'}</button></div></form></Modal>
}

function ProductionModal({ products, warehouses, onClose, onDone }: { products: Product[]; warehouses: WarehouseType[]; onClose: () => void; onDone: (message: string) => void }) {
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState({ order_number: `PO-${Date.now().toString().slice(-8)}`, product_id: products[0]?.id ?? '', warehouse_id: warehouses[0]?.id ?? '', planned_quantity: '10000', notes: '' })
  return <Modal title="CREATE PRODUCTION ORDER" onClose={onClose}><form className="form-grid" onSubmit={async e => { e.preventDefault(); setBusy(true); try { await api.createProduction({ ...form, planned_quantity: Number(form.planned_quantity) }); onDone('Production order created.') } catch (error) { onDone(error instanceof Error ? error.message : 'Production order creation failed') } finally { setBusy(false) } }}><Field label="ORDER NUMBER"><input value={form.order_number} onChange={e => setForm({ ...form, order_number: e.target.value })} /></Field><Field label="PRODUCT"><select value={form.product_id} onChange={e => setForm({ ...form, product_id: e.target.value })}>{products.map(p => <option key={p.id} value={p.id}>{p.brand_name} {p.strength ?? ''}</option>)}</select></Field><Field label="WAREHOUSE"><select value={form.warehouse_id} onChange={e => setForm({ ...form, warehouse_id: e.target.value })}>{warehouses.map(w => <option key={w.id} value={w.id}>{w.code} — {w.name}</option>)}</select></Field><Field label="PLANNED QUANTITY"><input type="number" min="1" value={form.planned_quantity} onChange={e => setForm({ ...form, planned_quantity: e.target.value })} /></Field><Field label="NOTES"><textarea value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} /></Field><div className="modal-actions"><button type="button" className="secondary-btn" onClick={onClose}>CANCEL</button><button className="primary-btn" disabled={busy}>{busy ? 'CREATING…' : 'CREATE ORDER'}</button></div></form></Modal>
}

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) { return <div className="modal-backdrop"><div className="modal"><div className="modal-head"><div><span>PHARMACORE CONTROL</span><h2>{title}</h2></div><button className="icon-btn" onClick={onClose}>×</button></div>{children}</div></div> }
function Field({ label, children }: { label: string; children: React.ReactNode }) { return <label className="field"><span>{label}</span>{children}</label> }
function MiniStat({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) { return <div className="mini-stat"><span className="mini-icon">{icon}</span><div><span>{label}</span><strong>{value}</strong></div></div> }
function PanelTitle({ title, subtitle }: { title: string; subtitle: string }) { return <div className="module-panel-title"><div><h2>{title}</h2><p>{subtitle}</p></div></div> }
function Signal({ title, value }: { title: string; value: string }) { return <div className="signal"><span>{title}</span><strong>{value}</strong></div> }
