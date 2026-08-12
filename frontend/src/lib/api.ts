const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1'
let token = localStorage.getItem('pharma_access_token') ?? ''

export type User = { id: string; email: string; full_name: string; role: string; active: boolean; created_at: string }
export type Product = { id: string; sku: string; brand_name: string; generic_name: string; strength?: string | null; dosage_form: string; route?: string | null; category?: string | null; manufacturer?: string | null; unit: string; packaging?: string | null; selling_price: number; cost_price: number; reorder_threshold: number; active: boolean; created_at: string }
export type Batch = { id: string; batch_number: string; product_id: string; manufacturing_date: string; expiry_date: string; quantity_produced: number; quantity_available: number; quantity_reserved: number; quantity_sold: number; quantity_rejected: number; qc_status: string; status: string; warehouse_id?: string | null }
export type ProductionOrder = { id: string; order_number: string; product_id: string; planned_quantity: number; actual_quantity: number; warehouse_id?: string | null; status: string; notes?: string | null; started_at?: string | null; completed_at?: string | null; created_at: string }
export type Sale = { id: string; order_number: string; customer_id: string; status: string; currency: string; total_amount: number; created_at: string }
export type Warehouse = { id: string; code: string; name: string; location?: string | null; active: boolean }
export type InventoryRow = { product_id: string; warehouse_id: string; net_quantity: string }
export type Customer = { id: string; name: string; code: string; email?: string | null; phone?: string | null; address?: string | null; active: boolean }
export type Invoice = { id: string; invoice_number: string; sales_order_id: string; issue_date: string; currency: string; subtotal: number; tax_amount: number; total_amount: number; created_at: string }
export type Shipment = { id: string; shipment_number: string; sales_order_id?: string | null; destination: string; carrier?: string | null; tracking_number?: string | null; dispatch_date?: string | null; delivery_date?: string | null; status: string; created_at: string }
export type ExportRecord = { id: string; export_number: string; destination_country: string; importer: string; currency: string; export_value: number; export_date?: string | null; shipment_id?: string | null; status: string; reference_document?: string | null; product_id?: string | null; batch_id?: string | null; quantity: number; created_at: string }
export type ReturnRecord = { id: string; return_number: string; invoice_id: string; customer_id: string; product_id: string; batch_id: string; quantity: number; reason: string; return_condition?: string | null; inspection_result?: string | null; disposition?: string | null; created_at: string }
export type ProductCreate = { sku: string; brand_name: string; generic_name: string; strength?: string; dosage_form: string; route?: string; category?: string; manufacturer?: string; unit?: string; packaging?: string; selling_price: number; cost_price: number; reorder_threshold: number }
export type ProductionCreate = { order_number: string; product_id: string; planned_quantity: number; warehouse_id?: string; notes?: string }
export type ProductionComplete = { actual_quantity: number; batch_number: string; manufacturing_date: string; expiry_date: string }
export type QCRequest = { reference_number: string; test_date: string; result: 'PASSED' | 'FAILED'; notes?: string }
export type SaleCreate = { order_number: string; customer_id: string; currency: string; items: { product_id: string; quantity: number; unit_price: number }[] }
export type UserCreate = { email: string; full_name: string; password: string; role: string }

export function setToken(next: string) { token = next; if (next) localStorage.setItem('pharma_access_token', next); else localStorage.removeItem('pharma_access_token') }
export function getToken() { return token }

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })
  if (!res.ok) { const body = await res.json().catch(() => ({})) as { detail?: string }; throw new Error(body.detail || `Request failed (${res.status})`) }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string }>('/health'),
  ready: () => request<{ status: string; database: string }>('/ready'),
  me: () => request<User>('/auth/me'),
  login: (email: string, password: string) => request<{ access_token: string; expires_in: number; user: User }>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  register: (data: UserCreate) => request<User>('/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  users: () => request<User[]>('/users'),
  products: (search = '') => request<Product[]>(`/products?limit=200${search ? `&search=${encodeURIComponent(search)}` : ''}`),
  createProduct: (data: ProductCreate) => request<Product>('/products', { method: 'POST', body: JSON.stringify(data) }),
  batches: () => request<Batch[]>('/batches'),
  releaseBatch: (id: string) => request<Batch>(`/batches/${id}/release`, { method: 'POST' }),
  recordQC: (id: string, data: QCRequest) => request<Batch>(`/batches/${id}/qc`, { method: 'POST', body: JSON.stringify(data) }),
  warehouses: () => request<Warehouse[]>('/warehouses'),
  productionOrders: () => request<ProductionOrder[]>('/production-orders'),
  createProduction: (data: ProductionCreate) => request<ProductionOrder>('/production-orders', { method: 'POST', body: JSON.stringify(data) }),
  planProduction: (id: string) => request<ProductionOrder>(`/production-orders/${id}/plan`, { method: 'POST' }),
  approveProduction: (id: string) => request<ProductionOrder>(`/production-orders/${id}/approve`, { method: 'POST' }),
  startProduction: (id: string) => request<ProductionOrder>(`/production-orders/${id}/start`, { method: 'POST' }),
  completeProduction: (id: string, data: ProductionComplete) => request<Batch>(`/production-orders/${id}/complete`, { method: 'POST', body: JSON.stringify(data) }),
  sales: () => request<Sale[]>('/sales'),
  createSale: (data: SaleCreate, warehouseId: string) => request<Sale>(`/sales?warehouse_id=${encodeURIComponent(warehouseId)}`, { method: 'POST', body: JSON.stringify(data) }),
  inventory: () => request<InventoryRow[]>('/reports/inventory'),
  transferStock: (data: { product_id: string; batch_id: string; from_warehouse_id: string; to_warehouse_id: string; quantity: number; reason?: string }) => request<void>('/inventory/transfers', { method: 'POST', body: JSON.stringify(data) }),
  customers: () => request<Customer[]>('/customers'),
  createCustomer: (data: { code: string; name: string; email?: string; phone?: string; address?: string }) => request('/customers', { method: 'POST', body: JSON.stringify(data) }),
  invoices: () => request<Invoice[]>('/invoices'),
  shipments: () => request<Shipment[]>('/shipments'),
  createShipment: (data: { shipment_number?: string; sales_order_id?: string; destination: string; carrier?: string; tracking_number?: string }) => request<Shipment>('/shipments', { method: 'POST', body: JSON.stringify(data) }),
  dispatchShipment: (id: string) => request<Shipment>(`/shipments/${id}/dispatch`, { method: 'POST' }),
  deliverShipment: (id: string) => request<Shipment>(`/shipments/${id}/deliver`, { method: 'POST' }),
  exports: () => request<ExportRecord[]>('/exports'),
  createExport: (data: { export_number: string; destination_country: string; importer: string; product_id: string; batch_id: string; quantity: number; currency: string; export_value: number; shipment_id?: string; export_date?: string; reference_document?: string }) => request('/exports', { method: 'POST', body: JSON.stringify(data) }),
  returns: () => request<ReturnRecord[]>('/returns'),
  createReturn: (data: { return_number: string; invoice_id: string; customer_id: string; product_id: string; batch_id: string; quantity: number; reason: string; return_condition?: string; inspection_result?: string; disposition?: string }) => request('/returns', { method: 'POST', body: JSON.stringify(data) }),
}
