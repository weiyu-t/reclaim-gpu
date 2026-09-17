import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from reclaim.analysis import analysis
from reclaim.main import app

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def a():
    return analysis()


def test_official_sample_reconciles(a):
    assert len(a.jobs) == 74849
    assert a.jobs.id_job.is_unique
    assert a.jobs.gpu_hours.sum() == pytest.approx(594003.84, abs=.01)
    assert a.gpus.gpu_hours.sum() == pytest.approx(a.jobs.gpu_hours.sum(), abs=.00001)
    assert len(a.findings) == 11979


def test_cohorts_are_disjoint_and_duration_is_capped(a):
    cpu, idle = a.cohorts.values()
    assert not (set(cpu.id_job) & set(idle.id_job))
    assert len(cpu) == 463
    assert len(idle) == 797
    assert a.overlap == 109
    for frame in [cpu, idle]:
        assert frame.attempts.eq(1).all()
        assert frame.eligible_gpu_hours.ge(0).all()
        assert (frame.eligible_gpu_hours <= frame.gpu_hours + 1e-9).all()
        assert (frame.eligible_gpu_hours <= frame.gpu_hours_alloc + 1e-9).all()
    assert (idle.eligible_gpu_hours <= (idle.gpu_hours_alloc - idle.gpu_count * 4).clip(lower=0) + 1e-9).all()


def test_cancellation_is_not_a_blanket_claim(a):
    selected = set().union(*(set(c.id_job) for c in a.cohorts.values()))
    all_cancelled = set(a.jobs.loc[a.jobs.state_name.eq("CANCELLED"), "id_job"])
    assert 0 < len(selected & all_cancelled) < len(all_cancelled)
    assert a.claims()["cancelled_is_waste"] is False


def test_intervals_and_allocation_ceiling(a):
    o = a.overview()
    r = o["recovery"]
    assert 0 <= r["low"] <= r["point"] <= r["high"] <= o["sample"]["gpu_hours"]
    assert r["point"] == pytest.approx(16206.57, abs=.01)
    assert r["target_coverage_percent"] < 100
    assert sum(s["gpu_hours"] for s in o["spend"]) == pytest.approx(o["sample"]["gpu_hours"], abs=.03)


def test_price_changes_dollars_not_evidence(a):
    base, double = a.overview(2.5), a.overview(5)
    assert base["recovery"]["point"] == double["recovery"]["point"]
    assert double["spend_usd"] == pytest.approx(2 * base["spend_usd"], abs=.02)
    for x, y in zip(base["actions"], double["actions"]):
        assert x["finding_ids"] == y["finding_ids"]
        assert y["value"]["point"] == pytest.approx(x["value"]["point"] * 2, abs=.02)


def test_zero_recovery_and_zero_cash_are_not_sold_as_savings(a):
    none = a.scenario(recovery=0, false_positive=.10)
    assert none["capacity_value_usd"] == 0
    assert none["net_capacity_value_usd"] < 0
    owned = a.scenario(cash_realization=0)
    assert owned["gross_bill_reduction_usd"] == 0
    assert owned["net_bill_value_usd"] < 0
    ideal = a.scenario(false_positive=0, cash_realization=1)
    assert ideal["downside_usd"] == 0
    assert ideal["net_bill_value_usd"] == ideal["capacity_value_usd"]


def test_downside_increases_and_break_even_reconciles(a):
    small, large = a.scenario(false_positive=.01), a.scenario(false_positive=.3)
    assert small["downside_usd"] < large["downside_usd"]
    breakeven = a.scenario(false_positive=small["break_even_false_positive"])
    assert abs(breakeven["net_capacity_value_usd"]) < 2


def test_evidence_joins_and_real_causal_case(a):
    for action in a.actions():
        assert action["finding_count"] == action["job_count"]
        for fid in action["finding_ids"]:
            f = a.by_finding[fid]
            assert not f["metadata"].get("synthetic", False)
            assert f["metadata"]["job_id"] in set(a.cohorts[action["id"]].id_job)
    c = a.causal_case()
    assert c["tasks"] == 721 and c["nodes"] == 34
    assert c["synthetic"] is False
    assert len(a.raw_job(c["jobs"]["rows"][0]["id"])["gpus"]) > 0


def test_claims_follow_schema_and_dashboard(a):
    claims = a.claims()
    Draft202012Validator(json.loads((ROOT / "starter/claims.schema.json").read_text())).validate(claims)
    o = a.overview()
    assert claims["recoverable_gpu_hours"]["point"] == o["recovery"]["point"]
    assert claims["recoverable_usd"]["point"] == o["recovery"]["value"]["point"]
    assert claims["recoverable_gpu_hours"]["interval_kind"] == "scenario"


def test_api_contracts_and_invalid_inputs():
    with TestClient(app) as c:
        for path in ["/api/reclaim/overview", "/api/reclaim/scenario", "/api/reclaim/causal-case", "/api/reclaim/agent/status", "/api/reclaim/rules"]:
            assert c.get(path).status_code == 200
        assert c.get("/api/reclaim/overview?price=-1").status_code == 422
        assert c.get("/api/reclaim/scenario?false_positive=1.1").status_code == 422
        assert c.get("/api/reclaim/actions/missing").status_code == 404
        assert c.get("/api/reclaim/jobs/0").status_code == 404
        assert c.get("/api/reclaim/actions/cpu-placement?offset=-1").status_code == 422
        assert c.post("/api/reclaim/investigate", json={"action_id": "unrestricted-query"}).status_code == 422
        status = c.get("/api/reclaim/agent/status").json()
        assert "key" not in status and "api_key" not in status
        r = c.get("/api/reclaim/claims")
        assert "attachment" in r.headers["content-disposition"]
