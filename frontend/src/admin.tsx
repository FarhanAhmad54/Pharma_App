import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { Plus, RefreshCw, ShieldCheck, Users, X } from 'lucide-react'
import { api, type Product, type User, type Warehouse } from './lib/api'

export function AdminWorkspace({ warehouses, products, notice }: { warehouses: Warehouse[]; products: Product[]; notice: (message: string) => void }) {
  const [users, setUsers] = useState<User[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [loading, setLoading] = useState(false)

  async function refresh() {
    setLoading(true)
    try { setUsers(await api.users()) } catch (error) { notice(error instanceof Error ? error.message : 'Unable to load users') } finally { setLoading(false) }
  }
  useEffect(() => { void refresh() }, [])

  return <>
    <div className="module-actions">
      <button className="primary-btn" onClick={() => setShowCreate(true)}><Plus size={15} /> NEW USER</button>
      <button className="secondary-btn" onClick={() => void refresh()}><RefreshCw size={15} /> {loading ? 'LOADING…' : 'REFRESH'}</button>
    </div>
    <div className="module-kpis">
      <MiniStat icon={<Users size={18} />} label="USERS" value={String(users.length)} />
      <MiniStat icon={<ShieldCheck size={18} />} label="ACTIVE" value={String(users.filter(u => u.active).length)} />
      <MiniStat icon={<ShieldCheck size={18} />} label="ROLE MODEL" value="10" />
      <MiniStat icon={<ShieldCheck size={18} />} label="RLS" value="ACTIVE" />
    </div>
    <div className="admin-grid">
      <section className="panel"><PanelTitle title="USER DIRECTORY" subtitle="Accounts and roles from the FastAPI authorization layer." /><div className="table-wrap"><table><thead><tr><th>NAME</th><th>EMAIL</th><th>ROLE</th><th>STATUS</th></tr></thead><tbody>{users.length ? users.map(user => <tr key={user.id}><td>{user.full_name}</td><td className="mono">{user.email}</td><td><span className="status-pill neutral">{user.role}</span></td><td><span className={`status-pill ${user.active ? 'success' : 'neutral'}`}>{user.active ? 'ACTIVE' : 'INACTIVE'}</span></td></tr>) : <tr><td colSpan={4} className="empty-state">No user records returned. Sign in as an administrator to manage accounts.</td></tr>}</tbody></table></div></section>
      <section className="panel"><PanelTitle title="FACILITIES & CATALOG" subtitle="Connected master data available to the signed-in administrator." /><div className="admin-row"><div><strong>WAREHOUSES</strong><span>{warehouses.length} configured facilities</span></div><span className="status-pill success">READY</span></div><div className="admin-row"><div><strong>PRODUCT CATALOG</strong><span>{products.length} product records</span></div><span className="status-pill success">READY</span></div><div className="role-list">{['SUPER_ADMIN','ADMIN','PRODUCTION_MANAGER','QUALITY_MANAGER','INVENTORY_MANAGER','WAREHOUSE_MANAGER','SALES_MANAGER','ACCOUNTANT','AUDITOR','VIEWER'].map(role => <div className="role-chip" key={role}><ShieldCheck size={14} />{role}</div>)}</div></section>
    </div>
    {showCreate && <UserModal onClose={() => setShowCreate(false)} onDone={async message => { setShowCreate(false); notice(message); await refresh() }} />}
  </>
}

function UserModal({ onClose, onDone }: { onClose: () => void; onDone: (message: string) => Promise<void> }) {
  const [form, setForm] = useState({ email: '', full_name: '', password: '', role: 'VIEWER' })
  const submit = async (event: FormEvent) => { event.preventDefault(); try { await api.register(form); await onDone('User created successfully.') } catch (error) { await onDone(error instanceof Error ? error.message : 'User creation failed') } }
  return <div className="modal-backdrop"><div className="modal"><div className="modal-head"><div><span>PHARMACORE CONTROL</span><h2>NEW USER</h2></div><button className="icon-btn" onClick={onClose}><X size={18} /></button></div><form className="form-grid" onSubmit={submit}><Field label="FULL NAME"><input required value={form.full_name} onChange={e => setForm({ ...form, full_name: e.target.value })} /></Field><Field label="EMAIL"><input type="email" required value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} /></Field><Field label="PASSWORD"><input type="password" minLength={12} required value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} /></Field><Field label="ROLE"><select value={form.role} onChange={e => setForm({ ...form, role: e.target.value })}>{['SUPER_ADMIN','ADMIN','PRODUCTION_MANAGER','QUALITY_MANAGER','INVENTORY_MANAGER','WAREHOUSE_MANAGER','SALES_MANAGER','ACCOUNTANT','AUDITOR','VIEWER'].map(role => <option key={role} value={role}>{role}</option>)}</select></Field><div className="modal-actions"><button type="button" className="secondary-btn" onClick={onClose}>CANCEL</button><button className="primary-btn">CREATE USER</button></div></form></div></div>
}
function MiniStat({ icon, label, value }: { icon: ReactNode; label: string; value: string }) { return <div className="mini-stat"><span className="mini-icon">{icon}</span><div><span>{label}</span><strong>{value}</strong></div></div> }
function PanelTitle({ title, subtitle }: { title: string; subtitle: string }) { return <div className="module-panel-title"><div><h2>{title}</h2><p>{subtitle}</p></div></div> }
function Field({ label, children }: { label: string; children: ReactNode }) { return <label className="field"><span>{label}</span>{children}</label> }
