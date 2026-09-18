"""Raw-record investigations. Findings nominate candidates; they do not decide causes."""
from functools import cached_property, lru_cache
import math
import numpy as np
import pandas as pd
from scipy.stats import binomtest
from .analysis import analysis, number


class Research:
    def __init__(self, a):
        self.a, self.jobs, self.gpus = a, a.jobs, a.gpus
        self.node_jobs = self.gpus.groupby("Node").id_job.agg(set).to_dict()

    def _stamp(self, text):
        return pd.Timestamp(text).timestamp() - self.a.epoch_offset

    def _iso(self, offset):
        return pd.to_datetime(offset + self.a.epoch_offset, unit="s", utc=True).isoformat()

    def _node_hours(self, node, job_ids):
        c = self.gpus[self.gpus.Node.eq(node) & self.gpus.id_job.isin(job_ids)]
        c = c.merge(self.jobs[["id_job", "walltime_sec", "attempts"]], on="id_job", validate="many_to_one")
        c = c[c.attempts.eq(1) & c.walltime_sec.gt(0)]
        return float(np.minimum(c.gpu_hours, c.walltime_sec / 3600).clip(lower=0).sum())

    def _episode(self, node, lo, hi, status, finding=None):
        w = self.jobs[self.jobs.time_end.ge(lo) & self.jobs.time_end.lt(hi)]
        local_ids = self.node_jobs.get(node, set())
        on = w[w.id_job.isin(local_ids) & w.attempts.eq(1)]
        signature = on[on.state_name.eq("FAILED") & (on.exit_code // 256).eq(status)]
        controls = []
        for uid in sorted(signature.id_user.dropna().unique()):
            here = on[on.id_user.eq(uid)]
            elsewhere = w[w.id_user.eq(uid) & ~w.id_job.isin(local_ids) & w.attempts.eq(1)]
            controls.append({
                "user": f"u-{int(uid)}", "here_jobs": len(here),
                "here_signature": int((here.state_name.eq("FAILED") & (here.exit_code // 256).eq(status)).sum()),
                "elsewhere_jobs": len(elsewhere),
                "elsewhere_signature": int((elsewhere.state_name.eq("FAILED") & (elsewhere.exit_code // 256).eq(status)).sum()),
                "here_job_ids": [str(int(x)) for x in here.id_job],
                "elsewhere_job_ids": [str(int(x)) for x in elsewhere.id_job],
            })
        supported_users = [c for c in controls if c["here_signature"] >= 2
                           and c["here_signature"] / c["here_jobs"] >= .5
                           and c["elsewhere_jobs"] >= 5
                           and c["elsewhere_signature"] / c["elsewhere_jobs"] <= .05]
        supported = status > 0 and len(supported_users) >= 3
        return {
            "node": node, "finding_id": finding["id"] if finding else None,
            "evidence_id": finding["id"] if finding else f"raw/node/{node}/{lo:g}/{status}",
            "root_id": (finding.get("rootCauses") or [None])[0] if finding else None,
            "supported": supported, "supported_users": len(supported_users),
            "start": self._iso(lo), "end": self._iso(hi), "hours": number((hi-lo)/3600),
            "jobs": len(on), "failed": int(on.state_name.eq("FAILED").sum()),
            "exit_status": status, "signature_jobs": len(signature), "controls": controls,
            "elsewhere_jobs": sum(c["elsewhere_jobs"] for c in controls),
            "elsewhere_signature": sum(c["elsewhere_signature"] for c in controls),
            "signature_gpu_hours": number(self._node_hours(node, set(signature.id_job)), 6),
            "job_ids": [str(int(x)) for x in signature.id_job],
            "all_failed_gpu_hours": number(self._node_hours(node, set(on.loc[on.state_name.eq("FAILED"), "id_job"]))),
            "method": "Join node/job placement to jobs; same-window, same-researcher controls; single attempts; packed exit_code // 256. Require at least three researchers, each with >=2 matching failures, >=50% local signature rate, >=5 elsewhere jobs and <=5% elsewhere signature rate. These are screening thresholds, not calibrated probabilities.",
            "limitation": ("Machine-specific evidence supports inspection, not a physical diagnosis. Shared environment and correlated jobs remain possible confounders."
                           if supported else "Raw records do not meet the machine-specific evidence thresholds. Do not authorize a hardware intervention from this finding."),
        }

    @cached_property
    def supplied_episodes(self):
        episodes = []
        self.invalid_hardware_findings = []
        for f in self.a.findings:
            if f["detectorId"] != "rules::node-hardware-fault" or f.get("metadata", {}).get("synthetic"):
                continue
            try:
                m = f["metadata"]
                lo, hi = self._stamp(m["window_start"]), self._stamp(m["window_end"])
                if not math.isfinite(lo + hi) or hi <= lo:
                    raise ValueError("Invalid episode dates")
                episodes.append(self._episode(m["node"], lo, hi, int(m["exit_status"]), f))
            except (KeyError, TypeError, ValueError, OverflowError):
                self.invalid_hardware_findings.append(f["id"])
        return episodes

    @cached_property
    def window_candidates(self):
        """Recompute the documented elevated-rate screen, including when findings are absent."""
        if self.jobs.empty:
            return []
        span = 14 * 86400
        placed = self.gpus[["Node", "id_job"]].drop_duplicates().merge(self.jobs, on="id_job", validate="many_to_one")
        indices = ((self.jobs.time_end - self.a.s.t0) // span).astype(int)
        placed["window"] = ((placed.time_end - self.a.s.t0) // span).astype(int)
        supplied = {}
        for f in self.a.findings:
            if f["detectorId"] != "rules::node-elevated-failure-rate" or f.get("metadata", {}).get("synthetic"):
                continue
            try:
                m = f["metadata"]
                index = round((self._stamp(m["window_start"]) - self.a.s.t0) / span)
                supplied[(m["node"], index)] = f
            except (KeyError, TypeError, ValueError, OverflowError):
                continue
        out = []
        for index, w in self.jobs.groupby(indices):
            lo, hi = self.a.s.t0 + int(index)*span, self.a.s.t0 + (int(index)+1)*span
            rate = float(w.state_name.eq("FAILED").mean())
            for node, on in placed[placed.window.eq(index)].groupby("Node"):
                failed = int(on.state_name.eq("FAILED").sum())
                elevated = bool(len(w) >= 100 and len(on) >= 30 and binomtest(failed, len(on), rate, alternative="greater").pvalue < .01)
                f = supplied.get((node, int(index)))
                if elevated or f:
                    out.append({"node": node, "index": int(index), "lo": lo, "hi": hi, "w": w, "on": on,
                                "cluster_rate": rate, "finding": f, "elevated": elevated})
        return out

    @cached_property
    def episodes(self):
        episodes = list(self.supplied_episodes)
        # A supplied finding may be missing or stale. Search raw windows as well.
        for candidate in self.window_candidates:
            node, lo, hi = candidate["node"], candidate["lo"], candidate["hi"]
            on = candidate["on"]
            failed = on[on.state_name.eq("FAILED") & on.attempts.eq(1)]
            for status, count in (failed.exit_code // 256).value_counts().items():
                if status <= 0 or count < 6:
                    continue
                if any(e["supported"] and e["node"] == node and e["exit_status"] == status
                       and lo <= self._stamp(e["start"]) < hi for e in episodes):
                    continue
                e = self._episode(node, lo, min(hi, float(np.nextafter(self.a.s.t1, np.inf))), int(status))
                if e["supported"]:
                    episodes.append(e)
        return sorted(episodes, key=lambda e: (not e["supported"], -e["signature_jobs"], e["node"], e["start"]))

    @cached_property
    def hardware(self):
        return next((e for e in self.episodes if e["supported"]), None)

    @cached_property
    def windows(self):
        out = []
        for item in self.window_candidates:
            node, index, lo, hi = item["node"], item["index"], item["lo"], item["hi"]
            on, w, f = item["on"], item["w"], item["finding"]
            failed = on[on.state_name.eq("FAILED")]
            users = failed.id_user.dropna().value_counts()
            uid = users.index[0] if len(users) else None
            mine = on[on.id_user.eq(uid)] if uid is not None else on.iloc[:0]
            others = on[~on.id_job.isin(mine.id_job)]
            my_failed = mine[mine.state_name.eq("FAILED")]
            controls = {"dominant_user": f"u-{int(uid)}" if uid is not None else None,
                        "dominant_jobs": len(mine), "dominant_failed": len(my_failed),
                        "failure_share": number(len(my_failed)/len(failed), 4) if len(failed) else 0,
                        "others_jobs": len(others), "others_failed": int(others.state_name.eq("FAILED").sum()),
                        "others_completed": int(others.is_success.sum())}
            arrays = my_failed.loc[my_failed.is_array_task, "id_array_job"].value_counts()
            array_control = None
            if len(arrays):
                array_id = arrays.index[0]
                peers = w[w.id_array_job.eq(array_id) & w.id_user.eq(uid) & w.is_array_task
                          & ~w.id_job.isin(self.node_jobs.get(node, set())) & w.attempts.eq(1)]
                local = my_failed[my_failed.id_array_job.eq(array_id)]
                code = int(local.exit_code.value_counts().index[0])
                array_control = {"array": f"array/{int(array_id)}", "local_failed": len(local),
                                 "elsewhere_jobs": len(peers), "elsewhere_failed": int(peers.state_name.eq("FAILED").sum()),
                                 "matching_exit_elsewhere": int((peers.state_name.eq("FAILED") & peers.exit_code.eq(code)).sum()),
                                 "exit_code": code, "peer_job_ids": [str(int(x)) for x in peers.id_job]}
            h = next((e for e in self.episodes if e["supported"] and e["node"] == node
                      and lo <= self._stamp(e["start"]) < hi), None)
            user_support = bool(len(failed) and array_control and array_control["exit_code"] != 0
                                and len(my_failed)/len(failed) >= .9 and array_control["local_failed"]/len(failed) >= .8
                                and array_control["elsewhere_jobs"] >= 10
                                and array_control["matching_exit_elsewhere"]/array_control["elsewhere_jobs"] >= .9
                                and not on.attempts.gt(1).any())
            cause = "hardware" if h else "user_code" if user_support else "cannot_determine"
            if h:
                reason = (f"Joined node/job records and same-window exit codes. {h['signature_jobs']} matching failures from "
                          f"{len(h['controls'])} researchers here, versus {h['elsewhere_signature']}/{h['elsewhere_jobs']} jobs elsewhere. "
                          "The raw controls meet the stated inspection thresholds; this does not identify a physical defect.")
                decision, verdict = "Inspect this machine; agree a bounded intervention with its owners.", "act"
            elif user_support:
                reason = (f"Joined node/job/user/array/exit-code records. One researcher owns {len(my_failed)}/{len(failed)} failures; "
                          f"their array contributes {array_control['local_failed']} local failures and "
                          f"{array_control['matching_exit_elsewhere']}/{array_control['elsewhere_jobs']} same-window sibling failures elsewhere "
                          f"with packed exit code {array_control['exit_code']}. Other researchers have {controls['others_failed']}/{len(others)} failures. "
                          "Investigate the shared workload/environment; this does not identify the exact code defect.")
                decision, verdict = "Investigate the shared array with its owner before draining this node.", "no_action"
            else:
                reason = (f"Joined node/job/user/array records. {len(failed)}/{len(on)} jobs FAILED; the dominant researcher accounts for "
                          f"{len(my_failed)} failures. No sufficiently replicated machine-signature or same-array control establishes cause. "
                          "Collect controlled reruns and diagnostics; a supplied finding alone is not a diagnosis.")
                decision, verdict = "Collect more evidence before changing machine capacity.", "monitor"
            counts_match = bool(f and len(on) == f["metadata"].get("jobs") and len(failed) == f["metadata"].get("failed"))
            out.append({"id": f["id"] if f else f"raw/window/{node}/{index}", "node": node, "window": index,
                        "finding_id": f["id"] if f else None, "start": self._iso(lo), "end": self._iso(min(hi, self.a.s.t1)),
                        "jobs": len(on), "failed": len(failed), "rate": number(len(failed)/len(on), 4),
                        "cluster_rate": item["cluster_rate"], "cause": cause, "reasoning": reason, "explanation": reason,
                        "decision": decision, "verdict": verdict, "controls": controls, "array_control": array_control,
                        "hardware": h, "requeued_jobs": int(on.attempts.gt(1).sum()), "detector_counts_match": counts_match,
                        "currently_elevated": item["elevated"],
                        "job_ids": [str(int(x)) for x in on.id_job], "examples": self.a.job_rows(on, limit=8)["rows"]})
        return out

    @cached_property
    def cases(self):
        # Preserve contrasting examples when available; never assume a class exists.
        hardware = sorted((x for x in self.windows if x["cause"] == "hardware"), key=lambda x: (-x["failed"], x["id"]))
        users = sorted((x for x in self.windows if x["cause"] == "user_code"), key=lambda x: (-x["array_control"]["matching_exit_elsewhere"], x["id"]))
        unknown = sorted((x for x in self.windows if x["cause"] == "cannot_determine"),
                         key=lambda x: (not any(h["node"] == x["node"] for h in hardware), x["window"], x["id"]))
        # Every recomputed window is accessible; no fixed three-case selection.
        return hardware + users + unknown

    def node_audit(self, price=2.5):
        from api.main import underperforming, recommendations
        ranked = underperforming(entity_type="node", limit=5, usd_per_gpu_hour=price).model_dump()
        rec = next((x for x in recommendations(usd_per_gpu_hour=price).model_dump()["recommendations"] if x["id"] == "rec_drain_nodes"), None)
        h = self.hardware
        included = h["node"] in {x["entity_id"] for x in ranked["rows"]} if h else None
        return {"hardware": h, "episodes": self.episodes, "cases": self.cases,
                "gpus_per_node": self.a.s.metadata["gpus_per_node"],
                "case_count": len(self.cases), "flagged_windows": len(self.windows),
                "rejected_hardware_findings": [e["finding_id"] for e in self.supplied_episodes if not e["supported"]] + self.invalid_hardware_findings,
                "baseline": {"nodes": ranked["rows"], "recommendation": rec, "includes_hardware_node": included,
                             "audit": "The proposed endpoint ranks finding counts and sums overlapping impacts. It does not validate raw-record controls. Its savings and confidence are not measured intervention outcomes."},
                "causal": None, "history": self.hardware_history(),
                "method": "Recompute 14-day node windows from the loaded sample origin. Evaluate supplied candidates and raw elevated-rate candidates. Diagnose only from raw controls; missing or contradictory evidence remains unresolved."}

    def hardware_history(self):
        j = self.jobs
        recorded = j[j.hit_node_failure]
        return {"jobs": len(recorded), "attempts": int(recorded.nodefail_attempts.sum()),
                "terminal_node_fail": int(j.state_name.eq("NODE_FAIL").sum()),
                "recovered_or_other_outcome": int((~recorded.state_name.eq("NODE_FAIL")).sum()),
                "basis": "Distinct GPU jobs with hit_node_failure, reconciled to nodefail_attempts from scheduler retry history. This counts recorded failures, not all possible hardware faults."}

    def drain(self, price=2.5, duration=4., recurrence=.5, operator_hours=1., nodes=1, evidence_id=None, gpus_per_node=None):
        h = next((e for e in self.episodes if e["supported"] and e["evidence_id"] == evidence_id), None) if evidence_id else self.hardware
        if not h:
            return {"available": False, "reason": "No machine-specific episode meets the evidence thresholds. A drain benefit cannot be estimated from the available records."}
        width = gpus_per_node if gpus_per_node is not None else self.a.s.metadata["gpus_per_node"]
        exposed = h["signature_gpu_hours"]
        avoided, unavailable, labor = exposed * recurrence, nodes * width * duration, operator_hours * 95
        return {"available": True, "evidence_id": h["evidence_id"], "node": h["node"], "start": h["start"], "end": h["end"],
                "inputs": {"duration": duration, "recurrence": recurrence, "operator_hours": operator_hours, "nodes": nodes, "price": price, "gpus_per_node": width},
                "reference_episode_hours": h["hours"], "observed_signature_gpu_hours": exposed,
                "avoided_gpu_hours": number(avoided), "unavailable_gpu_hours": number(unavailable),
                "avoided_value_usd": number(avoided * price), "capacity_cost_usd": number(unavailable * price),
                "operator_cost_usd": number(labor), "net_value_usd": number((avoided-unavailable)*price-labor),
                "break_even_drain_hours": number(max(0, (avoided * price - labor)/(nodes*width*price)), 4),
                "cannot_break_even_even_at_zero_drain": avoided*price < labor,
                "caveat": "Assume one recurrence and the selected fraction preventable. GPUs per machine, downtime and labor are scenario inputs; confirm actual machine inventory. Unavailable capacity is not proved cash or displaced work. Research value, queues and future recurrence are unmeasured."}

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
                "hardware_attributable_rationale": history["basis"] + f" {history['jobs']} jobs experienced {history['attempts']} recorded failed attempts; only {history['terminal_node_fail']} end in NODE_FAIL. Machine-specific signature investigations are not added to this scheduler-only count.",
                "card_imbalance_gpu_hours": {"point": levels[1]["gpu_hours"], "low": levels[0]["gpu_hours"], "high": levels[2]["gpu_hours"],
                                             "interval_kind": "scenario", "basis": cards["method"] + " Bounds represent measured exposure under different evidence thresholds, not recovered time. Excluded from recoverable_gpu_hours."},
                "card_imbalance_rationale": cards["limitation"] + " " + cards["pilot"],
                "card_imbalance_index_reasoning": f"Selected quiet-card rows by local gpu_id: {cards['quiet_card_index']}. " + cards["index_caveat"]}


@lru_cache(maxsize=2)
def research_for(a):
    return Research(a)


def research():
    return research_for(analysis())
