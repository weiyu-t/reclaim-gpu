import { useEffect, useRef, useState } from 'react'
import { ArrowUpRight, Check, ChevronLeft, ChevronRight, Cpu, FlaskConical, LoaderCircle, ShieldCheck, X } from 'lucide-react'

const whole = (n: number) => n.toLocaleString('en-US', { maximumFractionDigits: 0 })
const usd = (n: number) => n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 })
const date = (s: string) => new Date(s).toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })

async function get(path: string, signal?: AbortSignal) {
  const r = await fetch('/api/reclaim' + path, { signal })
  if (!r.ok) throw new Error('The investigation could not load (' + r.status + ').')
  return r.json()
}

function useEvidence(path: string) {
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const [pending, setPending] = useState(true)
  useEffect(() => {
    const c = new AbortController()
    setPending(true); setError('')
    get(path, c.signal).then(d => { setData(d); setPending(false) }).catch(e => { if (e.name !== 'AbortError') { setError(e.message); setPending(false) } })
    return () => c.abort()
  }, [path, revision])
  const status = error ? <div className="inline-error">{error}<button onClick={() => setRevision(x => x + 1)}>Retry</button></div> : !data ? <div className="research-loading"><LoaderCircle className="spin" size={20} />Checking the source records…</div> : null
  return { data, status, pending }
}

export function RawJob({ id, close }: { id: string; close: () => void }) {
  const ref = useRef<HTMLDialogElement>(null)
  const { data, status } = useEvidence('/jobs/' + id)
  useEffect(() => { ref.current?.showModal() }, [])
  return <dialog ref={ref} className="evidence-dialog" onCancel={close} aria-label={'Raw job ' + id} onClick={e => { if (e.target === e.currentTarget) close() }}>
    <div className="drawer-inner"><div className="drawer-top"><span className="eyebrow">SOURCE RECORDS</span><button className="icon-button" aria-label="Close raw job" onClick={close}><X size={20} /></button></div>
      <h2>Job {id}</h2><p className="section-description">Job, per-GPU measurements, and linked findings from the local dataset.</p>{status}
      {data && <><p className="small-muted">{data.source}</p><pre className="research-raw">{JSON.stringify(data, null, 2)}</pre></>}
    </div>
  </dialog>
}

export function NodeDecisions({ price, briefing }: { price: number; briefing: React.ReactNode }) {
  const { data, status } = useEvidence('/node-audit?price=' + price)
  const [selected, setSelected] = useState(0)
  const [raw, setRaw] = useState<string | null>(null)
  if (!data) return status
  const h = data.hardware, c = data.cases[selected]
  const labels: Record<string, string> = { hardware: 'Machine-specific signal', user_code: 'Shared workload signal', cannot_determine: 'Cause unresolved' }
  return <>
    {status}
    <div className="plan-summary"><ShieldCheck size={24} /><div><strong>Review the proposed machine removals before approving them.</strong><p>The proposed API recommends draining five machines for {usd(data.baseline.recommendation.estimated_savings.amount)}. Its ranking misses the node with the explicit hardware episode.</p></div><span className="pill neutral">Layer B audited</span></div>
    <div className="research-case-tabs" role="tablist" aria-label="Node investigations">{data.cases.map((x: any, i: number) => <button key={x.id} role="tab" aria-selected={selected === i} className={'card case-tab ' + (selected === i ? 'selected' : '')} onClick={() => setSelected(i)}>
      <span className="eyebrow">CASE {i + 1} / {x.cause === 'hardware' ? 'Inspect' : x.cause === 'user_code' ? 'Workload review' : 'Monitor'}</span><strong>{labels[x.cause]}</strong><span>{x.node}</span><small>{date(x.start)} – {date(x.end)} · window {x.window}</small>
    </button>)}</div>
    <section className="card research-card" role="tabpanel" aria-label={labels[c.cause]}>
      <div className="section-top"><div><span className="eyebrow">{c.node} · {date(c.start)}–{date(c.end)} UTC</span><h2>{c.decision}</h2></div><span className={'pill ' + (c.cause === 'cannot_determine' ? 'neutral' : 'green')}>{c.cause.replaceAll('_', ' ')}</span></div>
      <div className="research-metrics"><div><strong>{(c.rate * 100).toFixed(1)}%</strong><span>FAILED on this node</span></div><div><strong>{(c.cluster_rate * 100).toFixed(1)}%</strong><span>cluster rate in window</span></div><div><strong>{c.failed} / {c.jobs}</strong><span>failed jobs / all outcomes</span></div></div>
      <p className="research-body">{c.explanation}</p>
      {c.cause === 'hardware' && <><div className="research-callout"><strong>{h.signature_jobs} matching failures here. {h.elsewhere_signature} in {h.elsewhere_jobs} jobs elsewhere.</strong><p>Same researchers, same {h.hours}-hour episode ({date(h.start)}–{date(h.end)}). Packed exit status {h.exit_status}. Correlated jobs are not independent trials.</p></div>
        <div className="table-scroll"><table><thead><tr><th>Researcher</th><th>Here: signature / jobs</th><th>Elsewhere: signature / jobs</th><th>Inspect source</th></tr></thead><tbody>{h.controls.map((x: any) => <tr key={x.user}><td>{x.user}</td><td>{x.here_signature} / {x.here_jobs}</td><td>{x.elsewhere_signature} / {x.elsewhere_jobs}</td><td><button className="job-link" onClick={() => setRaw(x.here_job_ids[0])}>Here</button> · <button className="job-link" onClick={() => setRaw(x.elsewhere_job_ids[0])}>Elsewhere</button></td></tr>)}</tbody></table></div><p className="small-muted research-note">{h.limitation}</p></>}
      {c.array_control && c.cause === 'user_code' && <div className="research-callout"><strong>{c.array_control.matching_exit_elsewhere} sibling failures across other machines</strong><p>The same array and packed exit code repeat elsewhere. Workload ownership gives a narrower first action than removing node capacity.</p><button className="text-button" onClick={() => setRaw(c.array_control.peer_job_ids[0])}>Inspect a sibling job<ArrowUpRight size={15} /></button></div>}
      {c.cause === 'cannot_determine' && <div className="research-callout"><strong>A past hardware episode is not a permanent node label.</strong><p>This later window is on the same machine. Its failure rate alone does not establish that the earlier fault recurred.</p></div>}
      <details className="json-details"><summary>Inspect this window’s jobs, joins, and finding</summary><p>{data.method}</p><div className="research-job-links">{c.examples.map((x: any) => <button className="job-link" key={x.id} onClick={() => setRaw(x.id)}>{x.id} · {x.state}</button>)}</div><pre>{JSON.stringify({ finding_id: c.id, start: c.start, end: c.end, counts_match_detector: c.detector_counts_match, controls: c.controls }, null, 2)}</pre></details>
    </section>
    <DrainLab price={price} node={h.node} />
    <section className="card research-card"><div className="section-top"><div><span className="eyebrow">CHECK THE RECOMMENDATION</span><h2>Why the automatic recommendation needs review</h2></div><Cpu size={22} /></div><p className="research-body">{data.baseline.audit}</p>
      <div className="research-node-list">{data.baseline.nodes.map((x: any) => <span key={x.entity_id}><Cpu size={14} />{x.entity_id}<b>{x.finding_count} findings</b></span>)}</div>
      <details className="json-details"><summary>Inspect proposed recommendation and official causal response</summary><pre>{JSON.stringify({ baseline: data.baseline, hardware_causal: data.causal }, null, 2)}</pre></details>
      {briefing}
    </section>
    <section className="card quiet-card"><ShieldCheck size={26} /><div><h3>{data.history.jobs} jobs encountered {data.history.attempts} scheduler-recorded failed attempts.</h3><p>Only {data.history.terminal_node_fail} finish as NODE_FAIL. A final outcome hides retry history. Our hardware-count claim uses recorded scheduler evidence and keeps the SIGBUS investigation separate.</p></div></section>
    {raw && <RawJob id={raw} close={() => setRaw(null)} />}
  </>
}

function DrainLab({ price, node }: { price: number; node: string }) {
  const [duration, setDuration] = useState(4)
  const [fraction, setFraction] = useState(50)
  const [operator, setOperator] = useState(1)
  const [nodes, setNodes] = useState(1)
  const { data, status, pending } = useEvidence(`/drain-scenario?price=${price}&duration=${duration}&recurrence=${fraction / 100}&operator_hours=${operator}&nodes=${nodes}`)
  return <section className="card research-card"><div className="section-top"><div><span className="eyebrow">COST OF TAKING MACHINES OUT OF SERVICE</span><h2>What does taking capacity away cost?</h2></div><FlaskConical size={23} /></div>
    <p className="research-body">Reference episode: {node}, February 27–March 7. Assume one repeat; price avoidable GPU time against unavailable capacity and inspection effort. Research disruption and queue delays still need an owner’s assessment. The five-machine option compares costs; it does not reproduce the proposed API’s selection.</p>
    <div className="drain-grid"><div className="drain-controls">
      <RangeControl label="Time out of service per machine" value={duration} suffix=" hours" max={48} step={.5} change={setDuration} />
      <RangeControl label="Share of repeated GPU losses prevented" value={fraction} suffix="%" max={100} step={5} change={setFraction} />
      <RangeControl label="Total staff time · $95/hour" value={operator} suffix=" hours" max={8} step={.25} change={setOperator} />
      <fieldset className="node-switch"><legend>Machines made unavailable</legend>{[1, 5].map(n => <button className={'button ' + (nodes === n ? 'primary' : 'secondary')} key={n} aria-pressed={nodes === n} onClick={() => setNodes(n)}>{n === 1 ? 'One targeted machine' : 'Five machines'}</button>)}</fieldset>
    </div><div className="drain-result" aria-busy={pending}>{status}{pending && data && <span className="small-muted">Updating scenario…</span>}{data && <>
      <span className="eyebrow">GPU TIME BENEFIT MINUS INSPECTION COSTS</span><strong className={data.net_value_usd < 0 ? 'negative' : ''}>{usd(data.net_value_usd)}</strong>
      <div className="calc-line"><span>GPU time used by the matching failures</span><b>{data.observed_signature_gpu_hours.toFixed(3)} GPU-h</b></div>
      <div className="calc-line"><span>GPU time loss prevented</span><b>{usd(data.avoided_value_usd)}</b></div>
      <div className="calc-line"><span>Unavailable capacity · {data.unavailable_gpu_hours} GPU-h</span><b>−{usd(data.capacity_cost_usd)}</b></div>
      <div className="calc-line"><span>Staff cost</span><b>−{usd(data.operator_cost_usd)}</b></div>
      <p>{data.cannot_break_even_even_at_zero_drain ? 'Staff cost alone exceeds the modeled GPU-time benefit. Inspection may still be justified by research reliability; that value is not measured here.' : `Break-even drain duration: ${data.break_even_drain_hours.toFixed(4)} hours per machine under these assumptions.`}</p>
    </>}</div></div>
    {data && <p className="small-muted research-note">{data.caveat}</p>}
  </section>
}

function RangeControl({ label, value, max, step, suffix, change }: { label: string; value: number; max: number; step: number; suffix: string; change: (x: number) => void }) {
  return <label className="research-slider"><span>{label}<strong>{value}{suffix}</strong></span><input aria-label={label} type="range" min={0} max={max} step={step} value={value} onChange={e => change(+e.target.value)} /></label>
}

export function GPUCards({ price }: { price: number }) {
  const [offset, setOffset] = useState(0)
  const { data, status } = useEvidence('/card-imbalance?price=' + price + '&offset=' + offset)
  const [selected, setSelected] = useState(0)
  const [raw, setRaw] = useState<string | null>(null)
  if (!data) return status
  const example = data.examples[Math.min(selected, data.examples.length - 1)]
  return <>
    {status}
    <div className="plan-summary"><Cpu size={24} /><div><strong>Some jobs may be able to use fewer GPUs.</strong><p>Test the GPU allocation with workload owners. These estimates use completed jobs without retries and cap GPU hours to the job’s duration.</p></div><span className="pill neutral">Not in recovery total</span></div>
    <div className="card-thresholds">{data.thresholds.map((s: any) => <section className={'card threshold-card ' + (s.id === 'peak_zero' ? 'selected' : '')} key={s.id}>
      <span className="eyebrow">{s.id === 'small_memory' ? 'STRICTER EVIDENCE' : s.id === 'peak_zero' ? 'GPU TIME TO INVESTIGATE' : 'BROADER SCREEN'}</span><strong>{whole(s.gpu_hours)}<small> GPU-h</small></strong><b>{usd(s.value_usd)} capacity value</b><p>{s.label}</p><span>{s.cards} card allocations · {s.jobs} jobs</span>
    </section>)}</div>
    <p className="small-muted research-note">These totals change with the selection rules; they are not estimates of time we can recover. {data.limitation}</p>
    <section className="card research-card"><div className="section-top"><div><span className="eyebrow">INDIVIDUAL GPU USE</span><h2>Which GPU did the work?</h2></div><span className="pill green">Measured per card</span></div>
      <div className="gpu-explorer"><div className="gpu-job-list"><span className="eyebrow">Most time on quiet GPUs first</span>{data.examples.map((j: any, i: number) => <button key={j.id} aria-pressed={selected === i} className={selected === i ? 'selected' : ''} onClick={() => setSelected(i)}><span>Job {j.id}</span><strong>{whole(j.quiet_gpu_hours)} GPU-h<ArrowUpRight size={13} /></strong></button>)}
        <div className="pagination"><span>{offset + 1}–{Math.min(offset + data.limit, data.total)} / {data.total}</span><div><button className="icon-button" aria-label="Previous card jobs" disabled={!offset} onClick={() => { setOffset(x => x - 20); setSelected(0) }}><ChevronLeft size={16} /></button><button className="icon-button" aria-label="Next card jobs" disabled={offset + data.limit >= data.total} onClick={() => { setOffset(x => x + 20); setSelected(0) }}><ChevronRight size={16} /></button></div></div>
      </div><div className="gpu-detail">
        <div className="section-top"><div><span className="eyebrow">JOB {example.id} · COMPLETED</span><h3>{example.job_avg_sm}% average compute hides the split.</h3></div><button className="text-button" onClick={() => setRaw(example.id)}>Raw records<ArrowUpRight size={15} /></button></div>
        <div className="gpu-legend"><span><i className="compute-key" />Average compute</span><span><i className="memory-key" />Peak memory occupied</span><span>Bar scale: 0–100%</span></div>
        {example.cards.map((c: any) => <div className={'gpu-measurement ' + (c.selected ? 'quiet' : '')} key={c.node + ':' + c.gpu_id}>
          <div className="gpu-label"><span><Cpu size={15} /><strong>GPU {c.gpu_id}</strong><small>{c.node}</small></span>{c.selected && <span className="pill neutral">Zero compute</span>}</div>
          <div className="gpu-bar-row"><span>Compute</span><div className="gpu-track"><i style={{ width: c.avg_sm + '%' }} /></div><b>{c.avg_sm}%</b></div>
          <div className="gpu-bar-row memory"><span>Peak mem.</span><div className="gpu-track"><i style={{ width: c.memory_pct + '%' }} /></div><b>{c.memory_pct}%</b></div>
          <p>Peak compute {c.peak_sm}% · Reported PCIe Rx+Tx {whole(c.pcie_mbps)} MB/s · {c.capped_hours.toFixed(2)} allocated GPU-h</p>
        </div>)}
        <div className="research-callout"><strong>Zero compute does not establish that a card is removable.</strong><p>{data.pilot}</p></div>
      </div></div>
    </section>
    <div className="research-two-col"><section className="card research-card"><span className="eyebrow">MEMORY STILL MATTERS</span><h2>{data.memory_above_one_percent_cards} quiet-card allocations exceeded 1% peak memory.</h2><p className="research-body">The strict screen falls to {whole(data.thresholds[0].gpu_hours)} GPU-hours. Even that subset has nonzero PCIe counters. Those counters are coarse and can be censored; they do not establish sustained useful transfers. Verify output parity and runtime before reducing the allocation.</p></section>
      <section className="card research-card"><span className="eyebrow">PLACEMENT ASSOCIATION</span><h2>Check how jobs assign work to GPUs</h2><p className="research-body">Local GPU 0: {data.quiet_card_index['0']} quiet rows. Local GPU 1: {data.quiet_card_index['1']} quiet rows. {data.index_caveat}</p></section></div>
    <details className="json-details"><summary>Inspect threshold and deduplication method</summary><p>{data.method}</p><p><Check size={13} /> {data.existing_plan_overlap_jobs} jobs overlap with the existing two recovery cohorts. Card exposure remains separate regardless.</p></details>
    {raw && <RawJob id={raw} close={() => setRaw(null)} />}
  </>
}
