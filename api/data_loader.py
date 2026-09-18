"""Validated dataset snapshots shared by the API and in-process MCP tools."""
import json
import os
from contextvars import ContextVar
from threading import RLock
from uuid import uuid4
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PREP, SYN = ROOT / "data" / "prepped", ROOT / "data" / "synthetic"

V100_PER_NODE = 2
SM_PROXY_CAVEAT = ("SM utilization is a proxy for useful work. A data-loader-bound "
                   "or communication-bound job does real work at low SM occupancy.")


class Store:
    def __init__(self):
        data_dir = Path(os.environ.get("RECLAIM_DATA_DIR", ROOT / "data"))
        prep, syn = data_dir / "prepped", data_dir / "synthetic"
        paths = [prep / "jobs.parquet", prep / "gpus.parquet", syn / "resources.parquet", syn / "edges.parquet", syn / "findings.json"]
        meta_path = data_dir / "dataset.json"
        watched = paths + ([meta_path] if meta_path.exists() else [])
        before = [(p.stat().st_mtime_ns, p.stat().st_size) for p in watched]
        metadata = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        from pydantic import BaseModel, Field, ConfigDict
        class Metadata(BaseModel):
            model_config = ConfigDict(extra="forbid")
            name: str = Field(default="Local workload dataset", min_length=1, max_length=120)
            epoch_offset: float = Field(default=1750862959, ge=0, le=253402000000, allow_inf_nan=False)
            gpus_per_node: int = Field(default=2, ge=1, le=1024, strict=True)
        self.metadata = Metadata.model_validate(metadata).model_dump()
        self.epoch_offset = self.metadata["epoch_offset"]
        self.jobs = pd.read_parquet(prep / "jobs.parquet")
        self.gpus = pd.read_parquet(prep / "gpus.parquet")
        required_jobs = {"id_job", "id_user", "state_name", "is_success", "gpu_hours", "gpu_hours_alloc", "gpu_count", "walltime_sec", "attempts", "sm_util_avg", "sm_util_max", "job_type", "time_submit", "time_start", "time_end", "exit_code", "id_array_job", "is_array_task", "hit_node_failure", "nodefail_attempts", "wait_sec"}
        required_gpus = {"id_job", "Node", "gpu_id", "gpu_hours", "smutilization_pct_avg", "smutilization_pct_max", "mem_used_frac", "pcierxbandwidth_megabytes_avg", "pcietxbandwidth_megabytes_avg"}
        for name, frame, columns in [("jobs", self.jobs, required_jobs), ("gpus", self.gpus, required_gpus)]:
            missing = columns - set(frame.columns)
            if missing:
                raise ValueError(f"{name}.parquet is missing columns: {', '.join(sorted(missing))}")
        if self.jobs.id_job.isna().any() or not self.jobs.id_job.is_unique:
            raise ValueError("jobs.id_job must be present and unique")
        if not self.gpus.id_job.isin(self.jobs.id_job).all():
            raise ValueError("Every GPU record must reference a job in jobs.parquet")
        for col in ["gpu_hours", "time_submit", "time_end"]:
            if not np.isfinite(self.jobs[col].dropna()).all():
                raise ValueError(f"jobs.{col} must contain finite numbers")
        if self.jobs.gpu_hours.isna().any() or self.jobs.time_submit.isna().any() or self.jobs.time_end.isna().any():
            raise ValueError("Job allocation, submission and end times must be present")
        if not np.isfinite(self.jobs.time_start.dropna()).all():
            raise ValueError("Non-null job start times must be finite")
        if self.jobs.gpu_hours.lt(0).any():
            raise ValueError("jobs.gpu_hours must not be negative")
        for name, frame, fields in [("jobs", self.jobs, ["id_job", "id_user"]), ("gpus", self.gpus, ["id_job", "gpu_id"])]:
            for col in fields:
                if frame[col].isna().any() or not np.isfinite(frame[col]).all() or (frame[col] % 1 != 0).any():
                    raise ValueError(f"{name}.{col} must contain integer identifiers")
        if self.gpus.Node.isna().any() or self.gpus.duplicated(["Node", "gpu_id", "id_job"]).any():
            raise ValueError("GPU records need a node and a unique (Node, gpu_id, id_job) key")
        for col in ["is_success", "is_array_task", "hit_node_failure"]:
            if not self.jobs[col].dropna().isin([True, False]).all():
                raise ValueError(f"jobs.{col} must contain boolean flags")
        if len(self.jobs):
            pd.to_datetime(pd.Series([self.jobs.time_submit.min(), self.jobs.time_end.max()]) + self.epoch_offset, unit="s", utc=True)
        self.jobs = self.jobs[self.jobs.state_name.notna()].copy()
        self.jobs["is_success"] = self.jobs.is_success.fillna(False).astype(bool)
        self.jobs["util"] = self.jobs.sm_util_avg.clip(0, 100) / 100

        self.resources = pd.read_parquet(syn / "resources.parquet")
        self.edges = pd.read_parquet(syn / "edges.parquet")
        for name, frame, columns in [("resources", self.resources, {"id", "type", "name", "resourceId"}),
                                     ("edges", self.edges, {"sourceId", "destinationId"})]:
            if columns - set(frame.columns):
                raise ValueError(f"{name}.parquet needs columns: {', '.join(sorted(columns))}")
        self.findings = json.loads((syn / "findings.json").read_text())
        from .models import Finding
        self.findings = [Finding.model_validate(f).model_dump() for f in self.findings]
        if len({f["id"] for f in self.findings}) != len(self.findings):
            raise ValueError("Finding IDs must be unique")
        if [(p.stat().st_mtime_ns, p.stat().st_size) for p in watched] != before:
            raise ValueError("Dataset changed while loading. Finish replacing all files and retry.")
        self.revision = uuid4().hex

        # Stable join keys back to jobs.parquet and the node list, so a finding
        # can be joined without parsing the job id out of its prose.
        pods = self.resources[self.resources.type == "k8s:pod"]
        nodes = self.resources[self.resources.type == "k8s:node"]
        rid_to_job = dict(zip(pods.id, pods.resourceId))
        rid_to_node = dict(zip(nodes.id, nodes.name))
        for f in self.findings:
            md = f.setdefault("metadata", {})
            for r in f.get("resourceIds", []):
                if "job_id" not in md and r in rid_to_job:
                    try:
                        md["job_id"] = int(rid_to_job[r])
                    except (TypeError, ValueError):
                        md["job_id"] = str(rid_to_job[r])
                if "node" not in md and r in rid_to_node:
                    md["node"] = rid_to_node[r]

        self.by_id = {r.id: r for r in self.resources.itertuples(index=False)}
        self.name_of = dict(zip(self.resources.id, self.resources.name))
        self.type_of = dict(zip(self.resources.id, self.resources.type))

        j = self.jobs
        self.allocated = float(j.gpu_hours.sum())
        self.computed = float((j.gpu_hours * j.util).sum())
        ok = j[j.is_success]
        self.computed_completed = float((ok.gpu_hours * ok.util).sum())

        # window, in real dates -- the price book carries the epoch offset
        self.t0, self.t1 = (float(j.time_submit.min()), float(j.time_end.max())) if len(j) else (0., 0.)

    # ---- aggregations the endpoints need ----
    def waste_rows(self):
        g = self.jobs.groupby("state_name").gpu_hours.sum().sort_values(ascending=False)
        return [{"state": k, "gpu_hours": round(float(v), 1),
                 "share": round(float(v / self.allocated), 4) if self.allocated else 0} for k, v in g.items()]

    def queue(self):
        w = self.jobs.wait_sec.dropna()
        if w.empty:
            return {"p50_sec": None, "p90_sec": None, "p99_sec": None, "max_sec": None, "total_wait_hours": 0., "n_jobs": 0}
        return {"p50_sec": float(w.median()), "p90_sec": float(w.quantile(.90)),
                "p99_sec": float(w.quantile(.99)), "max_sec": float(w.max()),
                "total_wait_hours": float(w.sum() / 3600), "n_jobs": int(len(w))}

    def scaling(self):
        band = pd.cut(self.jobs.gpu_count, [0, 1, 2, 4, 8, 16, 64],
                      labels=["1", "2", "3-4", "5-8", "9-16", "17-64"])
        g = self.jobs.groupby(band, observed=True).agg(
            jobs=("gpu_hours", "size"), gpu_hours=("gpu_hours", "sum"),
            median_sm_util=("sm_util_avg", "median"),
            share_under_5pct=("sm_util_avg", lambda x: float((x < 5).mean())),
            share_over_80pct=("sm_util_avg", lambda x: float((x > 80).mean())))
        return [{"gpu_count_band": str(i), "jobs": int(r.jobs),
                 "gpu_hours": round(float(r.gpu_hours), 1),
                 "median_sm_util_pct": round(float(r.median_sm_util), 1),
                 "share_under_5pct": round(r.share_under_5pct, 3),
                 "share_over_80pct": round(r.share_over_80pct, 3)}
                for i, r in g.iterrows()]

    def findings_by_resource(self):
        """finding count and impact per resource id."""
        out = {}
        for f in self.findings:
            for rid_ in f["resourceIds"]:
                e = out.setdefault(rid_, {"count": 0, "impact_gpu_hours": 0.0, "owners": []})
                e["count"] += 1
                if f["metadata"].get("impact_scope") == "job":
                    e["impact_gpu_hours"] += f["metadata"].get("impact_gpu_hours") or 0.0
                if f["metadata"].get("owner"):
                    e["owners"].append(f["metadata"]["owner"])
        return out


_current = None
_lock = RLock()
snapshot_context = ContextVar("reclaim_snapshot", default=None)


def store() -> Store:
    snapshot = snapshot_context.get()
    if snapshot is not None:
        return snapshot
    global _current
    with _lock:
        if _current is None:
            _current = Store()
        return _current


def reload_store() -> Store:
    """Validate a complete replacement before atomically publishing it.

    In-flight requests retain their pinned snapshot. Failed reloads keep the last
    valid snapshot; the caller receives the validation error, never a partial load.
    """
    global _current
    with _lock:
        candidate = Store()
        _current = candidate
        return candidate
