import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { CheckCircle2, FileText, Plus, RotateCcw, Send, Truck, UserPlus, X } from 'lucide-react'
import {
  api,
  type Batch,
  type Customer,
  type ExportRecord,
  type Invoice,
  type Product,
  type ReturnRecord,
  type Sale,
  type Shipment,
  type Warehouse,
} from './lib/api'

type Notice = (message: string) => void

const money = (value: number) => `₹${new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(value)}`
const tone = (value: string) => {
  if (['DELIVERED', 'DISPATCHED', 'ALLOCATED', 'CONFIRMED', 'READY'].includes(value)) return 'success'
  if (['PREPARING', 'DRAFT', 'PENDING'].includes(value)) return 'warning'
  if (['CANCELLED', 'FAILED', 'REJECTED'].includes(value)) return 'danger'
  return 'neutral'
}

export function CommercialWorkspace({
  products,
  batches,
  warehouses,
  sales,
  onRefresh,
  notice,
}: {
  products: Product[]
  batches: Batch[]
  warehouses: Warehouse[]
  sales: Sale[]
  onRefresh: () => Promise<void>
  notice: Notice
}) {
  const [customers, setCustomers] = useState<Customer[]>([])
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [shipments, setShipments] = useState<Shipment[]>([])
  const [exports, setExports] = useState<ExportRecord[]>([])
  const [returns, setReturns] = useState<ReturnRecord[]>([])
  const [modal, setModal] = useState<'customer' | 'sale' | 'shipment' | 'export' | 'return' | null>(null)

  async function refreshCommercial() {
    await Promise.all([
      onRefresh(),
      api.customers().then(setCustomers),
      api.invoices().then(setInvoices),
      api.shipments().then(setShipments),
      api.exports().then(setExports),
      api.returns().then(setReturns),
    ])
  }

  useEffect(() => {
    void refreshCommercial().catch(() => undefined)
  }, [])

  const total = sales.reduce((sum, sale) => sum + Number(sale.total_amount || 0), 0)
  const allocated = sales.filter((sale) => sale.status === 'ALLOCATED').length
  const dispatched = sales.filter((sale) => sale.status === 'DISPATCHED').length

  async function afterAction(message: string) {
    setModal(null)
    notice(message)
    try {
      await refreshCommercial()
    } catch {
      notice('Action succeeded, but refresh failed.')
    }
  }

  return (
    <>
      <div className="module-actions">
        <button className="primary-btn" onClick={() => setModal('sale')}><Plus size={15} /> NEW SALES ORDER</button>
        <button className="secondary-btn" onClick={() => setModal('shipment')}><Truck size={15} /> NEW SHIPMENT</button>
        <button className="secondary-btn" onClick={() => setModal('export')}><Send size={15} /> NEW EXPORT</button>
        <button className="secondary-btn" onClick={() => setModal('customer')}><UserPlus size={15} /> CUSTOMER</button>
        <button className="secondary-btn" onClick={() => setModal('return')}><RotateCcw size={15} /> RETURN</button>
        <button className="secondary-btn" onClick={() => void refreshCommercial()}><CheckCircle2 size={15} /> REFRESH</button>
      </div>

      <div className="module-kpis">
        <MiniStat icon={<FileText size={18} />} label="SALES ORDERS" value={String(sales.length)} />
        <MiniStat icon={<CheckCircle2 size={18} />} label="ALLOCATED" value={String(allocated)} />
        <MiniStat icon={<Truck size={18} />} label="DISPATCHED" value={String(dispatched)} />
        <MiniStat icon={<FileText size={18} />} label="BOOKED VALUE" value={money(total)} />
      </div>

      <section className="panel module-table-panel">
        <PanelTitle title="SALES ORDER REGISTER" subtitle="Sales, invoice and fulfillment state from the live API." />
        <div className="table-wrap">
          <table>
            <thead><tr><th>ORDER</th><th>CUSTOMER</th><th>STATUS</th><th>TOTAL</th><th>CREATED</th></tr></thead>
            <tbody>
              {sales.length ? sales.map((sale) => (
                <tr key={sale.id}>
                  <td className="mono strong-cell">{sale.order_number}</td>
                  <td>{customers.find((customer) => customer.id === sale.customer_id)?.name ?? sale.customer_id.slice(0, 8)}</td>
                  <td><span className={`status-pill ${tone(sale.status)}`}>{sale.status}</span></td>
                  <td className="mono">{money(Number(sale.total_amount))}</td>
                  <td className="mono">{new Date(sale.created_at).toLocaleString('en-IN')}</td>
                </tr>
              )) : <tr><td colSpan={5} className="empty-state">No sales orders returned by the API.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      <div className="analytics-grid" style={{ marginTop: 18 }}>
        <ShipmentPanel shipments={shipments} afterAction={afterAction} notice={notice} />
        <RegistryPanel exports={exports} returns={returns} />
      </div>

      {modal === 'customer' && <CustomerModal onClose={() => setModal(null)} onDone={afterAction} />}
      {modal === 'sale' && <SaleModal products={products} customers={customers} warehouses={warehouses} onClose={() => setModal(null)} onDone={afterAction} />}
      {modal === 'shipment' && <ShipmentModal sales={sales} onClose={() => setModal(null)} onDone={afterAction} />}
      {modal === 'export' && <ExportModal products={products} batches={batches} onClose={() => setModal(null)} onDone={afterAction} />}
      {modal === 'return' && <ReturnModal customers={customers} products={products} batches={batches} invoices={invoices} onClose={() => setModal(null)} onDone={afterAction} />}
    </>
  )
}

function ShipmentPanel({ shipments, afterAction, notice }: { shipments: Shipment[]; afterAction: (message: string) => Promise<void>; notice: Notice }) {
  return (
    <section className="panel">
      <PanelTitle title="SHIPMENT REGISTER" subtitle="Create, dispatch and deliver against allocated sales orders." />
      <div className="table-wrap">
        <table>
          <thead><tr><th>SHIPMENT</th><th>ORDER</th><th>DESTINATION</th><th>STATUS</th><th>ACTION</th></tr></thead>
          <tbody>
            {shipments.length ? shipments.map((shipment) => (
              <tr key={shipment.id}>
                <td className="mono strong-cell">{shipment.shipment_number}</td>
                <td className="mono">{shipment.sales_order_id?.slice(0, 8) ?? '—'}</td>
                <td>{shipment.destination}</td>
                <td><span className={`status-pill ${tone(shipment.status)}`}>{shipment.status}</span></td>
                <td className="row-actions">
                  {['PREPARING', 'READY'].includes(shipment.status) && (
                    <button className="table-action success" onClick={async () => {
                      try { await api.dispatchShipment(shipment.id); await afterAction('Shipment dispatched.') } catch (error) { notice(error instanceof Error ? error.message : 'Dispatch failed') }
                    }}>DISPATCH</button>
                  )}
                  {shipment.status === 'DISPATCHED' && (
                    <button className="table-action success" onClick={async () => {
                      try { await api.deliverShipment(shipment.id); await afterAction('Shipment delivered.') } catch (error) { notice(error instanceof Error ? error.message : 'Delivery failed') }
                    }}>DELIVER</button>
                  )}
                </td>
              </tr>
            )) : <tr><td colSpan={5} className="empty-state">No shipments yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function RegistryPanel({ exports, returns }: { exports: ExportRecord[]; returns: ReturnRecord[] }) {
  return (
    <section className="panel">
      <PanelTitle title="EXPORT / RETURN REGISTER" subtitle="Cross-border exports and returned pharmaceutical stock." />
      <div className="table-wrap">
        <table>
          <thead><tr><th>TYPE</th><th>REFERENCE</th><th>STATUS</th><th>VALUE / QTY</th></tr></thead>
          <tbody>
            {exports.slice(0, 8).map((item) => (
              <tr key={`e-${item.id}`}><td>EXPORT</td><td className="mono">{item.export_number}</td><td><span className={`status-pill ${tone(item.status)}`}>{item.status}</span></td><td className="mono">{item.currency} {Number(item.export_value).toLocaleString('en-IN')}</td></tr>
            ))}
            {returns.slice(0, 8).map((item) => (
              <tr key={`r-${item.id}`}><td>RETURN</td><td className="mono">{item.return_number}</td><td><span className="status-pill warning">{item.disposition ?? 'QUARANTINE'}</span></td><td className="mono">{item.quantity}</td></tr>
            ))}
            {!exports.length && !returns.length && <tr><td colSpan={4} className="empty-state">No export or return records yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function CustomerModal({ onClose, onDone }: { onClose: () => void; onDone: (message: string) => Promise<void> }) {
  const [form, setForm] = useState({ code: '', name: '', email: '', phone: '', address: '' })
  return (
    <Modal title="NEW CUSTOMER" onClose={onClose}>
      <form className="form-grid" onSubmit={async (event) => {
        event.preventDefault()
        try { await api.createCustomer(form); await onDone('Customer created successfully.') } catch (error) { await onDone(error instanceof Error ? error.message : 'Customer creation failed') }
      }}>
        <Field label="CODE"><input required value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value })} /></Field>
        <Field label="NAME"><input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></Field>
        <Field label="EMAIL"><input type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} /></Field>
        <Field label="PHONE"><input value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} /></Field>
        <Field label="ADDRESS"><textarea value={form.address} onChange={(event) => setForm({ ...form, address: event.target.value })} /></Field>
        <Actions onClose={onClose} />
      </form>
    </Modal>
  )
}

function SaleModal({ products, customers, warehouses, onClose, onDone }: { products: Product[]; customers: Customer[]; warehouses: Warehouse[]; onClose: () => void; onDone: (message: string) => Promise<void> }) {
  const [form, setForm] = useState({ order_number: `SO-${Date.now().toString().slice(-8)}`, customer_id: customers[0]?.id ?? '', warehouse_id: warehouses[0]?.id ?? '', product_id: products[0]?.id ?? '', quantity: '1000', unit_price: String(products[0]?.selling_price ?? 0), currency: 'INR' })
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    try {
      await api.createSale({ order_number: form.order_number, customer_id: form.customer_id, currency: form.currency, items: [{ product_id: form.product_id, quantity: Number(form.quantity), unit_price: Number(form.unit_price) }] }, form.warehouse_id)
      await onDone('Sales order created and FEFO allocation attempted.')
    } catch (error) { await onDone(error instanceof Error ? error.message : 'Sales order creation failed') }
  }
  return <Modal title="NEW SALES ORDER" onClose={onClose}><form className="form-grid" onSubmit={submit}><Field label="ORDER NUMBER"><input required value={form.order_number} onChange={(event) => setForm({ ...form, order_number: event.target.value })} /></Field><Field label="CUSTOMER"><select required value={form.customer_id} onChange={(event) => setForm({ ...form, customer_id: event.target.value })}>{customers.map((customer) => <option key={customer.id} value={customer.id}>{customer.code} — {customer.name}</option>)}</select></Field><Field label="WAREHOUSE"><select value={form.warehouse_id} onChange={(event) => setForm({ ...form, warehouse_id: event.target.value })}>{warehouses.map((warehouse) => <option key={warehouse.id} value={warehouse.id}>{warehouse.code} — {warehouse.name}</option>)}</select></Field><Field label="PRODUCT"><select value={form.product_id} onChange={(event) => { const product = products.find((item) => item.id === event.target.value); setForm({ ...form, product_id: event.target.value, unit_price: String(product?.selling_price ?? 0) }) }}>{products.map((product) => <option key={product.id} value={product.id}>{product.brand_name} {product.strength ?? ''}</option>)}</select></Field><Field label="QUANTITY"><input type="number" min="1" required value={form.quantity} onChange={(event) => setForm({ ...form, quantity: event.target.value })} /></Field><Field label="UNIT PRICE"><input type="number" min="0" step="0.01" value={form.unit_price} onChange={(event) => setForm({ ...form, unit_price: event.target.value })} /></Field><Actions onClose={onClose} /></form></Modal>
}

function ShipmentModal({ sales, onClose, onDone }: { sales: Sale[]; onClose: () => void; onDone: (message: string) => Promise<void> }) {
  const eligible = sales.filter((sale) => sale.status === 'ALLOCATED')
  const [form, setForm] = useState({ sales_order_id: eligible[0]?.id ?? '', destination: '', carrier: '', tracking_number: '' })
  return <Modal title="NEW SHIPMENT" onClose={onClose}><form className="form-grid" onSubmit={async (event) => { event.preventDefault(); try { await api.createShipment({ sales_order_id: form.sales_order_id, destination: form.destination, carrier: form.carrier, tracking_number: form.tracking_number || undefined }); await onDone('Shipment created. Dispatch when ready.') } catch (error) { await onDone(error instanceof Error ? error.message : 'Shipment creation failed') } }}><Field label="ALLOCATED SALES ORDER"><select required value={form.sales_order_id} onChange={(event) => setForm({ ...form, sales_order_id: event.target.value })}>{eligible.map((sale) => <option key={sale.id} value={sale.id}>{sale.order_number}</option>)}</select></Field><Field label="DESTINATION"><input required value={form.destination} onChange={(event) => setForm({ ...form, destination: event.target.value })} /></Field><Field label="CARRIER"><input value={form.carrier} onChange={(event) => setForm({ ...form, carrier: event.target.value })} /></Field><Field label="TRACKING NUMBER"><input value={form.tracking_number} onChange={(event) => setForm({ ...form, tracking_number: event.target.value })} /></Field><Actions onClose={onClose} /></form></Modal>
}

function ExportModal({ products, batches, onClose, onDone }: { products: Product[]; batches: Batch[]; onClose: () => void; onDone: (message: string) => Promise<void> }) {
  const eligible = batches.filter((batch) => batch.status === 'RELEASED' && new Date(batch.expiry_date) > new Date())
  const [form, setForm] = useState({ export_number: `EXP-${Date.now().toString().slice(-8)}`, destination_country: 'IN', importer: '', product_id: products[0]?.id ?? '', batch_id: '', quantity: '1000', currency: 'INR', export_value: '0' })
  const productBatches = eligible.filter((batch) => batch.product_id === form.product_id)
  const selectedBatch = form.batch_id || productBatches[0]?.id || ''
  return <Modal title="NEW EXPORT" onClose={onClose}><form className="form-grid" onSubmit={async (event) => { event.preventDefault(); try { await api.createExport({ ...form, batch_id: selectedBatch, quantity: Number(form.quantity), export_value: Number(form.export_value) }); await onDone('Export created and warehouse stock reconciled.') } catch (error) { await onDone(error instanceof Error ? error.message : 'Export failed') } }}><Field label="EXPORT NUMBER"><input required value={form.export_number} onChange={(event) => setForm({ ...form, export_number: event.target.value })} /></Field><Field label="COUNTRY CODE"><input required maxLength={2} value={form.destination_country} onChange={(event) => setForm({ ...form, destination_country: event.target.value.toUpperCase() })} /></Field><Field label="IMPORTER"><input required value={form.importer} onChange={(event) => setForm({ ...form, importer: event.target.value })} /></Field><Field label="PRODUCT"><select value={form.product_id} onChange={(event) => setForm({ ...form, product_id: event.target.value, batch_id: '' })}>{products.map((product) => <option key={product.id} value={product.id}>{product.brand_name} {product.strength ?? ''}</option>)}</select></Field><Field label="RELEASED BATCH"><select required value={selectedBatch} onChange={(event) => setForm({ ...form, batch_id: event.target.value })}>{productBatches.map((batch) => <option key={batch.id} value={batch.id}>{batch.batch_number} · {batch.quantity_available}</option>)}</select></Field><Field label="QUANTITY"><input required type="number" min="1" value={form.quantity} onChange={(event) => setForm({ ...form, quantity: event.target.value })} /></Field><Field label="EXPORT VALUE"><input required type="number" min="0" step="0.01" value={form.export_value} onChange={(event) => setForm({ ...form, export_value: event.target.value })} /></Field><Actions onClose={onClose} /></form></Modal>
}

function ReturnModal({ customers, products, batches, invoices, onClose, onDone }: { customers: Customer[]; products: Product[]; batches: Batch[]; invoices: Invoice[]; onClose: () => void; onDone: (message: string) => Promise<void> }) {
  const soldBatches = batches.filter((batch) => batch.quantity_sold > 0)
  const selectableBatches = soldBatches.length ? soldBatches : batches
  const [form, setForm] = useState({ return_number: `RET-${Date.now().toString().slice(-8)}`, invoice_id: invoices[0]?.id ?? '', customer_id: customers[0]?.id ?? '', product_id: products[0]?.id ?? '', batch_id: selectableBatches[0]?.id ?? '', quantity: '1', reason: 'Customer return' })
  return <Modal title="RECEIVE RETURN" onClose={onClose}><form className="form-grid" onSubmit={async (event) => { event.preventDefault(); try { await api.createReturn({ ...form, quantity: Number(form.quantity), disposition: 'QUARANTINE' }); await onDone('Return received and placed into inspection flow.') } catch (error) { await onDone(error instanceof Error ? error.message : 'Return intake failed') } }}><Field label="RETURN NUMBER"><input required value={form.return_number} onChange={(event) => setForm({ ...form, return_number: event.target.value })} /></Field><Field label="INVOICE"><select required value={form.invoice_id} onChange={(event) => setForm({ ...form, invoice_id: event.target.value })}>{invoices.map((invoice) => <option key={invoice.id} value={invoice.id}>{invoice.invoice_number}</option>)}</select></Field><Field label="CUSTOMER"><select required value={form.customer_id} onChange={(event) => setForm({ ...form, customer_id: event.target.value })}>{customers.map((customer) => <option key={customer.id} value={customer.id}>{customer.name}</option>)}</select></Field><Field label="SOLD PRODUCT"><select value={form.product_id} onChange={(event) => setForm({ ...form, product_id: event.target.value })}>{products.map((product) => <option key={product.id} value={product.id}>{product.brand_name} {product.strength ?? ''}</option>)}</select></Field><Field label="SOLD BATCH"><select required value={form.batch_id} onChange={(event) => setForm({ ...form, batch_id: event.target.value })}>{selectableBatches.map((batch) => <option key={batch.id} value={batch.id}>{batch.batch_number} · sold {batch.quantity_sold}</option>)}</select></Field><Field label="QUANTITY"><input type="number" min="1" required value={form.quantity} onChange={(event) => setForm({ ...form, quantity: event.target.value })} /></Field><Field label="REASON"><input required value={form.reason} onChange={(event) => setForm({ ...form, reason: event.target.value })} /></Field><Actions onClose={onClose} /></form></Modal>
}

function MiniStat({ icon, label, value }: { icon: ReactNode; label: string; value: string }) { return <div className="mini-stat"><span className="mini-icon">{icon}</span><div><span>{label}</span><strong>{value}</strong></div></div> }
function PanelTitle({ title, subtitle }: { title: string; subtitle: string }) { return <div className="module-panel-title"><div><h2>{title}</h2><p>{subtitle}</p></div></div> }
function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) { return <div className="modal-backdrop"><div className="modal"><div className="modal-head"><div><span>PHARMACORE CONTROL</span><h2>{title}</h2></div><button className="icon-btn" onClick={onClose}><X size={18} /></button></div>{children}</div></div> }
function Field({ label, children }: { label: string; children: ReactNode }) { return <label className="field"><span>{label}</span>{children}</label> }
function Actions({ onClose }: { onClose: () => void }) { return <div className="modal-actions"><button type="button" className="secondary-btn" onClick={onClose}>CANCEL</button><button className="primary-btn">SAVE / SUBMIT</button></div> }
