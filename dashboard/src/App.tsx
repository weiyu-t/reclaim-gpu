import { useEffect, useRef, useState } from 'react'
import Markdown from 'react-markdown'
import { NodeDecisions, GPUCards } from './Investigations'
import { TrialPlanner } from './TrialPlanner'
import {
  ArrowDownRight, ArrowRight, ArrowUpRight, Check, CheckCheck, ChevronDown,
  ChevronLeft, ChevronRight, CircleHelp, Clock3, Cpu, Database, Download,
  FileCheck2, FlaskConical, Gauge, LayoutDashboard, Layers3, LoaderCircle,
  Network, Search, ShieldCheck, SlidersHorizontal, Sparkles, Target, X, ClipboardList,
} from 'lucide-react'

type Range = { low: number; point: number; high: number }
type Action = {
  id: string; title: string; short_title: string; tag: string; owner: string
  description: string; detector_id: string; evidence_strength: string; risk_level: string
  formula: string; savings_basis: string; downside: string; pilot: string; rollback: string
  job_count: number; observed_gpu_hours: number; eligible_gpu_hours: number
  recovery: Range; value: Range; share_of_sample: number; weighted_util_pct: number
  finding_count: number; finding_ids: string[]; completed_jobs: number; cancelled_jobs: number
}
type Job = {
  id: string; state: string; gpus: number; gpu_hours: number; usd: number
  avg_util: number; peak_util: number; wall_hours: number; eligible_gpu_hours: number
  finding_ids: string[]
}
type Overview = {
  window: { start: string; end: string }
  sample: { jobs: number; nodes: number; researchers: number; gpu_hours: number }
  price: { usd_per_gpu_hour: number; version: string }
  spend_usd: number; target: { percent: number; gpu_hours: number; value_usd: number }
  recovery: Range & { value: Range; share_percent: number; target_coverage_percent: number; target_gap_usd: number }
  spend: { state: string; label: string; gpu_hours: number; usd: number; share: number; jobs: number }[]
  weekly: { week: string; gpu_hours: number; completed: number; cancelled: number; other: number }[]
  actions: Action[]
  accounting: { naive_finding_hours: number; unique_flagged_hours: number; overlap_removed_jobs: number
    excluded_ambiguous_jobs: number; synthetic_findings: number; findings: number }
  caveat: string
  default_risk: Scenario
}
type Evidence = {
  action: Action; jobs: { total: number; offset: number; limit: number; rows: Job[] }
  findings: any[]; method: Record<string, string>
}
type Brief = {
  mode: string; text: string; note: string; model: string | null; cached: boolean; elapsed_seconds: number
  tool_trace: { tool: string; arguments: any; elapsed_ms: number; status: string }[]
  usage: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number } | null
}
type Scenario = {
  capacity_value_usd: number; recovered_gpu_hours: number; downside_usd: number
  net_capacity_value_usd: number; gross_bill_reduction_usd: number; net_bill_value_usd: number; engineer_hours: number
  rerun_gpu_hours: number; affected_jobs_equivalent: number; break_even_false_positive: number; caveat: string
}
type Tab = 'overview' | 'plan' | 'risk' | 'evidence' | 'nodes' | 'cards' | 'method' | 'planner'
const whole = (n: number) => new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(n)
const usd = (n: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n)
const compact = (n: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 }).format(n)
const pct = (n: number) => n.toFixed(1) + '%'
const colors: Record<string, string> = { COMPLETED: '#456b5a', CANCELLED: '#bfcba6', TIMEOUT: '#d99b60', FAILED: '#b7634e', NODE_FAIL: '#8c91aa' }

async function get<T>(url: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch('/api/reclaim' + url, { signal })
  if (!res.ok) throw new Error('The data service could not complete this request (' + res.status + ').')
  return res.json()
}

function App() {
  const [tab, setTab] = useState<Tab>('overview')
  const [price, setPrice] = useState(2.5)
  const [data, setData] = useState<Overview | null>(null)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const [selected, setSelected] = useState<string | null>(null)
  const [agent, setAgent] = useState(false)
  useEffect(() => {
    const controller = new AbortController()
    get<Overview>('/overview?price=' + price, controller.signal).then(d => { setData(d); setError('') })
      .catch(e => { if (e.name !== 'AbortError') setError(e.message) })
    return () => controller.abort()
  }, [price, revision])
  useEffect(() => { get<{ configured: boolean }>('/agent/status').then(s => setAgent(s.configured)).catch(() => {}) }, [revision, selected])
  const nav = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'plan', label: 'Proposed trials', icon: Layers3 },
    { id: 'planner', label: 'Trial planner', icon: ClipboardList },
    { id: 'risk', label: 'Downside costs', icon: SlidersHorizontal },
    { id: 'nodes', label: 'Machine review', icon: ShieldCheck },
    { id: 'cards', label: 'GPU usage', icon: Cpu },
    { id: 'evidence', label: 'Evidence', icon: Network },
  ] as const
  function navigate(next: Tab) { setTab(next); window.scrollTo({ top: 0, behavior: 'smooth' }) }
  return <div className="app-shell">
    <aside className="sidebar">
      <button className="wordmark" onClick={() => navigate('overview')} aria-label="Reclaim overview">
        <span className="logo"><ArrowUpRight size={24} strokeWidth={2.5} /></span>reclaim<span className="logo-dot">.</span>
      </button>
      <div className="workspace-label">DECISION WORKSPACE</div>
      <nav aria-label="Main navigation">
        {nav.map(n => <button key={n.id} aria-label={n.label} aria-current={tab === n.id ? 'page' : undefined} title={n.label} className={'nav-item ' + (tab === n.id ? 'active' : '')} onClick={() => navigate(n.id)}>
          <n.icon size={18} /><span>{n.label}</span>{n.id === 'plan' && <span className="nav-count">2</span>}
        </button>)}
      </nav>
      <div className="sidebar-spacer" />
      <div className="source-card"><div className="source-icon"><Database size={17} /></div>
        <strong>MIT SuperCloud</strong><span>TX-GAIA workload sample</span>
        <div className="source-status"><i />Real telemetry</div>
        <div className="source-details"><span>{data ? whole(data.sample.jobs) : '—'} jobs</span><span>{data?.sample.nodes || '—'} nodes</span></div>
      </div>
      <button className={'nav-item method-link ' + (tab === 'method' ? 'active' : '')} onClick={() => navigate('method')}><CircleHelp size={18} />Method & assumptions</button>
      <div className="sidebar-footer"><span className="avatar">R</span><div><strong>Reclaim workspace</strong><span>MantisGrid · Track 2</span></div></div>
    </aside>
    <div className="main-shell">
      <header className="topbar">
        <div className="breadcrumb"><span>Workspace</span><ChevronRight size={14} /><strong>{tab === 'method' ? 'Method & assumptions' : nav.find(n => n.id === tab)?.label}</strong></div>
        <div className="topbar-actions">
          <label className="price-select"><span>GPU-hour</span><select aria-label="Price per GPU-hour" value={price} onChange={e => setPrice(+e.target.value)}>
            {[1, 1.5, 2.5, 3.5, 5].map(p => <option key={p} value={p}>{'$' + p.toFixed(2)}</option>)}
          </select><ChevronDown size={13} /></label>
          <a className="button secondary export" href={'/api/reclaim/claims?price=' + price} download="claims.json"><Download size={15} />Export claims</a>
        </div>
      </header>
      <main>
        {!data ? <div className="loading-state"><span className="logo"><ArrowUpRight /></span><h1>{error ? 'The data service is unavailable.' : 'Loading the budget review…'}</h1>
          <p>{error || 'Loading the local workload sample and checking the accounting.'}</p>
          {error ? <button className="button primary" onClick={() => setRevision(r => r + 1)}>Try again</button> : <LoaderCircle className="spin" />}
        </div> : <>
          {error && <div className="inline-error">{error} <button onClick={() => setRevision(r => r + 1)}>Retry</button></div>}
          <div className="page-heading">
            <div><div className="eyebrow">GPU BUDGET INTELLIGENCE</div>
              <h1>{tab === 'overview' ? 'GPU budget decision' : tab === 'plan' ? 'Proposed trials' : tab === 'planner' ? 'Plan a focused trial' : tab === 'risk' ? 'Cost of an incorrect recommendation' : tab === 'nodes' ? 'Which machines need inspection?' : tab === 'cards' ? 'Where fewer GPUs may be enough' : tab === 'evidence' ? 'Evidence behind the recommendations' : 'Sources and assumptions'}</h1>
              <p>{tab === 'overview' ? 'Potential benefit, downside, and spending impact.' : tab === 'plan' ? 'Two changes to test with workload owners before a wider rollout.' : tab === 'planner' ? 'Choose owners, check the path to cash, and prepare a bounded proposal.' : tab === 'risk' ? 'Estimate the cost of interrupted work before approving a change.' : tab === 'nodes' ? 'Compare machine faults with problems in the work running on them.' : tab === 'cards' ? 'Check each GPU before reducing the number assigned to a job.' : tab === 'evidence' ? 'Review the source records and the reasons for each proposed action.' : 'How the estimates are calculated and what still needs testing.'}</p>
            </div>
            <div className="date-chip"><Clock3 size={14} /><span>{data.window.start} — {data.window.end}<small>Historical sample</small></span></div>
          </div>
          {tab === 'overview' && <>
            <section className="executive-brief" aria-label="Budget decision brief">
              <div className="executive-recommendation"><div><span className="eyebrow">RECOMMENDATION</span><h2>Approve two limited trials.</h2><p>Test CPU placement and warnings for low-activity GPU sessions. Defer a broad capacity cut.</p></div><span className="executive-status">Proposed · not yet tested</span></div>
              <div className="executive-metrics">
                <div><span>Potential value of GPU time freed</span><strong>{compact(data.recovery.value.point)}</strong><small>{compact(data.recovery.value.low)}–{compact(data.recovery.value.high)} scenario range for eligible jobs</small></div>
                <div><span>Cost if 2% of selected jobs are disrupted</span><strong>{compact(data.default_risk.downside_usd)}</strong><small>Repeated GPU work + staff time</small></div>
                <div><span>Net value after that rework</span><strong>{compact(data.default_risk.net_capacity_value_usd)}</strong><small>GPU time value less estimated rework</small></div>
              </div>
              <div className="executive-cash"><strong>{usd(data.default_risk.gross_bill_reduction_usd)}</strong><div><b>Bill reduction assumed</b><p>Freed GPU time reduces spending only if billing or purchasing changes.</p></div></div>
              <div className="executive-footer"><p>Historical sample at ${data.price.usd_per_gpu_hour.toFixed(2)}/GPU-hour. Trial results are unproven; actual recovery could be zero.</p><button className="button mint" onClick={() => navigate('planner')}>Plan a trial<ArrowUpRight size={16} /></button></div>
            </section>
            <div className="section-heading"><div><span className="eyebrow">PROPOSED ACTIONS</span><h2>What to test first</h2></div><button className="text-button" onClick={() => navigate('plan')}>Trial details<ArrowRight size={15} /></button></div>
            <div className="actions-grid">{data.actions.map((a, i) => <ActionCard key={a.id} action={a} index={i} onOpen={() => setSelected(a.id)} />)}</div>
            <section className="card target-review"><div className="section-top"><div><span className="eyebrow">PROGRESS TOWARD A 20% REDUCTION</span><h2>The current plan could cover {pct(data.recovery.target_coverage_percent)} of the target.</h2></div><Target size={20} /></div><p>The target equals {compact(data.target.value_usd)} of GPU time in this sample. Applied to eligible jobs, the proposed changes could free {whole(data.recovery.point)} GPU-hours ({pct(data.recovery.share_percent)} of recorded allocation), leaving {compact(data.recovery.target_gap_usd)} without an identified recovery plan.</p><div className="target-progress"><span style={{ width: Math.min(data.recovery.target_coverage_percent, 100) + '%' }} /></div><p className="small-muted">Rework estimate: 2% of selected jobs repeat their full GPU duration and need 0.5 staff hours each at $95/hour. Trial results must replace these assumptions before rollout.</p></section>
            <Spend data={data} />
          </>}
          {tab === 'plan' && <>
            <div className="plan-summary"><ShieldCheck size={23} /><div><strong>Approve a small trial with each workload owner.</strong><p>The starting estimate is {whole(data.recovery.point)} GPU-hours freed. Confirm the results and runtime before changing normal operations.</p></div><span className="pill green">{pct(data.recovery.share_percent)} of sample</span></div>
            <div className="actions-grid">{data.actions.map((a, i) => <ActionCard key={a.id} action={a} index={i} onOpen={() => setSelected(a.id)} expanded />)}</div>
            <button className="risk-banner" onClick={() => navigate('planner')}><ClipboardList size={26} /><div><strong>Choose owners and prepare a trial brief.</strong><span>Set a scope, spending cap, review date and stop conditions.</span></div><ArrowUpRight size={22} /></button>
            <section className="card dedup-note"><CheckCheck size={23} /><div><h3>Overlapping jobs are counted once.</h3><p>{data.accounting.overlap_removed_jobs} jobs qualify for both trials and are counted under CPU placement only. {data.accounting.excluded_ambiguous_jobs} jobs with unclear duration or retry history are excluded.</p></div><button className="text-button" onClick={() => navigate('method')}>Calculation method<ArrowRight size={15} /></button></section>
            <button className="risk-banner" onClick={() => navigate('risk')}><FlaskConical size={26} /><div><strong>Review the cost of interrupted work.</strong><span>See when rework costs exceed the benefit.</span></div><ArrowUpRight size={22} /></button>
          </>}
          {tab === 'risk' && <RiskLab data={data} price={price} />}
          {tab === 'planner' && <TrialPlanner price={price} />}
          {tab === 'nodes' && <NodeDecisions price={price} briefing={<NodeBriefing key={price} price={price} />} />}
          {tab === 'cards' && <GPUCards price={price} />}
          {tab === 'evidence' && <EvidencePage data={data} price={price} onOpen={setSelected} />}
          {tab === 'method' && <Method data={data} />}
          <footer className="main-footer"><span><Database size={13} />MIT SuperCloud TX-GAIA · observed workload sample</span><button onClick={() => navigate('method')}>Capacity value ≠ cash savings <ArrowUpRight size={13} /></button></footer>
        </>}
      </main>
    </div>
    {selected && <EvidenceDrawer actionId={selected} price={price} agent={agent} onClose={() => setSelected(null)} />}
  </div>
}

function Spend({ data }: { data: Overview }) {
  const max = Math.max(...data.weekly.map(w => w.gpu_hours))
  return <section className="card spend-card">
    <div className="section-top"><div><span className="eyebrow">RECORDED GPU USE</span><h2>GPU time by job outcome</h2></div><span className="pill neutral">Measured · {whole(data.sample.gpu_hours)} GPU-h</span></div>
    <div className="spend-layout">
      <div className="spend-total"><span>Value of allocated GPU time</span><strong>{compact(data.spend_usd)}</strong><p>At {'$' + data.price.usd_per_gpu_hour.toFixed(2)} per GPU-hour.<br />Reference value for this sample.</p></div>
      <div className="spend-chart"><div className="stacked-bar" role="img" aria-label="GPU allocation by job outcome">
        {data.spend.map(s => <div key={s.state} style={{ width: (s.share * 100) + '%', background: colors[s.state] || '#babbb5' }} title={s.label + ': ' + usd(s.usd) + ', ' + whole(s.gpu_hours) + ' GPU-h'} />)}
      </div><div className="spend-legend">{data.spend.filter(s => s.share > .005).map(s => <div key={s.state}><span><i style={{ background: colors[s.state] || '#babbb5' }} />{s.label}</span><strong>{compact(s.usd)}</strong><small>{pct(s.share * 100)}</small></div>)}</div></div>
      <div className="weekly-chart"><span>Weekly allocation <small>GPU-h</small></span><svg viewBox="0 0 240 70" role="img" aria-label="Weekly allocated GPU-hours by outcome">{data.weekly.map((w, i) => {
        const x = i * 240 / data.weekly.length
        const width = 240 / data.weekly.length - 3
        return <g key={w.week}><title>{w.week + ': ' + whole(w.gpu_hours) + ' GPU-h'}</title>
          <rect x={x} y={70 - w.gpu_hours / max * 66} width={width} height={w.other / max * 66} rx="1" fill="#d99b60" />
          <rect x={x} y={70 - (w.completed + w.cancelled) / max * 66} width={width} height={w.cancelled / max * 66} fill="#bfcba6" />
          <rect x={x} y={70 - w.completed / max * 66} width={width} height={w.completed / max * 66} fill="#456b5a" />
        </g>
      })}</svg><div><span>Feb</span><span>Jun</span></div></div>
    </div>
    <div className="subtle-note"><CircleHelp size={14} /><span>Cancelled work may still be useful. These totals alone do not identify savings.</span></div>
  </section>
}

function ActionCard({ action: a, index, onOpen, expanded = false }: { action: Action; index: number; onOpen: () => void; expanded?: boolean }) {
  return <section className="card action-card">
    <div className="action-top"><span className="action-icon">{index === 0 ? <Cpu size={21} /> : <Clock3 size={21} />}</span><span className="action-category">0{index + 1} / {a.tag}</span><span className={'pill ' + (index === 0 ? 'green' : 'amber')}>{index === 0 ? 'CPU trial' : 'Warnings only first'}</span></div>
    <h3>{a.title}</h3><p className="action-description">{a.description}</p>
    <div className="action-estimate"><strong>{compact(a.value.point)}</strong><span>potential GPU time value<br /><b>{compact(a.value.low)}–{compact(a.value.high)} scenario range</b></span></div>
    <div className="action-facts"><span><Database size={13} />{whole(a.job_count)} jobs</span><span>{whole(a.recovery.point)} GPU-h · base</span></div>
    {expanded && <div className="action-expanded"><div><span>TRIAL</span><p>{a.pilot}</p></div><div><span>STOP IF</span><p>{a.rollback}</p></div><div><span>ASSUMPTION</span><p>{a.savings_basis}</p></div></div>}
    <div className="action-footer"><span><i />{a.owner}</span><button className="text-button" onClick={onOpen}>Inspect evidence<ArrowUpRight size={16} /></button></div>
  </section>
}

function Slider({ label, value, min = 0, max = 100, step = 1, onChange, display, help }: { label: string; value: number; min?: number; max?: number; step?: number; onChange: (v: number) => void; display: string; help: string }) {
  return <label className="slider-field"><span><strong>{label}</strong><b>{display}</b></span><input type="range" min={min} max={max} step={step} value={value} onChange={e => onChange(+e.target.value)} /><small>{help}</small></label>
}

function RiskLab({ data, price }: { data: Overview; price: number }) {
  const [recovery, setRecovery] = useState(100)
  const [falsePositive, setFalsePositive] = useState(2)
  const [cash, setCash] = useState(0)
  const [engineerTime, setEngineerTime] = useState(.5)
  const [scenario, setScenario] = useState<Scenario | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    const c = new AbortController()
    const t = setTimeout(() => get<Scenario>('/scenario?price=' + price + '&recovery=' + recovery / 100 + '&false_positive=' + falsePositive / 100 + '&cash_realization=' + cash / 100 + '&engineer_hours_per_job=' + engineerTime, c.signal)
      .then(s => { setScenario(s); setError('') }).catch(e => { if (e.name !== 'AbortError') setError(e.message) }), 150)
    return () => { clearTimeout(t); c.abort() }
  }, [price, recovery, falsePositive, cash, engineerTime])
  function reset() { setRecovery(100); setFalsePositive(2); setCash(0); setEngineerTime(.5) }
  return <div className="risk-grid">
    <section className="card controls-card"><div className="section-top"><div><span className="eyebrow">CHANGE THE ASSUMPTIONS</span><h2>Test the financial impact</h2></div><button className="text-button" onClick={reset}>Reset</button></div>
      <Slider label="Share of planned GPU time freed" value={recovery} max={150} onChange={setRecovery} display={recovery + '%'} help={'100% means ' + whole(data.recovery.point) + ' GPU-hours, our starting estimate. Lower this if fewer jobs can change.'} />
      <Slider label="Useful jobs disrupted" value={falsePositive} max={50} onChange={setFalsePositive} display={falsePositive + '%'} help="Share of selected jobs interrupted by the change. Each is assumed to repeat its full GPU run." />
      <Slider label="Share of freed time that lowers spending" value={cash} onChange={setCash} display={cash + '%'} help="Owned or committed capacity may free time without reducing spend. Default: no proven bill reduction." />
      <Slider label="Staff time per disrupted job" value={engineerTime} max={4} step={.25} onChange={setEngineerTime} display={engineerTime.toFixed(2) + ' h'} help="Estimated time to resolve each disruption, valued at $95 per staff hour." />
    </section>
    <div className="risk-results">{error && <p className="inline-error">{error}</p>}
      <section className={'risk-answer ' + ((scenario?.net_capacity_value_usd || 0) < 0 ? 'negative' : '')}>
        <div className="card-eyebrow"><FlaskConical size={17} />02 / COST OF BEING WRONG</div>
        <span>Value of freed GPU time, after rework</span><strong>{scenario ? usd(scenario.net_capacity_value_usd) : '…'}</strong>
        <p>{scenario && scenario.net_capacity_value_usd < 0 ? 'Rework costs exceed the value of freed GPU time. Reduce disruption before expanding the trial.' : 'The value of freed GPU time exceeds rework costs under these assumptions. Confirm both in a trial.'}</p>
        <div className="risk-equation"><div><small>GPU time value</small><b>{scenario ? compact(scenario.capacity_value_usd) : '—'}</b></div><span>−</span><div><small>Rework cost</small><b>{scenario ? compact(scenario.downside_usd) : '—'}</b></div><span>=</span><div><small>Net value</small><b>{scenario ? compact(scenario.net_capacity_value_usd) : '—'}</b></div></div>
      </section>
      <section className="card risk-details"><div className="section-top"><h3>Costs included in this estimate</h3><ShieldCheck size={19} /></div>
        <div><span>GPU work repeated</span><strong>{scenario ? whole(scenario.rerun_gpu_hours) : '—'} GPU-h</strong></div>
        <div><span>Staff time</span><strong>{scenario ? whole(scenario.engineer_hours) : '—'} hours</strong></div>
        <div><span>Disruption rate that erases the benefit</span><strong>{scenario ? pct(scenario.break_even_false_positive * 100) : '—'}</strong></div>
        <div className="cash-row"><span>Bill reduction before rework</span><strong>{scenario ? usd(scenario.gross_bill_reduction_usd) : '—'}</strong></div>
        <div><span>Bill reduction minus rework value</span><strong>{scenario ? usd(scenario.net_bill_value_usd) : '—'}</strong></div>
        <p>{cash === 0 ? 'No bill reduction is assumed. Freed GPU time can be reused for other work.' : 'Cash reduction requires a real billing or procurement change. This slider does not establish one.'}</p>
      </section>
    </div>
    <div className="risk-footnote"><CircleHelp size={16} /><p>{scenario?.caveat || 'This is a decision model, not a forecast.'} Pilot measurements should replace these inputs before rollout.</p></div>
  </div>
}

function EvidencePage({ data, price, onOpen }: { data: Overview; price: number; onOpen: (id: string) => void }) {
  const [caseData, setCaseData] = useState<any>(null)
  const [error, setError] = useState('')
  const [brief, setBrief] = useState<Brief | null>(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => { get('/causal-case').then(setCaseData).catch(e => setError(e.message)) }, [])
  async function explain() {
    setBusy(true); setError('')
    try {
      const r = await fetch('/api/reclaim/investigate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action_id: 'causal-case', price }) })
      if (!r.ok) throw new Error('The evidence briefing could not complete. Please retry.')
      setBrief(await r.json())
    } catch (e) { setError(String(e)) } finally { setBusy(false) }
  }
  return <>
    <div className="evidence-summary">{data.actions.map(a => <button className="card evidence-shortcut" key={a.id} onClick={() => onOpen(a.id)}><FileCheck2 size={24} /><div><strong>{a.short_title}</strong><span>{whole(a.finding_count)} linked findings · {whole(a.job_count)} jobs</span></div><ArrowUpRight size={19} /></button>)}</div>
    <section className="card causal-card"><div className="section-top"><div><span className="eyebrow">SHARED WORKLOAD INVESTIGATION</span><h2>Investigate the workload first</h2></div><span className="pill green">Real telemetry</span></div>
      <p className="section-description">Related tasks failed across several machines. Check what they share before removing machines from service.</p>
      {error && <p className="inline-error">{error}</p>}
      {!caseData ? <LoaderCircle className="spin" /> : <>
        <div className="causal-grid"><div className="causal-copy"><div className="causal-numbers"><div><strong>{whole(caseData.tasks)}</strong><span>failed tasks</span></div><div><strong>{caseData.nodes}</strong><span>machines involved</span></div><div><strong>1</strong><span>shared array</span></div></div>
          <h3>{caseData.decision}</h3><p>{caseData.causal?.message}</p><p className="small-muted">{caseData.limitation}</p>
          <button className="button primary" onClick={explain} disabled={busy}>{busy ? <LoaderCircle size={16} className="spin" /> : <Sparkles size={16} />}{busy ? 'Retrieving evidence…' : 'Explain the evidence'}</button></div>
          <div className="causal-graph"><div className="graph-root"><Layers3 size={24} /><span>Shared workload<strong>{caseData.root_name}</strong></span></div><div className="graph-stem" /><div className="graph-nodes">{caseData.node_counts.slice(0, 4).map((n: any) => <div key={n.node}><Cpu size={20} /><strong>{n.jobs} tasks</strong><span>{n.node}</span></div>)}</div><p>Failures spread across machines; check the common workload.</p></div>
        </div>
        <details className="json-details"><summary>Inspect official causal response and finding ID</summary><pre>{JSON.stringify({ finding_id: caseData.finding_id, response: caseData.causal }, null, 2)}</pre></details>
      </>}
      {brief && <Briefing brief={brief} />}
    </section>
    <section className="card quiet-card"><ShieldCheck size={28} /><div><h3>No evidence here for a PCIe upgrade</h3><p>The PCIe saturation rule is armed but never fires in this sample. It provides no support for a PCIe-capacity upgrade; it does not rule out every data-loading bottleneck.</p></div><span className="pill green">Rule: CLEAR</span></section>
  </>
}

function Briefing({ brief }: { brief: Brief }) {
  return <div className="briefing"><div className="section-top"><h3><Sparkles size={17} />Evidence briefing</h3><span className={'pill ' + (brief.mode === 'live' ? 'green' : 'neutral')}>{brief.mode === 'live' ? 'Featherless + MCP' : 'MCP evidence · no model'}</span></div>
    <div className="brief-text"><Markdown skipHtml components={{a: ({children}) => <span>{children}</span>, img: () => null}}>{brief.text}</Markdown></div><p className="small-muted">{brief.note}</p>
    <details><summary>{brief.tool_trace.length} MCP tool calls · {brief.elapsed_seconds}s{brief.cached ? ' · cached' : ''}{brief.usage?.total_tokens ? ' · ' + whole(brief.usage.total_tokens) + ' tokens' : ''}</summary>
      {brief.tool_trace.map((t, i) => <div className="tool-call" key={i}><Check size={14} /><code>{t.tool}</code><span>{t.elapsed_ms} ms</span></div>)}
      {brief.model && <p className="small-muted">Model: {brief.model}</p>}
    </details>
  </div>
}

function NodeBriefing({ price }: { price: number }) {
  const [brief, setBrief] = useState<Brief | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function explain() {
    setBusy(true); setError('')
    try {
      const r = await fetch('/api/reclaim/investigate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action_id: 'node-audit', price }) })
      if (!r.ok) throw new Error('The node briefing could not complete. Please retry.')
      setBrief(await r.json())
    } catch (e) { setError(String(e)) } finally { setBusy(false) }
  }
  return <div className="node-brief"><button className="button primary" onClick={explain} disabled={busy}>{busy ? <LoaderCircle className="spin" size={16} /> : <Sparkles size={16} />}{busy ? 'Retrieving evidence…' : 'Explain the machine recommendation'}</button><p className="small-muted research-note">This explanation uses the recorded failure episode and the starting cost assumptions. It does not update with the sliders above.</p>{error && <p className="inline-error">{error}</p>}{brief && <Briefing brief={brief} />}</div>
}

function EvidenceDrawer({ actionId, price, agent, onClose }: { actionId: string; price: number; agent: boolean; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [evidence, setEvidence] = useState<Evidence | null>(null)
  const [offset, setOffset] = useState(0)
  const [error, setError] = useState('')
  const [brief, setBrief] = useState<Brief | null>(null)
  const [busy, setBusy] = useState(false)
  const [raw, setRaw] = useState<any>(null)
  const [rawBusy, setRawBusy] = useState(false)
  const rawRecord = useRef<HTMLDivElement>(null)
  useEffect(() => { if (raw) rawRecord.current?.scrollIntoView({behavior: 'smooth', block: 'center'}) }, [raw])
  useEffect(() => { dialog.current?.showModal() }, [])
  useEffect(() => {
    const c = new AbortController()
    get<Evidence>('/actions/' + actionId + '?price=' + price + '&offset=' + offset, c.signal).then(setEvidence).catch(e => { if (e.name !== 'AbortError') setError(e.message) })
    return () => c.abort()
  }, [actionId, price, offset])
  async function inspect(id: string) {
    setRawBusy(true)
    try { setRaw(await get('/jobs/' + id)) } catch (e) { setError(String(e)) } finally { setRawBusy(false) }
  }
  async function explain() {
    setBusy(true); setError('')
    try {
      const r = await fetch('/api/reclaim/investigate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action_id: actionId, price }) })
      if (!r.ok) throw new Error('The briefing could not complete. Your evidence is still available.')
      setBrief(await r.json())
    } catch (e) { setError(String(e)) } finally { setBusy(false) }
  }
  return <dialog className="evidence-dialog" ref={dialog} onCancel={onClose} onClick={e => { if (e.target === e.currentTarget) onClose() }} aria-label="Recommendation evidence">
    <div className="drawer-inner"><div className="drawer-top"><span className="eyebrow"><FileCheck2 size={15} />SUPPORTING RECORDS</span><button className="icon-button" onClick={onClose} aria-label="Close evidence"><X size={20} /></button></div>
      {error && <p className="inline-error">{error}</p>}
      {!evidence ? <LoaderCircle className="spin" /> : <>
        <h2>{evidence.action.title}</h2><p className="section-description">{evidence.action.description}</p>
        <div className="drawer-metrics"><div><span>Potential GPU time value</span><strong>{usd(evidence.action.value.point)}</strong></div><div><span>GPU time potentially freed</span><strong>{whole(evidence.action.recovery.point)}<small> GPU-h</small></strong></div><div><span>Matching jobs</span><strong>{whole(evidence.action.job_count)}<small> jobs</small></strong></div></div>
        <div className="drawer-ai"><div><Sparkles size={18} /><span>{agent ? 'Explain the evidence with Featherless' : 'Review the evidence through MCP'}</span></div><button className="button primary" onClick={explain} disabled={busy}>{busy ? <LoaderCircle className="spin" size={15} /> : <ArrowUpRight size={15} />}{busy ? 'Investigating…' : 'Get briefing'}</button></div>
        {brief && <Briefing brief={brief} />}
        <section className="drawer-section"><h3>The calculation</h3><code className="filter-code">{evidence.action.formula}</code><p>{evidence.action.savings_basis}</p><div className="calc-line"><span>GPU time eligible for the trial</span><b>{whole(evidence.action.eligible_gpu_hours)} GPU-h</b></div><div className="calc-line"><span>Potential GPU time freed</span><b>{whole(evidence.action.recovery.low)}–{whole(evidence.action.recovery.high)} GPU-h</b></div></section>
        <section className="drawer-section"><div className="section-top"><h3>Jobs behind the number</h3><span className="small-muted">Largest allocation first</span></div><div className="table-scroll"><table><thead><tr><th>Job ID</th><th>Outcome</th><th>GPU-h</th><th>Avg / peak SM</th><th /></tr></thead><tbody>{evidence.jobs.rows.map(j => <tr key={j.id}><td><button className="job-link" onClick={() => inspect(j.id)}>{j.id}</button></td><td><span className={'state ' + j.state.toLowerCase()}>{j.state.replaceAll('_', ' ')}</span></td><td>{whole(j.gpu_hours)}</td><td>{j.avg_util}% / {j.peak_util}%</td><td><button className="icon-button" onClick={() => inspect(j.id)} aria-label={'Inspect job ' + j.id}><ArrowUpRight size={14} /></button></td></tr>)}</tbody></table></div>
          <div className="pagination"><span>{offset + 1}–{Math.min(offset + evidence.jobs.limit, evidence.jobs.total)} of {whole(evidence.jobs.total)} jobs</span><div><button className="icon-button" aria-label="Previous jobs" disabled={offset === 0} onClick={() => setOffset(o => Math.max(0, o - 25))}><ChevronLeft size={17} /></button><button className="icon-button" aria-label="Next jobs" disabled={offset + evidence.jobs.limit >= evidence.jobs.total} onClick={() => setOffset(o => o + 25)}><ChevronRight size={17} /></button></div></div>
          {rawBusy && <LoaderCircle className="spin" size={18} />}
          {raw && <div className="raw-record" ref={rawRecord}><div className="section-top"><h4>Raw job {raw.job.id_job}</h4><button className="icon-button" aria-label="Close raw record" onClick={() => setRaw(null)}><X size={16} /></button></div><p className="small-muted">{raw.source}</p><pre>{JSON.stringify(raw, null, 2)}</pre></div>}
        </section>
        <section className="drawer-section"><h3>What could go wrong</h3><p>{evidence.action.downside}</p><div className="pilot-box"><strong>Trial</strong><p>{evidence.action.pilot}</p><strong>When to reverse the change</strong><p>{evidence.action.rollback}</p></div></section>
        <details className="json-details"><summary>Source, grain, and deduplication method</summary>{Object.entries(evidence.method).map(([k, v]) => <p key={k}><strong>{k.replaceAll('_', ' ')}:</strong> {v}</p>)}</details>
        <details className="json-details"><summary>Inspect {evidence.findings.length} representative MantisGrid findings</summary><pre>{JSON.stringify(evidence.findings, null, 2)}</pre></details>
      </>}
    </div>
  </dialog>
}

function Method({ data }: { data: Overview }) {
  return <div className="method-grid">
    <section className="card"><span className="eyebrow">01 / ACCOUNTING</span><h2>How double counting is prevented</h2><p>Findings overlap and mix impact types. Summing their impact yields {whole(data.accounting.naive_finding_hours)} GPU-hours, exceeding the sample’s {whole(data.sample.gpu_hours)} hours.</p><p>We recompute candidate cohorts from job records, cap duration against allocation, exclude retries, and give CPU placement precedence. {data.accounting.overlap_removed_jobs} jobs are counted only once.</p><div className="method-stat"><span>Overlap removed</span><strong>{data.accounting.overlap_removed_jobs} jobs</strong></div></section>
    <section className="card"><span className="eyebrow">02 / WHAT WE KNOW</span><h2>Measured data and assumptions</h2><p>Job outcomes, allocated time, and GPU utilization are observed. Recovery rates, disruption rates, and bill reduction are assumptions that need a pilot.</p><p>The recovery interval varies adoption and feasibility assumptions. It is not a statistical confidence interval. Actual recovery could be zero.</p><div className="method-stat"><span>Unmeasured intervention effects</span><strong>Explicit scenarios</strong></div></section>
    <section className="card"><span className="eyebrow">03 / SCOPE</span><h2>What this sample covers</h2><p>{whole(data.sample.jobs)} jobs from {data.sample.researchers} researchers ran on {data.sample.nodes} machines in this observed window. Job telemetry cannot establish total unallocated fleet idle time.</p><p>The {data.accounting.synthetic_findings} synthetic shared-storage findings are excluded from savings. The array investigation uses real telemetry.</p><div className="method-stat"><span>Price book</span><strong>{data.price.version}</strong></div></section>
    <section className="card"><span className="eyebrow">04 / DECISION QUALITY</span><h2>What the trials must confirm</h2><p>Low utilization is a symptom. Cancellation may preserve research resources. A node hosting failed tasks may be healthy. Findings start investigations; they do not authorize changes.</p><p>The MCP workflow retrieves rules and evidence. Deterministic code computes every dashboard number. Model explanations are labeled separately and include their tool trace.</p><div className="method-stat"><span>Action policy</span><strong>Pilot → measure → decide</strong></div></section>
      <section className="card method-wide"><div className="section-top"><h3>Reproduce this analysis</h3><FileCheck2 size={20} /></div><p>Run the official preparation, generator, and checksum commands, then start the dashboard with Docker Compose. Claims are generated from the same accounting functions as the interface.</p><pre>make prep{'\n'}make generate{'\n'}make check-data{'\n'}docker compose up{'\n'}make validate CLAIMS=claims.json URL=http://localhost:3000</pre><p className="small-muted">Data: MIT SuperCloud TX-GAIA, HPCA ’22 · CC BY-NC-ND 4.0. Telemetry is excluded from the submission. Live briefings send small evidence excerpts to the configured Featherless service. Dollar amounts use a reference price, not an invoice.</p></section>
  </div>
}

export default App
