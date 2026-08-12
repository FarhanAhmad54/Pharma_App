const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1'
let token = localStorage.getItem('pharma_access_token') ?? ''

export type User = { id: string; email: string; full_name: string; role: string; active: boolean; created_at: string }
export type Product = { id: string; sku: string; brand_name: string; generic_name: string; strength?: string | null; dosage_form: string; route?: string | null; category?: string | null; manufacturer?: string | null; unit: string; packaging?: string | null; selling_price: number; cost_price: number; reorder_threshold: number; active: boolean; created_at: string }
export type Batch = { id: string; batch_number: string; product_id: string; manufacturing_date: string; expiry_date: string; quantity_produced: number; quantity_available: number; quantity_reserved: number; quantity_sold: number; quantity_rejected: number; qc_status: string; status: string; warehouse_id?: string | null }
export type Sale = { id: string; order_number: string; customer_id: string; status: string; currency: string; total_amount: number; created_at: string }
export type Warehouse = { id: string; code: string; name: string; location?: string | null; active: boolean }
export type InventoryRow = { product_id: string; warehouse_id: string; net_quantity: string }
export type ProductCreate = { sku: string; brand_name: string; generic_name: string; strength?: string; dosage_form: string; route?: string; category?: string; manufacturer?: string; unit?: string; packaging?: string; selling_price: number; cost_price: number; reorder_threshold: number }
export type ProductionCreate = { order_number: string; product_id: string; planned_quantity: number; warehouse_id?: string; notes?: string }
export type QCRequest = { reference_number: string; test_date: string; result: 'PASSED' | 'FAILED'; notes?: string }

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
  products: (search = '') => request<Product[]>(`/products?limit=200${search ? `&search=${encodeURIComponent(search)}` : ''}`),
  createProduct: (data: ProductCreate) => request<Product>('/products', { method: 'POST', body: JSON.stringify(data) }),
  batches: () => request<Batch[]>('/batches'),
  releaseBatch: (id: string) => request<Batch>(`/batches/${id}/release`, { method: 'POST' }),
  recordQC: (id: string, data: QCRequest) => request<Batch>(`/batches/${id}/qc`, { method: 'POST', body: JSON.stringify(data) }),
  warehouses: () => request<Warehouse[]>('/warehouses'),
  sales: () => request<Sale[]>('/sales'),
  inventory: () => request<InventoryRow[]>('/reports/inventory'),
  createProduction: (data: ProductionCreate) => request('/production-orders', { method: 'POST', body: JSON.stringify(data) }),
}
