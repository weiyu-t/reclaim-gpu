import { useEffect, useState } from 'react'
import { ArrowDown, ArrowUpRight, Check, CircleHelp, ClipboardList, Download, LoaderCircle, Users } from 'lucide-react'
import { RawJob } from './Investigations'
import './planning.css'

type Draft = {
  action_id: 'cpu-placement' | 'idle-sessions'; owners: 1 | 3 | 5
  billing_model: 'owned' | 'committed' | 'usage'; confirmations: string[]; contract_date: string
  responsible_person: string; review_date: string; max_jobs: number; duration_days: number
  spend_cap_usd: number; max_slowdown_percent: number
}
type Owner = { id: string; label: string; jobs: number; eligible_gpu_hours: number; share_percent: number; example_jobs: { id: string; eligible_gpu_hours: number }[] }
type Path = { label: string; outcome: string; explanation: string; checks: { id: string; label: string; confirmed?: boolean }[]; next_step: string }
type Shortlist = {
  title: string; total_owners: number; total_jobs: number; total_eligible_gpu_hours: number
  selected_owners: number; selected_jobs: number; selected_gpu_hours: number; selected_share_percent: number
  reference_value_usd: number; owners_for_80_percent: number; owners: Owner[]; basis: string; limitation: string
  billing_paths: Record<Draft['billing_model'], Path>
}
type Plan = { eligible: boolean; status: string; success: string; stop: string; scope_note: string; missing: string[]
  cash: Path & { status: string; conditions_confirmed: boolean; missing: string[]; evidence_status: string } }
const storageKey = 'reclaim-trial-draft-v1'
const defaults: Draft = { action_id: 'cpu-placement', owners: 3, billing_model: 'owned', confirmations: [], contract_date: '', responsible_person: '', review_date: '', max_jobs: 5, duration_days: 7, spend_cap_usd: 500, max_slowdown_percent: 10 }
const whole = (n: number) => n.toLocaleString('en-US', { maximumFractionDigits: 0 })
const usd = (n: number) => n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })

function loadDraft(key: string): Draft {
  try {
    const saved = JSON.parse(localStorage.getItem(key) || 'null')
    if (!saved || typeof saved !== 'object') return { ...defaults }
    const d = { ...defaults }
    if (['cpu-placement', 'idle-sessions'].includes(saved.action_id)) d.action_id = saved.action_id
    if ([1, 3, 5].includes(saved.owners)) d.owners = saved.owners
    if (['owned', 'committed', 'usage'].includes(saved.billing_model)) d.billing_model = saved.billing_model
    d.confirmations = Array.isArray(saved.confirmations) ? saved.confirmations.filter((x: unknown) => typeof x === 'string' && ['reuse', 'purchase', 'terms', 'release', 'meter'].includes(x)).slice(0, 4) : []
    for (const key of ['contract_date', 'review_date'] as const) if (typeof saved[key] === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(saved[key])) d[key] = saved[key]
    if (typeof saved.responsible_person === 'string') d.responsible_person = saved.responsible_person.slice(0, 120)
    for (const [key, min, max] of [['max_jobs', 1, 100], ['duration_days', 1, 30], ['spend_cap_usd', 0, 100000], ['max_slowdown_percent', 0, 100]] as const) {
      if (typeof saved[key] === 'number' && Number.isFinite(saved[key]) && saved[key] >= min && saved[key] <= max) d[key] = saved[key]
    }
    return d
  } catch { return { ...defaults } }
}

function validation(d: Draft): string {
  for (const [label, value] of [['Review date', d.review_date], ['Contract change date', d.contract_date]]) {
    if (value) {
      const parsed = new Date(value + 'T00:00:00Z')
      if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || !Number.isFinite(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== value) return label + ' must be a real date in YYYY-MM-DD format.'
    }
  }
  if (!Number.isInteger(d.max_jobs) || d.max_jobs < 1 || d.max_jobs > 100) return 'Choose a whole-number trial limit from 1 to 100 jobs.'
  if (!Number.isInteger(d.duration_days) || d.duration_days < 1 || d.duration_days > 30) return 'Choose a whole-number duration from 1 to 30 days.'
  if (!Number.isFinite(d.spend_cap_usd) || d.spend_cap_usd < 0 || d.spend_cap_usd > 100000) return 'Enter a spending cap between $0 and $100,000.'
  if (!Number.isFinite(d.max_slowdown_percent) || d.max_slowdown_percent < 0 || d.max_slowdown_percent > 100) return 'Enter a runtime increase between 0% and 100%.'
  return ''
}

export function TrialPlanner({ price, datasetRevision }: { price: number; datasetRevision: string }) {
  const key = storageKey + ':' + datasetRevision
  const [draft, setDraft] = useState<Draft>(() => loadDraft(key))
  const [data, setData] = useState<Shortlist | null>(null)
  const [plan, setPlan] = useState<Plan | null>(null)
  const [error, setError] = useState('')
  const [planError, setPlanError] = useState('')
  const [saved, setSaved] = useState(true)
  const [pending, setPending] = useState(true)
  const [busy, setBusy] = useState(false)
  const [downloaded, setDownloaded] = useState(false)
  const [revision, setRevision] = useState(0)
  const [raw, setRaw] = useState<string | null>(null)
  const invalid = validation(draft)
  const payload = { ...draft, price, contract_date: draft.contract_date || null, review_date: draft.review_date || null }
  function update(values: Partial<Draft>) { setDownloaded(false); setDraft(d => ({ ...d, ...values })) }
  useEffect(() => {
    try { localStorage.setItem(key, JSON.stringify(draft)); setSaved(true) } catch { setSaved(false) }
  }, [draft, key])
  useEffect(() => {
    const c = new AbortController()
    setData(null); setError('')
    fetch(`/api/reclaim/trial-shortlist?action_id=${draft.action_id}&owners=${draft.owners}&price=${price}`, { signal: c.signal })
      .then(r => { if (!r.ok) throw new Error('The shortlist could not load.'); return r.json() })
      .then(setData).catch(e => { if (e.name !== 'AbortError') setError(e.message) })
    return () => c.abort()
  }, [draft.action_id, draft.owners, price, revision])
  useEffect(() => {
    const c = new AbortController()
    setPending(true); setPlanError('')
    if (invalid) { setPlan(null); setPending(false); return () => c.abort() }
    const t = setTimeout(() => {
      fetch('/api/reclaim/trial-plan', { method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: c.signal, body: JSON.stringify({ ...draft, price, contract_date: draft.contract_date || null, review_date: draft.review_date || null }) })
        .then(r => { if (!r.ok) throw new Error('The draft could not be prepared. Check the dates and limits, then retry.'); return r.json() })
        .then(p => { setPlan(p); setPending(false) }).catch(e => { if (e.name !== 'AbortError') { setPlanError(e.message); setPending(false) } })
    }, 200)
    return () => { clearTimeout(t); c.abort() }
  }, [draft, price, revision, invalid])
  async function download() {
    setBusy(true); setDownloaded(false); setPlanError('')
    try {
      const r = await fetch('/api/reclaim/trial-brief', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      if (!r.ok) throw new Error('The brief could not be exported. Check your entries and retry.')
      const url = URL.createObjectURL(await r.blob())
      const a = document.createElement('a'); a.href = url; a.download = 'reclaim-trial-brief.html'; a.click()
      setTimeout(() => URL.revokeObjectURL(url), 60000); setDownloaded(true)
    } catch (e) { setPlanError(String(e)) } finally { setBusy(false) }
  }
  const route = data?.billing_paths[draft.billing_model]
  return <div className="trial-planner">
    <div className="planner-intro"><ClipboardList size={23} /><div><strong>Choose a small trial you can review.</strong><p>Start with the owners behind the opportunity, check how the bill could change, and set limits before any work begins.</p></div><span>{saved ? 'Draft saved in this browser' : 'Browser saving unavailable — export your draft'}</span></div>
    <section className="card planner-card">
      <div className="section-top"><div><span className="eyebrow">01 / OWNERS TO CONSULT</span><h2>Where a few conversations could help</h2></div><Users size={23} /></div>
      <div className="planner-controls"><label className="planner-field"><span>Proposed change</span><select value={draft.action_id} onChange={e => update({ action_id: e.target.value as Draft['action_id'], confirmations: [] })}><option value="cpu-placement">Test CPU-only placement</option><option value="idle-sessions">Trial session warnings</option></select></label><fieldset className="owner-count"><legend>Owners with the most eligible GPU time</legend>{([1, 3, 5] as const).map(n => <button key={n} aria-pressed={draft.owners === n} className={'button ' + (draft.owners === n ? 'primary' : 'secondary')} onClick={() => { if (draft.owners !== n) update({ owners: n, confirmations: [] }) }}>Top {n}</button>)}</fieldset></div>
      {error ? <p className="inline-error">{error} <button onClick={() => setRevision(r => r + 1)}>Retry</button></p> : !data ? <p className="planner-loading"><LoaderCircle className="spin" size={17} />Ranking the source records…</p> : <>
        <div className="shortlist-summary"><div><strong>{data.selected_share_percent.toFixed(1)}%</strong><span>of this action’s eligible GPU time</span></div><p><b>{data.selected_owners} of {data.total_owners} researcher accounts</b> cover {whole(data.selected_gpu_hours)} eligible GPU-hours across {whole(data.selected_jobs)} historical jobs. {data.selected_jobs ? 'Start by asking these owners which repeat runs are suitable.' : 'No eligible workloads were found for this action. Choose another action or load new data.'}</p><button className="text-button" onClick={() => document.getElementById('trial-brief')?.scrollIntoView({ behavior: 'smooth' })}>Use in trial brief<ArrowDown size={15} /></button></div>
        <div className="owner-rows">{data.owners.map((o, i) => <div className="owner-row" key={o.id}><span className="owner-rank">{i + 1}</span><div className="owner-identity"><strong>{o.label}</strong><small>{whole(o.jobs)} matching jobs</small></div><div className="owner-measure"><strong>{whole(o.eligible_gpu_hours)} GPU-h</strong><span>{o.share_percent.toFixed(1)}% of eligible time</span><div className="owner-bar"><i style={{ width: o.share_percent + '%' }} /></div></div><details className="owner-records"><summary>Source jobs</summary>{o.example_jobs.map(j => <button className="job-link" onClick={() => setRaw(j.id)} key={j.id}>{j.id}<ArrowUpRight size={12} /></button>)}</details></div>)}</div>
        <p className="planner-note">The percentage measures concentration in the historical sample. It does not predict trial savings or assess researcher performance. IDs are anonymized; a named owner still needs to agree.</p>
        <details className="json-details"><summary>How the shortlist is calculated</summary><p>{data.basis}</p><p>{data.limitation}</p><p>{data.owners_for_80_percent} owners account for at least 80% of this action’s eligible time. All {data.total_owners} owners together account for {whole(data.total_eligible_gpu_hours)} eligible GPU-hours.</p></details>
      </>}
    </section>
    <section className="card planner-card">
      <div className="section-top"><div><span className="eyebrow">02 / PATH TO CASH</span><h2>What has to change for the bill to fall?</h2></div><span className="pill neutral">Commercial inputs</span></div>
      <div className="billing-options" role="group" aria-label="How the capacity is paid for">{(['owned', 'committed', 'usage'] as const).map(model => <button key={model} aria-pressed={draft.billing_model === model} className={'billing-option ' + (draft.billing_model === model ? 'selected' : '')} onClick={() => { if (draft.billing_model !== model) update({ billing_model: model, confirmations: [], contract_date: '' }) }}><span>{model === 'owned' ? 'Owned equipment' : model === 'committed' ? 'Prepaid / committed' : 'Usage-based billing'}</span><small>{model === 'owned' ? 'Reuse or defer a purchase' : model === 'committed' ? 'Review the next contract change' : 'Reduce actual billed resources'}</small></button>)}</div>
      {route && <div className="cash-route"><div><h3>{route.outcome}</h3><p>{route.explanation}</p><div className="cash-unknown"><span className="eyebrow">VERIFIED BILL REDUCTION</span><strong>Not established</strong><span>Telemetry shows resource use. Contracts and invoices are still needed.</span></div></div><div className="commercial-checks"><span className="eyebrow">CONFIRM WITH FINANCE AND OPERATIONS</span>{route.checks.map(check => <label className="planner-check" key={check.id}><input type="checkbox" checked={draft.confirmations.includes(check.id)} onChange={e => update({ confirmations: e.target.checked ? [...draft.confirmations, check.id] : draft.confirmations.filter(x => x !== check.id) })} /><span>{check.label}</span></label>)}{draft.billing_model === 'committed' && <label className="planner-field"><span>Next date the commitment can change</span><input type="text" placeholder="YYYY-MM-DD" maxLength={10} autoComplete="off" value={draft.contract_date} onChange={e => update({ contract_date: e.target.value })} /></label>}<p className="planner-note">Checks record your statements. They do not verify a contract or establish savings.</p></div></div>}
      {plan && !pending && <div className={'cash-status ' + (plan.cash.conditions_confirmed ? 'conditions-entered' : '')}>{plan.cash.conditions_confirmed ? <Check size={16} /> : <CircleHelp size={16} />}<div><strong>{plan.cash.status}</strong><p>{plan.cash.next_step}</p></div></div>}
    </section>
    <section className="card planner-card" id="trial-brief">
      <div className="section-top"><div><span className="eyebrow">03 / DRAFT FOR REVIEW</span><h2>What are we asking someone to approve?</h2></div><span className="pill neutral">No action executed</span></div>
      <p className="planner-description">The selected owners and billing conditions carry into this brief. The limits below are editable examples; agree them with the workload owners.</p>
      <div className="trial-brief-grid"><div className="trial-fields">
        <label className="planner-field field-wide"><span>Responsible person or role</span><input type="text" maxLength={120} placeholder="Assign a trial lead" value={draft.responsible_person} onChange={e => update({ responsible_person: e.target.value })} /></label>
        <label className="planner-field"><span>Review date</span><input type="text" placeholder="YYYY-MM-DD" maxLength={10} autoComplete="off" value={draft.review_date} onChange={e => update({ review_date: e.target.value })} /></label>
        <label className="planner-field"><span>Trial duration (days)</span><input type="number" min={1} max={30} step={1} value={draft.duration_days} onChange={e => update({ duration_days: +e.target.value })} /></label>
        <label className="planner-field"><span>Maximum trial jobs, total</span><input type="number" min={1} max={100} step={1} value={draft.max_jobs} onChange={e => update({ max_jobs: +e.target.value })} /></label>
        <label className="planner-field"><span>Total trial spending cap ($)</span><input type="number" min={0} max={100000} step={50} value={draft.spend_cap_usd} onChange={e => update({ spend_cap_usd: +e.target.value })} /></label>
        {draft.action_id === 'cpu-placement' && <label className="planner-field field-wide"><span>Maximum runtime increase (%)</span><input type="number" min={0} max={100} value={draft.max_slowdown_percent} onChange={e => update({ max_slowdown_percent: +e.target.value })} /></label>}
        <p className="planner-note field-wide">The cap includes incremental trial spending such as staff time and replacement compute. It is a proposed limit, not a cost estimate. The trial lead must monitor and enforce it.</p>
      </div><div className="trial-preview" aria-busy={pending}>
        <span className="eyebrow">BRIEF PREVIEW</span>
        {pending ? <p className="planner-loading"><LoaderCircle className="spin" size={16} />Updating the draft…</p> : invalid ? <p className="inline-error">{invalid}</p> : plan && <>
          <h3>{plan.status}</h3><div className="trial-preview-stats"><span><b>{draft.max_jobs}</b> jobs total</span><span><b>{draft.duration_days}</b> days</span><span><b>{usd(draft.spend_cap_usd)}</b> proposed cap</span></div>
          <p>{plan.scope_note}</p><h4>Success criteria</h4><p>{plan.success}</p><h4>Stop or reverse the change</h4><p>{plan.stop}</p>
          {plan.missing.length > 0 && <p className="trial-missing">Before owner review: {plan.missing.join(' ')}</p>}
        </>}
      </div></div>
      {planError && <p className="inline-error">{planError} <button onClick={() => setRevision(r => r + 1)}>Retry</button></p>}
      <div className="brief-export"><div><strong>Download a one-page decision brief</strong><p>Includes the shortlist, conditions, limits and space to record the decision. Open the HTML file in a browser to print or save as PDF.</p></div><button className="button primary" disabled={busy || pending || !!invalid || !data || !plan || !plan.eligible || !!planError} onClick={download}>{busy ? <LoaderCircle className="spin" size={16} /> : <Download size={16} />}Download trial brief</button></div>
      {downloaded && <p className="download-confirmation" role="status"><Check size={15} />Brief download prepared. It remains a draft for review.</p>}
    </section>
    {raw && <RawJob id={raw} close={() => setRaw(null)} />}
  </div>
}
