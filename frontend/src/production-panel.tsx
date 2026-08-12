import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { CheckCircle2, Database, Factory, PackageCheck, Play, RefreshCw, Square, Warehouse, X, Zap } from 'lucide-react'
import { api, type Batch, type Product, type ProductionOrder, type Sale, type Warehouse as WarehouseType } from './lib/api'
import { EnterprisePage } from './enterprise'

type Notice = (message: string) => void

export function ProductionControlPanel({ onRefresh, notice }: { onRefresh: () => Promise<void>; notice: Notice }) {
  const [orders, setOrders] = useState<ProductionOrder[]>([])
  const [completeId, setCompleteId] = useState<string | null>(null)
  const [tab, setTab] = useState<'control' | 'production' | 'inventory' | 'master'>('control')
  const [products, setProducts] = useState<Product[]>([])
  const [batches, setBatches] = useState<Batch[]>([])
  const [warehouses, setWarehouses] = useState<WarehouseType[]>([])
  const [sales, setSales] = useState<Sale[]>([])

  async function load() {
    try {
      const [o, ps, bs, ws, ss] = await Promise.all([api.productionOrders(), api.products(), api.batches(), api.warehouses(), api.sales()])
      setOrders(o); setProducts(ps); setBatches(bs); setWarehouses(ws); setSales(ss)
    } catch (error) { notice(error instanceof Error ? error.message : 'Unable to load operational data') }
  }
  useEffect(() => { void load() }, [])

  async function action(id: string, kind: 'plan' | 'approve' | 'start') {
    try {
      if (kind === 'plan') await api.planProduction(id)
      if (kind === 'approve') await api.approveProduction(id)
      if (kind === 'start') await api.startProduction(id)
      notice(`Production order ${kind} action completed.`)
      await load(); await onRefresh()
    } catch (error) { notice(error instanceof Error ? error.message : 'Production transition failed') }
  }

  const refreshEnterprise = async () => { await load(); await onRefresh() }

  return <>
    <div className="enterprise-tabs">
      <button className={tab === 'control' ? 'active' : ''} onClick={() => setTab('control')}><Factory size={15}/> CONTROL</button>
      <button className={tab === 'production' ? 'active' : ''} onClick={() => setTab('production')}><PackageCheck size={15}/> PRODUCTION</button>
      <button className={tab === 'inventory' ? 'active' : ''} onClick={() => setTab('inventory')}><Warehouse size={15}/> INVENTORY</button>
      <button className={tab === 'master' ? 'active' : ''} onClick={() => setTab('master')}><Database size={15}/> MASTER DATA</button>
      <button className="enterprise-refresh" onClick={() => void load()}><RefreshCw size={15}/></button>
    </div>
    {tab === 'control' && <section className="panel module-table-panel" style={{ marginTop: 24 }}>
      <div className="module-panel-title"><div><h2>PRODUCTION CONTROL REGISTER</h2><p>Validated lifecycle: draft → planned → approved → in progress → completed.</p></div></div>
      <div className="table-wrap"><table><thead><tr><th>ORDER</th><th>PRODUCT</th><th>PLANNED</th><th>ACTUAL</th><th>STATUS</th><th>ACTION</th></tr></thead><tbody>{orders.length ? orders.map(order => <tr key={order.id}><td className="mono strong-cell">{order.order_number}</td><td className="mono">{order.product_id.slice(0, 8)}</td><td className="mono">{order.planned_quantity}</td><td className="mono">{order.actual_quantity}</td><td><span className={`status-pill ${tone(order.status)}`}>{order.status}</span></td><td className="row-actions">{order.status === 'DRAFT' && <button className="table-action success" onClick={() => void action(order.id, 'plan')}>PLAN</button>}{order.status === 'PLANNED' && <button className="table-action success" onClick={() => void action(order.id, 'approve')}>APPROVE</button>}{order.status === 'APPROVED' && <button className="table-action success" onClick={() => void action(order.id, 'start')}>START</button>}{order.status === 'IN_PROGRESS' && <button className="table-action success" onClick={() => setCompleteId(order.id)}>COMPLETE</button>}</td></tr>) : <tr><td colSpan={6} className="empty-state">No production orders returned by the API.</td></tr>}</tbody></table></div>
    </section>}
    {tab === 'production' && <EnterprisePage module="Production" products={products} batches={batches} warehouses={warehouses} sales={sales} onRefresh={refreshEnterprise} notice={notice} />}
    {tab === 'inventory' && <EnterprisePage module="Inventory" products={products} batches={batches} warehouses={warehouses} sales={sales} onRefresh={refreshEnterprise} notice={notice} />}
    {tab === 'master' && <EnterprisePage module="Master Data" products={products} batches={batches} warehouses={warehouses} sales={sales} onRefresh={refreshEnterprise} notice={notice} />}
    {completeId && <CompleteProductionModal order={orders.find(order => order.id === completeId)!} onClose={() => setCompleteId(null)} onDone={async message => { setCompleteId(null); notice(message); await load(); await onRefresh() }} />}
  </>
}

function CompleteProductionModal({ order, onClose, onDone }: { order: ProductionOrder; onClose: () => void; onDone: (message: string) => Promise<void> }) {
  const today = new Date(); const expiry = new Date(today); expiry.setFullYear(expiry.getFullYear() + 3)
  const [form, setForm] = useState({ actual_quantity: String(order.planned_quantity), batch_number: `${order.order_number}-B01`, manufacturing_date: today.toISOString().slice(0, 10), expiry_date: expiry.toISOString().slice(0, 10) })
  const submit = async (event: FormEvent) => { event.preventDefault(); try { await api.completeProduction(order.id, { actual_quantity: Number(form.actual_quantity), batch_number: form.batch_number, manufacturing_date: form.manufacturing_date, expiry_date: form.expiry_date }); await onDone('Production completed and batch created.') } catch (error) { await onDone(error instanceof Error ? error.message : 'Production completion failed') } }
  return <div className="modal-backdrop"><div className="modal"><div className="modal-head"><div><span>PHARMACORE CONTROL</span><h2>COMPLETE PRODUCTION</h2></div><button className="icon-btn" onClick={onClose}><X size={18}/></button></div><form className="form-grid" onSubmit={submit}><Field label="ACTUAL QUANTITY"><input type="number" min="1" required value={form.actual_quantity} onChange={e => setForm({ ...form, actual_quantity: e.target.value })}/></Field><Field label="BATCH NUMBER"><input required value={form.batch_number} onChange={e => setForm({ ...form, batch_number: e.target.value })}/></Field><Field label="MANUFACTURING DATE"><input type="date" required value={form.manufacturing_date} onChange={e => setForm({ ...form, manufacturing_date: e.target.value })}/></Field><Field label="EXPIRY DATE"><input type="date" required value={form.expiry_date} onChange={e => setForm({ ...form, expiry_date: e.target.value })}/></Field><div className="modal-actions"><button type="button" className="secondary-btn" onClick={onClose}>CANCEL</button><button className="primary-btn">COMPLETE & CREATE BATCH</button></div></form></div></div>
}
function tone(value: string) { if (['COMPLETED','APPROVED'].includes(value)) return 'success'; if (['DRAFT','PLANNED','IN_PROGRESS'].includes(value)) return 'warning'; if (['CANCELLED','REJECTED'].includes(value)) return 'danger'; return 'neutral' }
function Field({ label, children }: { label: string; children: ReactNode }) { return <label className="field"><span>{label}</span>{children}</label> }
void CheckCircle2; void Play; void Square; void Zap
