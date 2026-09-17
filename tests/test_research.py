import asyncio
import json
import pytest
from fastapi.testclient import TestClient
from reclaim.main import app
from reclaim.research import research
from reclaim import investigator as inv


@pytest.fixture(scope="module")
def r():
    return research()


def test_hardware_episode_uses_same_window_researcher_controls(r):
    h = r.hardware
    assert (h["jobs"], h["failed"], h["signature_jobs"]) == (144, 140, 114)
    assert (h["elsewhere_jobs"], h["elsewhere_signature"]) == (311, 0)
    assert len(h["controls"]) == 3
    assert all(c["elsewhere_jobs"] > 0 for c in h["controls"])
    assert 0 < h["signature_gpu_hours"] < .03
    assert h["signature_gpu_hours"] < h["all_failed_gpu_hours"]
    for c in h["controls"]:
        assert not set(c["here_job_ids"]) & set(c["elsewhere_job_ids"])
        peers = r.jobs[r.jobs.id_job.isin([int(x) for x in c["elsewhere_job_ids"]])]
        assert peers.time_end.ge(r._stamp(h["start"])).all()
        assert peers.time_end.lt(r._stamp(h["end"])).all()


def test_window_cases_reconcile_and_do_not_carry_hardware_labels_forward(r):
    hardware, workload, unknown = r.cases
    assert all(c["detector_counts_match"] for c in r.cases)
    assert hardware["node"] == unknown["node"]
    assert (hardware["window"], unknown["window"]) == (0, 3)
    assert [c["cause"] for c in r.cases] == ["hardware", "user_code", "cannot_determine"]
    assert workload["array_control"]["matching_exit_elsewhere"] == 568
    assert workload["array_control"]["elsewhere_jobs"] == 568
    assert workload["controls"]["others_failed"] == 2
    assert all(c["requeued_jobs"] == 0 for c in (hardware, workload))
    assert not r.node_audit()["baseline"]["includes_hardware_node"]


def test_failed_attempt_history_not_just_terminal_state(r):
    h = r.hardware_history()
    assert (h["jobs"], h["attempts"], h["terminal_node_fail"]) == (31, 39, 10)
    assert h["recovered_or_other_outcome"] + h["terminal_node_fail"] == h["jobs"]
    assert r.claims()["hardware_attributable_failures"] == 31


def test_drain_costs_and_break_even_without_operator_cost(r):
    targeted, broad = r.drain(nodes=1), r.drain(nodes=5)
    assert broad["unavailable_gpu_hours"] == 5 * targeted["unavailable_gpu_hours"]
    assert broad["net_value_usd"] < targeted["net_value_usd"] < 0
    none = r.drain(recurrence=0, duration=0, operator_hours=0)
    assert none["net_value_usd"] == 0
    no_labor = r.drain(recurrence=1, operator_hours=0)
    break_even = r.drain(recurrence=1, operator_hours=0, duration=no_labor["break_even_drain_hours"])
    assert abs(break_even["net_value_usd"]) <= .01
    assert targeted["cannot_break_even_even_at_zero_drain"]


def test_card_thresholds_are_nested_duration_capped_and_not_headline_savings(r):
    d = r.card_data
    strict, point, broad = [d[k] for k in ("small_memory", "peak_zero", "average_zero")]
    keys = lambda f: set(zip(f.Node, f.gpu_id, f.id_job))
    assert keys(strict) < keys(point) < keys(broad)
    assert len(point) == 380 and point.id_job.nunique() == 370
    assert point.smutilization_pct_max.eq(0).all()
    assert (point.capped_hours <= point.walltime_sec / 3600).all()
    assert point.capped_hours.sum() == pytest.approx(4100.17313889)
    assert len(point[point.mem_used_frac.gt(.01)]) == 288
    assert r.cards(limit=0)["existing_plan_overlap_jobs"] == 0
    assert r.a.claims()["recoverable_gpu_hours"]["point"] == 16206.57
    assert r.a.claims()["card_imbalance_gpu_hours"]["point"] == 4100.17


def test_research_routes_pagination_and_bounds():
    with TestClient(app) as c:
        for path in ("node-audit", "drain-scenario", "card-imbalance"):
            assert c.get("/api/reclaim/" + path).status_code == 200
        assert c.get("/api/reclaim/drain-scenario?nodes=0").status_code == 422
        assert c.get("/api/reclaim/drain-scenario?recurrence=2").status_code == 422
        assert c.get("/api/reclaim/drain-scenario?duration=-1").status_code == 422
        one = c.get("/api/reclaim/card-imbalance?offset=0&limit=20").json()
        two = c.get("/api/reclaim/card-imbalance?offset=20&limit=20").json()
        assert not {x["id"] for x in one["examples"]} & {x["id"] for x in two["examples"]}
        assert one["point"] == two["point"]


def test_node_investigation_uses_mcp_and_safe_keyless_brief(monkeypatch, tmp_path):
    monkeypatch.setattr(inv, "settings", lambda: {"key": "", "url": "https://example.test/v1", "model": "test"})
    monkeypatch.setattr(inv, "ROOT", tmp_path)
    inv._cache.clear()
    result = asyncio.run(inv.investigate("node-audit", 2.5))
    assert result["mode"] == "evidence-only"
    assert [t["tool"] for t in result["tool_trace"]] == ["decision_evidence", "list_rules", "causal"]
    assert "114" in result["text"] and "311" in result["text"]
    obs = {"decision_evidence": inv.decision_evidence("node-audit")}
    answer = {"recommendation": "Inspect the machine.", "downside": "Draining removes capacity.",
              "pilot": "Use controlled reruns.", "finding_id": obs["decision_evidence"]["finding_id"]}
    assert "0.022 GPU-hours" in inv.final_brief(json.dumps(answer), obs)
    inv._cache.clear()


def test_node_financial_downside_cannot_invert_cost_and_net_benefit():
    e = inv.decision_evidence("node-audit")
    answer = {"recommendation": "Inspect the machine.",
              "downside": "The drain cost is negative and inspection provides no value.",
              "pilot": "Compare controlled reruns.", "finding_id": e["finding_id"]}
    brief = inv.final_brief(json.dumps(answer), {"decision_evidence": e})
    assert "cost is negative" not in brief
    assert "provides no value" not in brief
    assert "cost USD 115.00" in brief and "USD 0.03 of avoided GPU time" in brief
    assert "inspection may still be justified" in brief
