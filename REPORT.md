# Reclaim — Track 2 report

## Decision

Pilot CPU placement for successful jobs with no observed GPU compute, then trial warnings for long interactive allocations with very low GPU activity. Research platform owns the first pilot; scheduler operations owns the second. Do not authorize a fleet cut from these observations alone.

At $2.50/GPU-hour, the base recovery scenario is **16,206.57 GPU-hours, worth $40,516.43 in capacity**. Low/high scenarios are **8,879.80 / 24,377.49 GPU-hours**, or **$22,199.50 / $60,943.73**. These are adoption and feasibility scenarios, not measured treatment effects or confidence intervals. Actual recovery may be zero.

The base case is **2.73% of observed allocation**. It covers **13.64%** of the sample-equivalent 20% target of **$297,001.92**, leaving **$256,485.50** without an investigated claim. None of these values establishes next-quarter cash savings. Capacity reduces a bill only when a billing or procurement decision makes it reducible.

## Data and accounting

The official prepared sample contains **74,849 jobs, 195 researchers, 225 machines and 594,003.84 measured GPU-hours**. The shifted display window is February 25–June 30, 2026. We use the official epoch offset of 1,750,862,959 seconds and UTC conversion; these dates do not turn historical data into a forecast. All five files match `data/checksums.txt`.

GPU-hours reconcile between `jobs.parquet` and `gpus.parquet`. Sample allocation value is **$1,485,009.60**:

| Outcome | GPU-hours | Capacity value |
|---|---:|---:|
| Completed | 229,040.57 | $572,601.43 |
| Cancelled | 203,929.58 | $509,823.94 |
| Timed out | 107,951.52 | $269,878.80 |
| Failed | 50,033.16 | $125,082.89 |
| Scheduler node failure | 2,027.89 | $5,069.73 |
| Undecoded states | 1,021.12 | $2,552.81 |

Rounding can produce cent-level differences. Completed allocation is not completed compute: the brief's approximately 17% computed-and-completed proxy also weights SM utilization. Low SM activity can accompany useful preprocessing, communication or data loading. Neither the 83% headline nor cancellation alone measures recoverable waste.

Adding finding impacts produces **931,559.99 GPU-hours**, more than the sample. Even deduplicating job-scoped findings leaves **311,420.20 flagged hours**, which still are not automatically recoverable. We instead use explicit job cohorts. All **121 synthetic storage findings** are excluded from recovery. We do not estimate unallocated idle fleet capacity, which leaves no job telemetry.

## Two investigated actions

Candidates require positive walltime and GPU count, nonnegative measured GPU-hours, finite allocated hours, observed average and peak SM utilization, and exactly one attempt. Cap usable duration at `min(measured GPU-hours, GPU count × walltime / 3600)`. Exclude retries/requeues because the durations may not describe one clean execution.

| Rank | Action | Disjoint jobs | Eligible GPU-hours | Low / base / high recovery rates | Base recovered GPU-hours |
|---|---|---:|---:|---|---:|
| 1 | CPU placement | 463 | 11,985.85 | 50% / 75% / 95% | 8,989.39 |
| 2 | Interactive-session warnings | 797 | 28,868.72 | 10% / 25% / 45% | 7,217.18 |

**CPU placement.** Require `state_name == COMPLETED`, `sm_util_avg == 0`, `sm_util_max == 0`, and measured `gpu_hours > 1`, plus the quality filter. Successful completion with no recorded GPU compute is a placement signal. Rates express adoption and feasibility assumptions, not observed recovery. Pilot an opt-in cohort and compare output parity, CPU runtime and queue delay. Roll back if any worsens materially. GPU libraries, unobserved activity and scarce CPU capacity remain risks.

**Interactive sessions.** Require `job_type == LLSUB:INTERACTIVE`, walltime greater than four hours and average SM activity below 5%. Remove CPU-placement jobs first: **109 overlaps** belong to the first action. Subtract a four-hour grace period per GPU from capped duration, flooring at zero. This is an exposure envelope, not a located idle interval. Use lower scenario rates because averages cannot tell when termination would have been safe. Start warning-only; collect user responses and continuous activity before any opt-in expiry. Keep expiry disabled until false positives are measured.

The second cohort includes **58 cancelled jobs**, selected for activity and duration, not simply cancellation. No blanket cancellation recovery is claimed. No retry ambiguity excludes additional jobs in these particular cohorts, although the rule is enforced.

## Cost of being wrong

The Risk lab uses the two disjoint cohorts and these visible assumptions:

```
recovered hours = base scenario hours × recovery achieved
rerun hours = cohort observed hours × disruption rate
operator hours = cohort job count × disruption rate × hours per affected job
downside value = rerun hours × GPU price + operator hours × $95
net capacity value = recovered hours × GPU price − downside value
```

Defaults assume 100% of base recovery, 2% useful jobs disrupted and 0.5 operator hours per affected job. That models **902.28 GPU-hours of reruns**, **12.6 operator hours**, and **$3,452.71** of valued rework. Net capacity value is **$37,063.71**. Benefit disappears at approximately **23.47% disruption**, holding the other defaults fixed. This is a model boundary, not an acceptable disruption target.

The bill-reduction slider defaults to **0%**. Gross bill reduction is therefore **$0**, and bill reduction less valued rework is **−$3,452.71**. GPU and salary rates are opportunity-cost proxies, not incremental invoices.

The model assumes a uniform disruption rate and full-duration reruns. It does not price CPU migration, setup effort, lost research output, queue delay or downstream deadlines. Those need pilot measurements. The UI and tests cover zero recovery and high disruption, not only favorable scenarios.

## Real causal evidence

We select the real array-mass-failure finding with the most linked task findings, resolve it through official Layer A `causal`, then join task `job_id` to `jobs.id_job` and `gpus.id_job`, counting distinct `gpus.Node`. The result is **721 failed tasks across 34 machines**, linked to one shared array. The interface exposes the finding ID, causal response and source evidence.

Inspect the shared workload before draining machines. Dispersion and a shared exit code support workload triage; they do not prove every machine healthy or establish hardware-attributable failures. The node and scheduler claims below are separate investigations. Synthetic-incident claims remain omitted.

The PCIe saturation rule is armed with zero findings. That supplies no positive support for a PCIe upgrade, but does not rule out every I/O or data-loading bottleneck.

## Three node decisions, with controls

We join distinct `(gpus.Node, gpus.id_job)` placements to `jobs.id_job`, use `time_end` for window membership, and inspect `id_user`, `id_array_job`, `exit_code` and `attempts`. The detector's 14-day windows begin at the sample's exact origin (2026-02-25 21:58:51 UTC), not midnight on the rounded date label. These are selected case studies, not a calibration set or classifications for every flagged window.

| Node / window | Evidence | First decision |
|---|---|---|
| `r216287-n200569` / 0 | 188/243 FAILED; enclosed hardware episode has 114 matching-signature failures across three researchers, versus 0/311 same-window jobs elsewhere for those researchers | Inspect the machine; choose any drain duration with the owner |
| `r1039410-n772143` / 8 | 32/34 failures belong to one researcher's array; 568/568 same-window sibling jobs elsewhere fail with the same packed exit code 256; other researchers here have 2/14 failures | Investigate shared workload/environment before draining |
| `r216287-n200569` / 3 | 33/62 FAILED in a later window; dominant user owns 20 failures, others 13/35; no matching episode or strong replicated array control establishes cause | Monitor and obtain controlled reruns; cause unresolved |

All three node/window counts reproduce the corresponding detector counts. Our raw-placement reconstruction matches 112 of 113 windows. One omitted window (`r8473362-n410412`, window 4) has 115 joined jobs versus the detector's 116, with 56 failures in both; we do not silently repair or claim that case. Retry placements and the generator's node-list membership can differ from the per-GPU placement join.

The hardware episode spans February 27–March 7, 192 hours. There are 144 single-attempt jobs, 140 FAILED, and 114 with `exit_code // 256 == 135`. Same-window controls are:

| Researcher | Signature / jobs here | Signature / jobs elsewhere |
|---|---:|---:|
| `u-56073333661` | 86 / 86 | 0 / 268 |
| `u-16337070303` | 23 / 27 | 0 / 40 |
| `u-32801634342` | 5 / 5 | 0 / 3 |

This supports a machine-specific investigation, not a physical diagnosis or attribution of every failure. Shared environment remains a possible confounder, jobs are correlated, and the small third control group is weak individually. We use same-window controls rather than copying the detector's larger whole-sample control counts. A hardware label from this episode is not carried into the later window.

For `hardware_attributable_failures`, we count **31 distinct jobs** with scheduler `hit_node_failure`, reconciled to **39 failed attempts**. Only **10** end in NODE_FAIL; 21 have another final outcome. Failed-attempt `nodefail_nodes`, not a retry's final placement, identify scheduler failure locations. This is a scheduler-only count, not all hardware-caused failures; the SIGBUS episode is not added to it.

## Argue with the proposed drain recommendation

Layer B recommends the five nodes with most findings and claims **22,890.4 GPU-hours / $57,225.93**, with a fixed 0.58 confidence. Its ranking misses the explicit hardware-episode node. Its total combines finding impacts without establishing preventability or removing overlap. Neither the fixed confidence nor the dollar amount is a measured treatment effect. This mismatch does not establish that all five ranked nodes are healthy.

The drain model values a repeated episode against temporarily unavailable capacity:

```
assumed avoided hours = observed matching-signature hours × avoidable fraction
unavailable hours = machine count × 2 GPUs × drain duration
net capacity value = (avoided hours − unavailable hours) × GPU price
                     − total operator hours × $95
```

An unexpected result is that the 114 signature jobs fail within **0–5 seconds** of walltime, leaving just **0.022094 capped node GPU-hours**. The larger all-failed exposure is not attributed wholesale to this signature. At defaults (one repeat, 50% avoidable, one machine, four-hour drain, one operator hour), modeled avoided time is worth **$0.03**, unavailable capacity **$20**, and operator effort **$95**: net **−$114.97**. Five machines cost $100 of unavailable capacity, making net **−$194.97** with the same total operator effort. The five-machine setting is a cost sensitivity, not a replay of the proposed endpoint's specific five-node set.

Hardware inspection may still be justified by research reliability. This narrow GPU-time model does not value research disruption, repeated debugging, missed deadlines or queue spillover. It assumes one recurrence and an avoidable fraction, not a recurrence forecast or calibrated fault probability. Capacity cost charges all unavailable slots even if unoccupied, so it is neither demonstrated displaced work nor an incremental invoice. The UI exposes the break-even duration and identifies cases where labor alone exceeds the modeled benefit.

## Per-card imbalance investigation

We recompute imbalance from `gpus.parquet` at `(Node, gpu_id, id_job)` grain: at least two observed cards, busiest average SM ≥20%, busiest-minus-quietest average SM >30 percentage points. Require COMPLETED, walltime >1 hour, attempts=1. Clip each card's hours to job walltime. This avoids treating job averages or local card index as a physical device identity.

| Quiet-card evidence | Cards / jobs | GPU-hours | Value at $2.50 |
|---|---:|---:|---:|
| Zero average and peak SM, ≤1% memory | 92 / 82 | 2,475.48 | $6,188.71 |
| Zero average and peak SM (point) | 380 / 370 | 4,100.17 | $10,250.43 |
| Zero average SM only | 419 / 409 | 4,685.45 | $11,713.63 |

These are measured exposure thresholds, not recovery rates or statistical confidence limits. **288 of the 380 zero-peak cards still hold >1% memory**; even low-memory cards have nonzero PCIe counters. Memory is a peak measurement; coarse/censored PCIe counters do not establish sustained useful transfers. Device binding, memory residency and communication must be checked before removing a card. The interface pairs average/peak compute, memory, transfers and capped duration for every card of the selected job, with raw records available.

Quiet rows skew toward local GPU 0 (365 versus 15 on GPU 1). This is a placement association, not evidence that physical GPU 0 is faulty. There are zero overlapping jobs with the two existing recovery cohorts, but **none of these hours is added to the savings headline** without a fewer-card replay that preserves output parity and acceptable runtime.

## API and MCP design

Official FastAPI routes remain available. `/api/reclaim` adds cohort evidence, raw records, scenarios and claims. The investigator uses `fastmcp.Client` against the official server through actual in-process MCP transport. Each investigation retrieves `decision_evidence` (our deterministic tool), official `list_rules`, then official `list_findings` or `causal`.

This is a bounded retrieval-and-explanation workflow, not autonomous tool selection. The model receives a small evidence bundle. Calculations never depend on model output. Live explanations are labeled with trace and usage; provider failure preserves evidence-only operation. Calls are serialized, limited to two attempts and cached for ten minutes. Usage includes unsuccessful attempts when returned by the provider; a timeout can have unreported usage. Keys, raw errors and reasoning text are not logged.

Requests use JSON mode with non-thinking generation. Only final content matching four expected string fields and a retrieved finding ID is accepted. The model writes recommendation, downside and pilot prose without numeric claims; prose containing digits is rejected. The evidence section renders counts, eligible hours, recovery and dollars directly from deterministic calculations. This prevents a tested failure in which model prose confused observed and capped eligible hours. Provider reasoning is never used as answer text. Each attempt has a 45-second total deadline. Structure and citation checks do not establish factual correctness of every sentence; a formal explanation-quality evaluation remains future work. See [Featherless's template documentation](https://featherless.ai/docs/chat-template-kwargs).

We do not inherit Layer B recommendations as action authority. A business API should distinguish measured exposure, deduplicated eligibility, assumed recovery, intervention evidence and realizable cash. `kind: fact` alone does not express those differences. Each Reclaim action supplies its filter, overlap ownership, unit/grain, scenario bounds, pilot and rollback. Future API fields should include treatment-effect evidence, uncertainty provenance and billing constraints.

The initial live Docker smoke check completed in **8.1 seconds**, using **2,309 input and 122 output tokens** on GLM-4.7-Flash. It cited a retrieved finding and displayed the exact capped eligible hours and base dollar value. The added hardware-audit briefing completed in **8.22 seconds / 2,206 total tokens**, via `decision_evidence`, `list_rules` and `causal`. These are integration checks, not latency benchmarks or empirical calibration studies.

## Calibration and limits

We use `interval_kind: scenario`, explicitly supported by the provided schema. Endpoints vary disclosed assumptions; they are not said to cover hidden truth with a measured probability. We do not invent a confidence score from observational data. The official validator warns because it checks only top-level `*_confidence` fields and ignores nested estimate confidence. The claims pass its schema; its warning is not a complete grading rule. Card intervals vary measured evidence thresholds. `zero_recovery_stress` also records no recovery with default disruption: **−$3,452.71** net valued capacity. A measured intervention evaluation remains future work.

To calibrate: preregister cohorts and success criteria, start with shadow warnings and opt-in CPU migrations, measure output parity, runtime, queue delay, released hours and false positives, then compare observations with the declared scenarios. Randomized or matched holdouts and researcher/workload stratification would improve attribution. Expand only after replacing assumptions with measured outcomes.

## Reproduction and validation

Follow `README.md`. `scripts/export_claims.py` uses the UI's accounting functions, defaulting to $2.50/GPU-hour. UI export honors the selected price. Claims include recovery, cancellation rationale, three investigated node windows, scheduler-recorded hardware failures and per-card exposure; synthetic incident claims remain omitted.

**23 automated checks pass**, covering reconciliation, duration caps, disjoint ownership, cancellation, price invariance, downside, joins, claim/UI agreement, API validation, actual MCP retrieval, provider errors, empty final answers, token aggregation, cache reuse, cohort-specific context and citation validation. Five official checksums and the TypeScript/production frontend build pass. The Docker launch and browser walkthrough are checked locally, including 1280-pixel desktop and 390-pixel phone layouts; `DEMO.md` gives the repeatable sequence.

The generator and its rules are unchanged. A wrapper uses container-native temporary storage and disables Go GC to avoid an observed local execution issue; outputs remain checksum-identical. Telemetry and generated findings are excluded from Git. AI assistance and inherited code are disclosed in `README.md`.

A fresh clone of the public repository was rehearsed on local Docker/ARM64: downloaded the official raw archive, ran `make prep`, `make generate`, and `make check-data` (five matches), then launched with `docker compose up -d --wait` on ports 3000/8000 with no `.env`. The exported JSON exactly matched committed `claims.json`; the key-free MCP hardware brief completed through all three tools in 0.18 seconds. The official validator confirmed schema validity and HTTP 200, retaining the intentional confidence warning. The image build reused local base/dependency caches; this is not a cold-download timing benchmark.
