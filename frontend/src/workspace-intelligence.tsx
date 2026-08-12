import { Activity, ArrowUpRight, CheckCircle2, CircleAlert, Clock3, Layers3, ShieldCheck, Sparkles, Wifi } from 'lucide-react'

const context: Record<string, { eyebrow: string; purpose: string; next: string; icon: typeof Activity }> = {
  Operations: { eyebrow: 'CONTROL ROOM', purpose: 'Monitor production, inventory and batch readiness across the selected facility.', next: 'Review the next production or transfer action.', icon: Activity },
  Quality: { eyebrow: 'QUALITY GATE', purpose: 'Control QC exceptions and determine which batches are eligible for release.', next: 'Resolve the oldest pending or failed QC item.', icon: ShieldCheck },
  Commercial: { eyebrow: 'ORDER DESK', purpose: 'Move customer demand from order creation through allocation and fulfillment.', next: 'Check unfulfilled orders before opening new demand.', icon: Layers3 },
  Analytics: { eyebrow: 'DECISION SUPPORT', purpose: 'Interpret live operational signals instead of isolated dashboard numbers.', next: 'Investigate the largest deviation from target.', icon: Sparkles },
  Admin: { eyebrow: 'PLATFORM CONTROL', purpose: 'Review facilities, access roles and operational governance.', next: 'Verify role access before changing platform state.', icon: ShieldCheck },
}

export function WorkspaceIntelligence({ module, pendingCount, facility }: { module: string; pendingCount: number; facility?: string }) {
  const item = context[module] ?? context.Operations
  const Icon = item.icon
  return (
    <section className="workspace-intelligence" aria-label="Workspace context">
      <div className="intel-main">
        <div className="intel-icon"><Icon size={18} /></div>
        <div>
          <div className="intel-eyebrow">{item.eyebrow}<span className="intel-divider" />{facility ? `FACILITY ${facility}` : 'ALL FACILITIES'}</div>
          <div className="intel-purpose">{item.purpose}</div>
        </div>
      </div>
      <div className="intel-items">
        <div className="intel-item"><Wifi size={14} /><span>LIVE SYNC</span><strong>CONNECTED</strong></div>
        <div className="intel-item"><CircleAlert size={14} /><span>ATTENTION</span><strong className={pendingCount > 0 ? 'intel-warn' : 'intel-ok'}>{pendingCount > 0 ? `${pendingCount} ITEMS` : 'CLEAR'}</strong></div>
        <div className="intel-item"><Clock3 size={14} /><span>NEXT ACTION</span><strong>{item.next}</strong></div>
        <button className="intel-action" aria-label="Open workspace guidance"><ArrowUpRight size={15} /></button>
      </div>
    </section>
  )
}

export function WorkflowStrip({ steps, current }: { steps: string[]; current: number }) {
  return <div className="workflow-strip" aria-label="Workflow progress">
    {steps.map((step, index) => {
      const state = index < current ? 'done' : index === current ? 'current' : 'upcoming'
      return <div className={`workflow-step ${state}`} key={step}>
        <span className="workflow-dot">{state === 'done' ? <CheckCircle2 size={13} /> : index + 1}</span>
        <span>{step}</span>
      </div>
    })}
  </div>
}
