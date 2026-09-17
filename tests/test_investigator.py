import asyncio
import json
import httpx
import pytest
from reclaim import investigator as inv

BRIEF = json.dumps({"recommendation": "Pilot CPU placement.",
                    "downside": "Migration may fail.", "pilot": "Check output parity.",
                    "finding_id": "8907b8b4-1658-5867-9eeb-ed99a4df81da"})


def test_mcp_retrieves_real_records():
    trace, obs = asyncio.run(inv.collect("cpu-placement", 2.5))
    assert [x["tool"] for x in trace] == ["decision_evidence", "list_rules", "list_findings"]
    assert obs["decision_evidence"]["action"]["job_count"] == 463
    assert obs["list_findings"]["total"] == 463


def test_idle_brief_excludes_cpu_overlap_and_synthetic_ids():
    from reclaim.analysis import analysis
    _, obs = asyncio.run(inv.collect("idle-sessions", 2.5))
    a = analysis()
    eligible = set(a.cohorts["idle-sessions"].id_job)
    for f in obs["list_findings"]["findings"]:
        assert f["metadata"]["job_id"] in eligible
    for row in obs["decision_evidence"]["jobs"]["rows"]:
        for fid in row["finding_ids"]:
            f = a.by_finding[fid]
            assert f["detectorId"] == "rules::idle-interactive-session"
            assert not f["metadata"].get("synthetic")


@pytest.mark.parametrize("status", [200, 403])
def test_provider_error_or_model_access_denial_falls_back(monkeypatch, tmp_path, status):
    original = httpx.AsyncClient
    calls = []
    def handler(request):
        import json
        model = json.loads(request.content)["model"]
        calls.append(model)
        if len(calls) == 1:
            return httpx.Response(status, json={"error": {"message": "busy or unavailable"}})
        return httpx.Response(200, json={
            "choices": [{"message": {"content": BRIEF}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        })
    monkeypatch.setattr(inv, "settings", lambda: {"key": "test-only", "url": "https://example.test/v1", "model": "test-first"})
    monkeypatch.setattr(inv.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    monkeypatch.setattr(inv, "ROOT", tmp_path)
    inv._cache.clear()
    result = asyncio.run(inv.investigate("cpu-placement", 2.5))
    assert result["mode"] == "live"
    assert result["model"] == "zai-org/GLM-5.3-Flash"
    assert len(calls) == 2
    assert result["usage"]["total_tokens"] == 15
    assert "test-only" not in (tmp_path / "out/agent_runs.jsonl").read_text()
    inv._cache.clear()


def test_empty_final_answer_never_exposes_reasoning_and_counts_both_attempts(monkeypatch, tmp_path):
    original = httpx.AsyncClient
    calls = []
    def handler(request):
        calls.append(request)
        message = ({"content": "", "reasoning": "PRIVATE REASONING"} if len(calls) == 1
                   else {"content": BRIEF})
        return httpx.Response(200, json={
            "choices": [{"message": message, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        })
    monkeypatch.setattr(inv, "settings", lambda: {"key": "test-only", "url": "https://example.test/v1", "model": "test-first"})
    monkeypatch.setattr(inv.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    monkeypatch.setattr(inv, "ROOT", tmp_path)
    inv._cache.clear()
    result = asyncio.run(inv.investigate("cpu-placement", 2.5))
    assert result["mode"] == "live" and result["usage"]["total_tokens"] == 30
    assert result["attempts"][0]["status"] == "empty_answer"
    assert "PRIVATE REASONING" not in str(result)
    assert "PRIVATE REASONING" not in (tmp_path / "out/agent_runs.jsonl").read_text()
    cached = asyncio.run(inv.investigate("cpu-placement", 2.5))
    assert cached["cached"] and len(calls) == 2
    inv._cache.clear()


def test_structured_answer_rejects_unknown_ids_and_nonanswers():
    observations = {"decision_evidence": inv.decision_evidence("cpu-placement")}
    final = inv.final_brief(BRIEF, observations)
    assert final and "11,985.85 capped eligible GPU-hours" in final
    bad = json.loads(BRIEF)
    bad["finding_id"] = "invented"
    assert inv.final_brief(json.dumps(bad), observations) is None
    bad = json.loads(BRIEF)
    bad["recommendation"] = "Save $999999 immediately."
    assert inv.final_brief(json.dumps(bad), observations) is None
    assert inv.final_brief("internal reasoning text", observations) is None
    assert inv.final_brief('{"recommendation": "partial"}', observations) is None
