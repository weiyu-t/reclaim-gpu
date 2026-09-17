"""Independent investigations: node/window controls and per-card accounting.

Observations are recomputed from parquet, not copied from detector verdicts.
These exposures are not added to the two policy recovery estimates.
"""
from functools import cached_property, lru_cache
import numpy as np
import pandas as pd
from .analysis import analysis, EPOCH_OFFSET, number


class Research:
    def __init__(self, a):
        self.a = a
        self.jobs = a.jobs
        self.gpus = a.gpus
        self.node_jobs = self.gpus.groupby("Node").id_job.agg(set).to_dict()

    def _stamp(self, text):
        return pd.Timestamp(text).timestamp() - EPOCH_OFFSET

    def _iso(self, offset):
        return pd.to_datetime(offset + EPOCH_OFFSET, unit="s", utc=True).isoformat()

    def _node_hours(self, node, job_ids):
        c = self.gpus[self.gpus.Node.eq(node) & self.gpus.id_job.isin(job_ids)]
        c = c.merge(self.jobs[["id_job", "walltime_sec", "attempts"]], on="id_job", validate="many_to_one")
        c = c[c.attempts.eq(1) & c.walltime_sec.gt(0)]
        return float(np.minimum(c.gpu_hours, c.walltime_sec / 3600).clip(lower=0).sum())

    @cached_property
    def hardware(self):
        finding = next(f for f in self.a.findings if f["detectorId"] == "rules::node-hardware-fault")
        m = finding["metadata"]
        node, status = m["node"], int(m["exit_status"])
        lo, hi = self._stamp(m["window_start"]), self._stamp(m["window_end"])
        w = self.jobs[self.jobs.time_end.ge(lo) & self.jobs.time_end.lt(hi)]
        on = w[w.id_job.isin(self.node_jobs[node]) & w.attempts.eq(1)]
        signature = on[on.state_name.eq("FAILED") & (on.exit_code // 256).eq(status)]
        controls = []
        for uid in sorted(signature.id_user.unique()):
            here = on[on.id_user.eq(uid)]
            elsewhere = w[w.id_user.eq(uid) & ~w.id_job.isin(self.node_jobs[node]) & w.attempts.eq(1)]
            controls.append({
                "user": f"u-{int(uid)}", "here_jobs": len(here),
                "here_signature": int((here.state_name.eq("FAILED") & (here.exit_code // 256).eq(status)).sum()),
                "elsewhere_jobs": len(elsewhere),
                "elsewhere_signature": int((elsewhere.state_name.eq("FAILED") & (elsewhere.exit_code // 256).eq(status)).sum()),
                "here_job_ids": [str(int(x)) for x in here.id_job],
                "elsewhere_job_ids": [str(int(x)) for x in elsewhere.id_job],
            })
        return {
            "node": node, "finding_id": finding["id"], "root_id": finding["rootCauses"][0],
            "start": self._iso(lo), "end": self._iso(hi), "hours": number((hi - lo) / 3600),
            "jobs": len(on), "failed": int(on.state_name.eq("FAILED").sum()),
            "exit_status": status, "signature_jobs": len(signature), "controls": controls,
            "elsewhere_jobs": sum(x["elsewhere_jobs"] for x in controls),
            "elsewhere_signature": sum(x["elsewhere_signature"] for x in controls),
            "signature_gpu_hours": number(self._node_hours(node, set(signature.id_job)), 6),
            "all_failed_gpu_hours": number(self._node_hours(node, set(on.loc[on.state_name.eq("FAILED"), "id_job"]))),
            "job_ids": [str(int(x)) for x in signature.id_job],
            "method": "Join gpus.id_job → jobs.id_job; distinct node/job placement; time_end within this episode; attempts = 1; exit_code // 256; compare the same researchers on other nodes in the same time window.",
            "limitation": "Strong machine-specific evidence, not a physical diagnosis. Shared software/environment and correlated jobs remain possible confounders. Only matching-signature hours enter the drain scenario.",
        }

    @cached_property
    def windows(self):
        out = []
        for f in self.a.findings:
            if f["detectorId"] != "rules::node-elevated-failure-rate":
                continue
            m = f["metadata"]
            # Displayed dates omit time-of-day. Recover the official consecutive
            # windows from the sample origin, not midnight on the display date.
            index = round((self._stamp(m["window_start"] + "T00:00:00Z") - self.a.s.t0) / (14 * 86400))
            lo, hi = self.a.s.t0 + index * 14 * 86400, self.a.s.t0 + (index + 1) * 14 * 86400
            w = self.jobs[self.jobs.time_end.ge(lo) & self.jobs.time_end.lt(hi)]
            on = w[w.id_job.isin(self.node_jobs[m["node"]])]
            failed = on[on.state_name.eq("FAILED")]
            uid = failed.id_user.value_counts().index[0]
            mine, others = on[on.id_user.eq(uid)], on[~on.id_user.eq(uid)]
            my_failed = mine[mine.state_name.eq("FAILED")]
            controls = {"dominant_user": f"u-{int(uid)}", "dominant_jobs": len(mine),
                        "dominant_failed": len(my_failed), "failure_share": number(len(my_failed) / len(failed), 4),
                        "others_jobs": len(others), "others_failed": int(others.state_name.eq("FAILED").sum()),
                        "others_completed": int(others.is_success.sum())}
            arrays = my_failed.loc[my_failed.is_array_task, "id_array_job"].value_counts()
            array_control = None
            if len(arrays):
                array_id = arrays.index[0]
                peers = w[w.id_array_job.eq(array_id) & ~w.id_job.isin(self.node_jobs[m["node"]]) & w.attempts.eq(1)]
                local = my_failed[my_failed.id_array_job.eq(array_id)]
                code = int(local.exit_code.value_counts().index[0])
                array_control = {"array": f"array/{int(array_id)}", "local_failed": len(local),
                                 "elsewhere_jobs": len(peers), "elsewhere_failed": int(peers.state_name.eq("FAILED").sum()),
                                 "matching_exit_elsewhere": int((peers.state_name.eq("FAILED") & peers.exit_code.eq(code)).sum()),
                                 "exit_code": code, "peer_job_ids": [str(int(x)) for x in peers.id_job]}
            hw_here = (m["node"] == self.hardware["node"] and lo <= self._stamp(self.hardware["start"]) < hi)
            user_support = bool(array_control and len(my_failed) / len(failed) >= .9
                                and array_control["local_failed"] / len(failed) >= .8
                                and array_control["elsewhere_jobs"] >= 10
                                and array_control["matching_exit_elsewhere"] / array_control["elsewhere_jobs"] >= .9
                                and not on.attempts.gt(1).any())
            cause = "hardware" if hw_here else "user_code" if user_support else "cannot_determine"
            if cause == "hardware":
                reason = (f"Joined gpus.Node/id_job to jobs.id_job/time_end/exit_code. In the enclosed episode, "
                          f"{self.hardware['signature_jobs']} FAILED jobs from {len(self.hardware['controls'])} researchers share exit status "
                          f"{self.hardware['exit_status']} here, versus {self.hardware['elsewhere_signature']}/{self.hardware['elsewhere_jobs']} "
                          "same-window jobs elsewhere for those researchers. This supports targeted hardware inspection; it does not attribute every failure to hardware.")
                decision, verdict = "Inspect this machine; decide the drain duration from the downside model.", "act"
            elif cause == "user_code":
                reason = (f"Joined gpus.Node/id_job to jobs.id_job/time_end/id_user/id_array_job/exit_code. "
                          f"One researcher owns {len(my_failed)}/{len(failed)} failures. Their array contributes "
                          f"{array_control['local_failed']} local failures; {array_control['matching_exit_elsewhere']}/{array_control['elsewhere_jobs']} "
                          f"same-window sibling jobs elsewhere fail with the same packed exit code {array_control['exit_code']}. "
                          f"Other researchers here have {controls['others_failed']}/{len(others)} FAILED jobs. "
                          "Investigate the shared workload/environment; this does not identify the exact code defect.")
                decision, verdict = "Investigate the shared array with its owner before draining this node.", "no_action"
            else:
                reason = (f"Joined gpus.Node/id_job to jobs.id_job/time_end/id_user/id_array_job. "
                          f"The window has {len(failed)}/{len(on)} FAILED jobs. The dominant researcher owns "
                          f"{len(my_failed)}/{len(failed)} failures; other researchers have {controls['others_failed']}/{len(others)} failures. "
                          "No matching hardware episode or sufficiently replicated same-array/exit-code control establishes cause. "
                          "Failure concentration alone cannot distinguish workload mix, user code and hardware. Collect controlled reruns and node diagnostics.")
                decision, verdict = "Monitor and collect controlled reruns; do not authorize a drain from this flag.", "monitor"
            out.append({"id": f["id"], "node": m["node"], "window": index,
                        "start": self._iso(lo), "end": self._iso(min(hi, self.jobs.time_end.max())),
                        "jobs": len(on), "failed": len(failed), "rate": number(len(failed)/len(on), 4),
                        "cluster_rate": m["cluster_rate_this_window"], "cause": cause, "reasoning": reason,
                        "explanation": reason.split(". ", 1)[1],
                        "decision": decision, "verdict": verdict, "controls": controls, "array_control": array_control,
                        "requeued_jobs": int(on.attempts.gt(1).sum()),
                        "detector_counts_match": len(on) == m["jobs"] and len(failed) == m["failed"],
                        "job_ids": [str(int(x)) for x in on.id_job],
                        "examples": self.a.job_rows(on, limit=8)["rows"]})
        return out

    @cached_property
    def cases(self):
        hardware = next(x for x in self.windows if x["cause"] == "hardware" and x["detector_counts_match"])
        user = max((x for x in self.windows if x["cause"] == "user_code" and x["detector_counts_match"]),
                   key=lambda x: x["array_control"]["matching_exit_elsewhere"])
        ambiguous = next((x for x in self.windows if x["node"] == hardware["node"] and x["cause"] == "cannot_determine" and x["detector_counts_match"]),
                         next(x for x in self.windows if x["cause"] == "cannot_determine" and x["detector_counts_match"]))
        return [hardware, user, ambiguous]

    def node_audit(self, price=2.5):
        from api.main import underperforming, recommendations, causal
        from api.models import CausalRequest
        ranked = underperforming(entity_type="node", limit=5, usd_per_gpu_hour=price).model_dump()
        rec = next(x for x in recommendations(usd_per_gpu_hour=price).model_dump()["recommendations"] if x["id"] == "rec_drain_nodes")
        return {"hardware": self.hardware, "cases": self.cases,
                "case_count": len(self.cases), "flagged_windows": len(self.windows),
                "baseline": {"nodes": ranked["rows"], "recommendation": rec,
                             "includes_hardware_node": self.hardware["node"] in {x["entity_id"] for x in ranked["rows"]},
                             "audit": "The proposed endpoint ranks finding counts and sums mixed, overlapping impacts. It does not check root causes. Its savings estimate and fixed confidence are not validated treatment effects. Absence of a hardware finding does not establish that its five selected nodes are healthy."},
                "causal": causal(CausalRequest(finding_id=self.hardware["finding_id"])).model_dump(),
                "history": self.hardware_history(),
                "method": "Three selected, reproducible case studies. Node/window totals use time_end and unique GPU node/job placement. Window indices start at the sample's exact t0 and span 14 days. These are not predictions or a validation set for all nodes."}

    def hardware_history(self):
        j = self.jobs
        recorded = j[j.hit_node_failure]
        return {"jobs": len(recorded), "attempts": int(recorded.nodefail_attempts.sum()),
                "terminal_node_fail": int(j.state_name.eq("NODE_FAIL").sum()),
                "recovered_or_other_outcome": int((~recorded.state_name.eq("NODE_FAIL")).sum()),
                "basis": "Distinct GPU jobs with hit_node_failure, reconciled to nodefail_attempts from the scheduler requeue history. This is a scheduler-recorded count, not an estimate of all hardware failures. Failed-attempt nodefail_nodes are used for placement; a retry's final node is not blamed."}

    def drain(self, price=2.5, duration=4., recurrence=.5, operator_hours=1., nodes=1):
        h = self.hardware
        exposed = h["signature_gpu_hours"]
        avoided = exposed * recurrence
        unavailable = nodes * 2 * duration
        labor = operator_hours * 95
        return {"inputs": {"duration": duration, "recurrence": recurrence, "operator_hours": operator_hours, "nodes": nodes, "price": price},
                "reference_episode_hours": h["hours"], "observed_signature_gpu_hours": exposed,
                "avoided_gpu_hours": number(avoided), "unavailable_gpu_hours": number(unavailable),
                "avoided_value_usd": number(avoided * price), "capacity_cost_usd": number(unavailable * price),
                "operator_cost_usd": number(labor), "net_value_usd": number((avoided-unavailable)*price-labor),
                "break_even_drain_hours": number(max(0, (avoided * price - labor)/(nodes*2*price)), 4),
                "cannot_break_even_even_at_zero_drain": avoided*price < labor,
                "caveat": "Assume one recurrence of the observed episode and the selected fraction of signature losses preventable. This is not a forecast or hardware-fault probability. Drain cost values every unavailable slot at the reference rate, even if unoccupied; it is capacity cost, not proved cash or displaced work. Jobs need checkpointing; repair success, queue effects, lost research value and transition timing are unmeasured."}

    @cached_property
    def card_data(self):
        j, g = self.jobs, self.gpus
        spread = g.groupby("id_job").smutilization_pct_avg.agg(["min", "max", "size"])
        ids = spread.index[(spread["max"] >= 20) & ((spread["max"]-spread["min"]) > 30) & (spread["size"] >= 2)]
        jobs = j[j.id_job.isin(ids) & j.walltime_sec.gt(3600) & j.attempts.eq(1) & j.is_success]
        cards = g[g.id_job.isin(jobs.id_job)].merge(jobs[["id_job", "walltime_sec"]], on="id_job", validate="many_to_one")
        cards["capped_hours"] = np.minimum(cards.gpu_hours, cards.walltime_sec/3600).clip(lower=0)
        average_zero = cards[cards.smutilization_pct_avg.eq(0)]
        peak_zero = average_zero[average_zero.smutilization_pct_max.eq(0)]
        small_memory = peak_zero[peak_zero.mem_used_frac.le(.01)]
        return {"jobs": jobs, "cards": cards, "average_zero": average_zero,
                "peak_zero": peak_zero, "small_memory": small_memory}

    def cards(self, price=2.5, offset=0, limit=20):
        d = self.card_data
        scenarios = []
        for key, label in [("small_memory", "Zero compute peak + ≤1% peak memory"), ("peak_zero", "Zero average and peak compute"), ("average_zero", "Zero average compute only")]:
            c = d[key]
            hours = float(c.capped_hours.sum())
            scenarios.append({"id": key, "label": label, "jobs": int(c.id_job.nunique()), "cards": len(c),
                              "gpu_hours": number(hours), "value_usd": number(hours*price)})
        c = d["peak_zero"]
        eligible = set(c.id_job)
        exposure = c.groupby("id_job").capped_hours.sum().sort_values(ascending=False)
        examples = []
        for jid in exposure.index[offset:offset+limit]:
            row = self.jobs[self.jobs.id_job.eq(jid)].iloc[0]
            cards = d["cards"][d["cards"].id_job.eq(jid)]
            examples.append({"id": str(int(jid)), "job_avg_sm": number(row.sm_util_avg),
                             "state": row.state_name, "quiet_gpu_hours": number(exposure[jid]),
                             "cards": [{"node": r.Node, "gpu_id": int(r.gpu_id), "avg_sm": number(r.smutilization_pct_avg),
                                        "peak_sm": number(r.smutilization_pct_max), "memory_pct": number(r.mem_used_frac*100),
                                        "pcie_mbps": number(r.pcierxbandwidth_megabytes_avg+r.pcietxbandwidth_megabytes_avg),
                                        "capped_hours": number(r.capped_hours), "selected": r.smutilization_pct_avg == 0 and r.smutilization_pct_max == 0}
                                       for r in cards.itertuples()]})
        overlaps = eligible & set().union(*(set(x.id_job) for x in self.a.cohorts.values()))
        return {"thresholds": scenarios, "point": scenarios[1], "total": len(exposure), "offset": offset, "limit": limit,
                "examples": examples, "existing_plan_overlap_jobs": len(overlaps),
                "memory_above_one_percent_cards": int(c.mem_used_frac.gt(.01).sum()),
                "quiet_card_index": {str(int(k)): int(v) for k,v in c.gpu_id.value_counts().items()},
                "index_caveat": "Card index is an observed placement association; device numbering does not identify a defective GPU. Use (Node, gpu_id, id_job), not gpu_id alone.",
                "pilot": "Workload owners should audit device binding, memory residency and communication; replay with fewer cards and verify output parity and runtime before changing defaults.",
                "limitation": "These are observed quiet-card exposure thresholds, not recovery rates. Zero compute can coexist with useful memory or transfers. Memory is a peak measurement; coarse/censored PCIe counters do not establish sustained useful traffic. No card hours are added to the recovery headline until a right-sizing pilot establishes feasibility.",
                "method": "Per (Node, gpu_id, id_job), recompute busiest-minus-quietest average SM >30 points and busiest ≥20%; job COMPLETED, walltime >1h, attempts=1. Point exposure: card average AND peak SM =0. Clip each card's hours to job walltime. Bounds vary peak and memory evidence, not a statistical confidence interval."}

    def claims(self):
        cards = self.cards(limit=0)
        levels = cards["thresholds"]
        history = self.hardware_history()
        return {"node_triage": [{k: c[k] for k in ("node", "window", "cause", "reasoning", "verdict")} for c in self.cases],
                "hardware_attributable_failures": history["jobs"],
                "hardware_attributable_rationale": history["basis"] + f" {history['jobs']} jobs experienced {history['attempts']} recorded failed attempts; only {history['terminal_node_fail']} end in NODE_FAIL. The separate SIGBUS episode is investigated but not added to this scheduler-only count.",
                "card_imbalance_gpu_hours": {"point": levels[1]["gpu_hours"], "low": levels[0]["gpu_hours"], "high": levels[2]["gpu_hours"],
                                             "interval_kind": "scenario", "basis": cards["method"] + " Bounds represent measured exposure under different evidence thresholds, not recovered time. Excluded from recoverable_gpu_hours."},
                "card_imbalance_rationale": cards["limitation"] + " " + cards["pilot"],
                "card_imbalance_index_reasoning": f"Selected quiet-card rows by local gpu_id: {cards['quiet_card_index']}. " + cards["index_caveat"]}


@lru_cache(maxsize=1)
def research():
    return Research(analysis())
