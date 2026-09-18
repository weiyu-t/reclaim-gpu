# Loading and analyzing another dataset

Reclaim computes its results from the loaded telemetry. It is a rule-based GPU
workload analysis tool, not an arbitrary-file interpreter. New data must use the
documented column schema; there is no CSV guessing, automatic schema mapping, or
live telemetry collector. IDs, dates, users, nodes, job counts, failure signatures,
and eligible workloads do not need to match the hackathon sample.

## Directory layout

```text
my-cluster/
  dataset.json                 optional display/date/capacity configuration
  prepped/jobs.parquet
  prepped/gpus.parquet
  synthetic/resources.parquet
  synthetic/edges.parquet
  synthetic/findings.json
```

`synthetic/` is the inherited directory name for the projected API layer. It does
not mean every finding is synthetic. Mark simulated records with
`metadata.synthetic: true`; they cannot establish a machine diagnosis.

Job and GPU column descriptions are in [data.md](data.md). Required job columns:
`id_job`, `id_user`, `state_name`, `is_success`, `gpu_hours`, `gpu_hours_alloc`,
`gpu_count`, `walltime_sec`, `attempts`, `sm_util_avg`, `sm_util_max`, `job_type`,
`time_submit`, `time_start`, `time_end`, `exit_code`, `id_array_job`, `is_array_task`,
`hit_node_failure`, `nodefail_attempts`, `wait_sec`.

Required GPU columns: `id_job`, `Node`, `gpu_id`, `gpu_hours`,
`smutilization_pct_avg`, `smutilization_pct_max`, `mem_used_frac`,
`pcierxbandwidth_megabytes_avg`, `pcietxbandwidth_megabytes_avg`.

Use numeric job/user/array IDs, boolean flag columns and numeric measurements.
GPU IDs are local to a machine. Exit codes use the documented packed format
(`exit_code // 256` extracts exit status). Timestamps are seconds from the
configured origin. A missing start time is allowed for a job that never started.
Job IDs must be unique; GPU records must refer to supplied jobs.

The three projected files can be empty: `findings.json` contains `[]`, while the
Parquet tables retain their schemas from `docs/data.md`. Empty resource tables
need `id`, `type`, `name`, `resourceId`; empty edge tables need `sourceId`,
`destinationId` (plus any relationship metadata). Populated resources/findings follow the official
API models. Reclaim can discover candidate node windows and failed arrays from
raw records without precomputed findings. Missing findings do not mean a rule
was evaluated clean.

## Dataset configuration

For Unix timestamps and machines with eight GPUs:

```json
{
  "name": "Research cluster — January",
  "epoch_offset": 0,
  "gpus_per_node": 8
}
```

Without `dataset.json`, the display name is “Local workload dataset”, the epoch
offset is the official sample's `1750862959`, and drain scenarios assume two GPUs
per machine. Set these values for your source. GPU width is an assumption that can
also be changed in the drain calculator; it is not inferred installed inventory.
Reference GPU and staff prices and recovery fractions are scenario assumptions,
not measured costs or treatment effects. Recovery rates and disruption assumptions
can be varied in Downside costs.

## Select and reload

Native:

```bash
RECLAIM_DATA_DIR=/absolute/path/my-cluster uvicorn reclaim.main:app --port 8000
```

Docker (the selected directory is mounted read-only):

```bash
RECLAIM_DATA_DIR=/absolute/path/my-cluster docker compose up -d --build --force-recreate api dashboard
```

To update the selected directory, finish writing all five files and any metadata,
then click **Reload data** or POST `/api/reclaim/dataset/reload`. Do not run a
generator while loading. Reclaim checks the schemas and joins before switching
snapshots. Files changing during loading reject the reload. A rejected reload
retains the last valid snapshot and explains the error.

Each request, including an MCP/AI investigation, uses one pinned snapshot. A new
snapshot gets a new revision; cached analysis and model briefings cannot be reused
for another revision. The initiating browser remounts its views after a successful
reload. Trial drafts are scoped to a dataset revision so commercial confirmations
and owner selections cannot carry over silently to a new snapshot. Other browser sessions must refresh to fetch the new snapshot. Use the
single-process Uvicorn command above; multi-worker/distributed reload coordination
is not implemented.

## How decisions adapt

- Candidate trial groups and rankings are recomputed. Only actions with positive
  eligible time are recommended. A zero-result screen says so; it does not declare
  the cluster efficient. Trial export is disabled for unsupported cohorts.
- Node windows are recomputed over 14-day periods from the loaded sample origin,
  using the documented one-sided binomial screen (p < .01, at least 30 jobs locally
  and 100 in the window). Supplied candidate windows are also investigated.
- A hardware finding only nominates an episode. Inspection support requires a
  shared nonzero exit status across at least three researchers. Each must have at
  least two matching failures, at least 50% local signature frequency, at least
  five comparable-window jobs elsewhere, and at most 5% signature frequency there.
  These are conservative screening rules, not calibrated fault probabilities.
- All supported episodes and investigated windows are available, rather than
  requiring one hardware, one workload and one unresolved example. Missing or
  contradictory evidence does not authorize a drain. Shared software and
  correlated work remain possible confounders.
- Array candidates are discovered from raw jobs, with at least ten tasks and over
  90% failures. Replicated matching nonzero exit codes on multiple machines
  strengthen a workload lead; they still do not identify a code defect.
- MCP returns the current records, rules and validated decisions. Existing finding
  and causal annotations cannot override raw checks. Raw-derived investigations
  use `raw/…` evidence references when no upstream finding exists. With no eligible
  evidence, the workflow returns a deterministic explanation and skips the model.

The existing cohort rules cover CPU-placement and low-activity interactive-session
trials, plus card imbalance and failure investigations. This is not exhaustive
discovery of every possible optimization. New workload types may need additional
rules and independent validation.

`claims.json` and `REPORT.md` are saved historical artifacts. The dashboard does
not read results from them. Download claims or run `make claims` to export the
active data; do not expect a report written for one dataset to describe another.
