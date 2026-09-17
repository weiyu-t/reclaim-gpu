"""Auditable accounting. No model computes a displayed number."""
from __future__ import annotations
from collections import defaultdict
from functools import lru_cache
import json
import math
import os
import numpy as np
import pandas as pd
from api.data_loader import ROOT, store

EPOCH_OFFSET = 1750862959
DEFAULT_PRICE = 2.5
POLICY_VERSION = "reclaim-v2"


def number(value, digits=2):
    value = float(value)
    return round(value, digits) if math.isfinite(value) else 0.0


def bounds(hours, fractions):
    low, point, high = [number(hours * f) for f in fractions]
    return {"low": low, "point": point, "high": high, "interval_kind": "scenario"}


class Analysis:
    def __init__(self):
        self.s = store()
        self.jobs = self.s.jobs.copy()
        self.gpus = pd.read_parquet(ROOT / "data/prepped/gpus.parquet")
        self.findings = self.s.findings
        self.by_job = defaultdict(list)
        for f in self.findings:
            jid = f.get("metadata", {}).get("job_id")
            if jid is not None:
                self.by_job[int(jid)].append(f)
        self.by_finding = {f["id"]: f for f in self.findings}
        j = self.jobs
        reliable = (
            j.walltime_sec.gt(0) & j.gpu_hours.ge(0) & j.gpu_count.gt(0)
            & j.attempts.eq(1) & np.isfinite(j.gpu_hours_alloc)
            & j.sm_util_avg.notna() & j.sm_util_max.notna()
        )
        cpu_signal = (
            j.state_name.eq("COMPLETED") & j.sm_util_avg.eq(0)
            & j.sm_util_max.eq(0) & j.gpu_hours.gt(1)
        )
        idle_signal = (
            j.job_type.eq("LLSUB:INTERACTIVE") & j.walltime_sec.gt(4 * 3600)
            & j.sm_util_avg.lt(5)
        )
        self.cohorts = {
            "cpu-placement": j[reliable & cpu_signal].copy(),
            "idle-sessions": j[reliable & idle_signal & ~cpu_signal].copy(),
        }
        self.excluded = int(((cpu_signal | idle_signal) & ~reliable).sum())
        self.overlap = int((reliable & cpu_signal & idle_signal).sum())
        for key, frame in self.cohorts.items():
            cap = np.minimum(frame.gpu_hours, frame.gpu_hours_alloc).clip(lower=0)
            if key == "idle-sessions":
                cap = (cap - frame.gpu_count * 4).clip(lower=0)
            frame["eligible_gpu_hours"] = cap
            frame["action_id"] = key

    def actions(self, price=DEFAULT_PRICE):
        definitions = [
            {
                "id": "cpu-placement", "title": "Give CPU work a CPU home",
                "short_title": "CPU placement", "tag": "Placement",
                "owner": "Research platform",
                "description": "Successful jobs held GPUs without recording any GPU compute. Pilot CPU placement for repeat runs.",
                "detector_id": "rules::gpu-not-needed", "fractions": (0.5, 0.75, 0.95),
                "evidence_strength": "Strong placement signal",
                "risk_level": "Lower intervention risk",
                "formula": "COMPLETED AND sm_util_avg = 0 AND sm_util_max = 0 AND gpu_hours > 1 AND attempts = 1",
                "savings_basis": "50% / 75% / 95% of capped GPU-hours become available after CPU placement. These are adoption and feasibility scenarios, not measured treatment effects.",
                "downside": "A repeat run may need GPU libraries, unobserved GPU activity, or scarce CPU capacity. A failed migration creates rework and delay.",
                "pilot": "Opt in a small repeat-workload cohort; verify output parity and CPU runtime before changing its default queue.",
                "rollback": "Restore GPU placement if output parity fails, CPU runtime worsens materially, or CPU queue delay increases.",
            },
            {
                "id": "idle-sessions", "title": "Put an end to forgotten sessions",
                "short_title": "Idle-session policy", "tag": "Scheduling",
                "owner": "Scheduler operations",
                "description": "Long interactive allocations recorded little GPU activity. Start with warnings and opt-in expiry.",
                "detector_id": "rules::idle-interactive-session", "fractions": (0.10, 0.25, 0.45),
                "evidence_strength": "Activity signal; timing unknown",
                "risk_level": "Pilot before enforcement",
                "formula": "INTERACTIVE AND walltime > 4h AND sm_util_avg < 5% AND attempts = 1, excluding CPU-placement jobs",
                "savings_basis": "10% / 25% / 45% of capped hours beyond a four-hour grace period. Job averages do not locate continuous idle periods; recovery is a policy scenario.",
                "downside": "Low GPU activity may be legitimate CPU preprocessing or interactive research. Expiry could interrupt useful work and require a rerun.",
                "pilot": "Run warning-only mode, collect opt-in responses, and measure continuous idleness before enabling any timeout.",
                "rollback": "Keep expiry disabled until the pilot measures false positives; restore allocations if useful sessions are interrupted.",
            },
        ]
        out = []
        for d in definitions:
            c = self.cohorts[d["id"]]
            hours, raw_hours = float(c.eligible_gpu_hours.sum()), float(c.gpu_hours.sum())
            estimate = bounds(hours, d.pop("fractions"))
            ids = set(c.id_job.astype(int))
            finding_ids = [
                f["id"] for f in self.findings if f["detectorId"] == d["detector_id"]
                and f.get("metadata", {}).get("job_id") in ids
            ]
            out.append({
                **d, "job_count": len(c), "observed_gpu_hours": number(raw_hours),
                "eligible_gpu_hours": number(hours), "recovery": estimate,
                "value": {k: number(estimate[k] * price) for k in ("low", "point", "high")},
                "share_of_sample": number(100 * estimate["point"] / self.s.allocated),
                "weighted_util_pct": number((c.gpu_hours * c.sm_util_avg).sum() / raw_hours) if raw_hours else 0,
                "finding_count": len(finding_ids), "finding_ids": finding_ids,
                "completed_jobs": int(c.state_name.eq("COMPLETED").sum()),
                "cancelled_jobs": int(c.state_name.eq("CANCELLED").sum()),
                "max_rework_gpu_hours": number(raw_hours),
            })
        return out

    def overview(self, price=DEFAULT_PRICE):
        s, j = self.s, self.jobs
        actions = self.actions(price)
        estimate = {k: number(sum(a["recovery"][k] for a in actions)) for k in ("low", "point", "high")}
        spend = []
        labels = {"COMPLETED": "Completed", "CANCELLED": "Cancelled", "TIMEOUT": "Timed out",
                  "FAILED": "Failed", "NODE_FAIL": "Node failure"}
        for state, frame in j.groupby("state_name"):
            hours = float(frame.gpu_hours.sum())
            spend.append({
                "state": state, "label": labels.get(state, "Undecoded"),
                "gpu_hours": number(hours), "usd": number(hours * price),
                "share": hours / s.allocated, "jobs": len(frame),
            })
        spend.sort(key=lambda x: -x["gpu_hours"])
        dates = pd.to_datetime(j.time_start + EPOCH_OFFSET, unit="s", utc=True)
        weekly = []
        for name, frame in j.groupby(dates.dt.strftime("%G-W%V")):
            weekly.append({
                "week": name, "gpu_hours": number(frame.gpu_hours.sum()),
                "completed": number(frame.loc[frame.is_success, "gpu_hours"].sum()),
                "cancelled": number(frame.loc[frame.state_name.eq("CANCELLED"), "gpu_hours"].sum()),
                "other": number(frame.loc[~frame.is_success & ~frame.state_name.eq("CANCELLED"), "gpu_hours"].sum()),
            })
        all_claimed = sum((f.get("metadata", {}).get("impact_gpu_hours") or 0) for f in self.findings)
        flagged_ids = {
            int(f["metadata"]["job_id"]) for f in self.findings
            if f.get("metadata", {}).get("impact_scope") == "job"
            and f.get("metadata", {}).get("job_id") is not None
        }
        return {
            "product": "Reclaim", "policy_version": POLICY_VERSION,
            "window": {
                "start": pd.to_datetime(s.t0 + EPOCH_OFFSET, unit="s", utc=True).strftime("%b %d, %Y"),
                "end": pd.to_datetime(s.t1 + EPOCH_OFFSET, unit="s", utc=True).strftime("%b %d, %Y"),
            },
            "sample": {"jobs": len(j), "nodes": int(self.gpus.Node.nunique()),
                       "researchers": int(j.id_user.nunique()), "gpu_hours": number(s.allocated)},
            "price": {"usd_per_gpu_hour": price, "usd_per_engineer_hour": 95,
                      "version": "2026-Q3" if price == DEFAULT_PRICE else "2026-Q3+custom"},
            "spend_usd": number(s.allocated * price),
            "completed_compute_proxy_share": s.computed_completed / s.allocated,
            "target": {"percent": 20, "gpu_hours": number(s.allocated * .2),
                       "value_usd": number(s.allocated * .2 * price)},
            "recovery": {**estimate, "interval_kind": "scenario",
                         "value": {k: number(v * price) for k, v in estimate.items()},
                         "share_percent": number(100 * estimate["point"] / s.allocated),
                         "target_coverage_percent": number(100 * estimate["point"] / (s.allocated * .2)),
                         "target_gap_usd": number(max(0, (s.allocated * .2 - estimate["point"]) * price))},
            "spend": spend, "weekly": weekly, "actions": actions,
            "default_risk": self.scenario(price),
            "accounting": {
                "naive_finding_hours": number(all_claimed),
                "unique_flagged_hours": number(j.loc[j.id_job.isin(flagged_ids), "gpu_hours"].sum()),
                "overlap_removed_jobs": self.overlap, "excluded_ambiguous_jobs": self.excluded,
                "synthetic_findings": sum(bool(f.get("metadata", {}).get("synthetic")) for f in self.findings),
                "findings": len(self.findings),
            },
            "caveat": "Historical workload sample, not whole-fleet utilization or a next-quarter forecast. Recovery ranges are scenarios; cash savings require a reducible bill. Low SM utilization alone does not prove waste.",
        }

    def job_rows(self, frame, offset=0, limit=50, price=DEFAULT_PRICE):
        frame = frame.sort_values("gpu_hours", ascending=False)
        rows = []
        for r in frame.iloc[offset:offset + limit].itertuples():
            rows.append({
                "id": str(int(r.id_job)), "state": r.state_name,
                "gpus": int(r.gpu_count), "gpu_hours": number(r.gpu_hours),
                "usd": number(r.gpu_hours * price),
                "avg_util": number(r.sm_util_avg), "peak_util": number(r.sm_util_max),
                "wall_hours": number(r.walltime_sec / 3600),
                "eligible_gpu_hours": number(getattr(r, "eligible_gpu_hours", 0)),
                "attempts": int(r.attempts), "type": str(r.job_type),
                "finding_ids": [f["id"] for f in self.by_job[int(r.id_job)]],
            })
        return {"total": len(frame), "offset": offset, "limit": limit, "rows": rows}

    def evidence(self, action_id, price=DEFAULT_PRICE, offset=0, limit=50):
        action = next((a for a in self.actions(price) if a["id"] == action_id), None)
        if action is None:
            raise KeyError(action_id)
        selected = sorted(
            (self.by_finding[fid] for fid in action["finding_ids"]),
            key=lambda f: f.get("metadata", {}).get("impact_gpu_hours") or 0, reverse=True,
        )[:6]
        return {
            "action": action, "jobs": self.job_rows(self.cohorts[action_id], offset, limit, price),
            "findings": selected,
            "method": {
                "source": "data/prepped/jobs.parquet", "grain": "One job; GPU-hours measured by DCGM",
                "filter": action["formula"],
                "duration_cap": "min(gpu_hours, gpu_count × walltime_sec / 3600); discard ambiguous requeues.",
                "deduplication": "CPU-placement jobs take precedence and are removed from idle-session policy.",
                "scope": "The four-month observed sample. No extrapolation to unobserved idle fleet capacity.",
            },
        }

    def raw_job(self, job_id):
        frame = self.jobs[self.jobs.id_job.eq(int(job_id))]
        if frame.empty:
            raise KeyError(job_id)
        cards = self.gpus[self.gpus.id_job.eq(int(job_id))]
        return {
            "job": json.loads(frame.to_json(orient="records"))[0],
            "gpus": json.loads(cards.to_json(orient="records")),
            "findings": self.by_job[int(job_id)],
            "source": "data/prepped/jobs.parquet + data/prepped/gpus.parquet",
        }

    def causal_case(self):
        arrays = [f for f in self.findings if f["detectorId"] == "rules::array-mass-failure"
                  and f.get("rootCauses") and not f.get("metadata", {}).get("synthetic")]
        if not arrays:
            return None
        tasks_by_root = defaultdict(list)
        for f in self.findings:
            if f["detectorId"] == "rules::array-task-failure":
                for root in f.get("rootCauses", []):
                    tasks_by_root[root].append(f)
        chosen = max(arrays, key=lambda f: len(tasks_by_root[f["rootCauses"][0]]))
        root = chosen["rootCauses"][0]
        tasks = tasks_by_root[root]
        ids = {int(f["metadata"]["job_id"]) for f in tasks if f.get("metadata", {}).get("job_id")}
        raw = self.jobs[self.jobs.id_job.isin(ids)]
        cards = self.gpus[self.gpus.id_job.isin(ids)]
        node_counts = cards.groupby("Node").id_job.nunique().sort_values(ascending=False)
        return {
            "finding_id": chosen["id"], "root_id": root,
            "root_name": self.s.name_of.get(root, root), "tasks": len(raw),
            "nodes": int(cards.Node.nunique()), "gpu_hours": number(raw.gpu_hours.sum()),
            "node_counts": [{"node": k, "jobs": int(v)} for k, v in node_counts.head(8).items()],
            "exit_codes": {str(k): int(v) for k, v in raw.exit_code.value_counts().items()},
            "jobs": self.job_rows(raw, limit=8), "synthetic": False,
            "decision": "Inspect the shared array and its workload before draining machines.",
            "limitation": "Dispersion and a shared exit code support workload triage; they do not prove every machine healthy.",
        }

    def scenario(self, price=DEFAULT_PRICE, recovery=1., false_positive=.02,
                 cash_realization=0., engineer_hours_per_job=.5, engineer_rate=95.):
        actions = self.actions(price)
        gross = sum(a["recovery"]["point"] for a in actions) * recovery
        count = sum(a["job_count"] for a in actions)
        rerun = sum(a["max_rework_gpu_hours"] for a in actions) * false_positive
        eng_hours = count * false_positive * engineer_hours_per_job
        downside = rerun * price + eng_hours * engineer_rate
        denominator = sum(a["max_rework_gpu_hours"] for a in actions) * price + count * engineer_hours_per_job * engineer_rate
        return {
            "kind": "scenario",
            "inputs": {"recovery": recovery, "false_positive": false_positive,
                       "cash_realization": cash_realization, "price": price,
                       "engineer_hours_per_job": engineer_hours_per_job, "engineer_rate": engineer_rate},
            "recovered_gpu_hours": number(gross), "capacity_value_usd": number(gross * price),
            "rerun_gpu_hours": number(rerun), "engineer_hours": number(eng_hours),
            "downside_usd": number(downside),
            "net_capacity_value_usd": number(gross * price - downside),
            "gross_bill_reduction_usd": number(gross * price * cash_realization),
            "net_bill_value_usd": number(gross * price * cash_realization - downside),
            "affected_jobs_equivalent": number(count * false_positive),
            "break_even_false_positive": number(gross * price / denominator, 5) if denominator else 0,
            "caveat": "Assumed uniform false-positive rate and full-duration rerun cost. Rework uses reference GPU and salary rates, not incremental invoices. Queue delay, CPU migration cost, and research value are unmeasured. No cash savings are established at 0% bill reduction.",
        }

    def claims(self, price=DEFAULT_PRICE):
        from .research import research
        overview = self.overview(price)
        rec = overview["recovery"]
        basis = " ".join(
            f"{a['id']}: {a['job_count']} jobs; {a['eligible_gpu_hours']} capped eligible GPU-hours. {a['savings_basis']}"
            for a in overview["actions"]
        )
        return {
            "team": os.environ.get("TEAM_NAME", "Reclaim"),
            **research().claims(),
            "recoverable_gpu_hours": {
                **{k: rec[k] for k in ("point", "low", "high")}, "interval_kind": "scenario",
                "basis": basis + " CPU cohort owns overlaps. Excludes requeues. No causal recovery rate has been measured; actual recovery may be zero.",
            },
            "recoverable_usd": {
                **rec["value"], "interval_kind": "scenario",
                "basis": f"Capacity-equivalent value at USD {price}/GPU-hour for the observed sample, not demonstrated cash savings or a forecast.",
            },
            "cancelled_is_waste": False,
            "cancelled_rationale": "Cancellation alone is not waste. Selected cancelled interactive sessions enter only the explicit long-duration/low-activity policy scenario; no blanket cancellation savings are claimed.",
            "zero_recovery_stress": {
                "recoverable_gpu_hours": 0, "capacity_value_usd": 0,
                "net_capacity_value_usd": self.scenario(price, recovery=0)["net_capacity_value_usd"],
                "basis": "No realized recovery, with the default 2% disruption and 0.5 operator hours per affected job. The low recovery scenario is not a guarantee or a lower confidence bound.",
            },
            "notes": "Intervals are assumption scenarios, not statistical confidence intervals. No calibrated probability is claimed for intervention success. All savings use real telemetry; the synthetic storage incident is excluded. Policy " + POLICY_VERSION,
        }


@lru_cache(maxsize=1)
def analysis():
    return Analysis()
