import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from reclaim.analysis import analysis
from reclaim.main import app
from reclaim.planning import TrialDraft, brief_html, cash_path, draft_plan, shortlist


def test_owner_concentration_and_scoped_source_jobs():
    a = analysis()
    s = shortlist("cpu-placement", 3)
    assert s["total_owners"] == 68
    assert s["selected_jobs"] == 63
    assert s["selected_share_percent"] == pytest.approx(52.4, abs=.1)
    assert s["owners_for_80_percent"] == 13
    cohort = a.cohorts["cpu-placement"]
    selected = cohort[cohort.id_user.astype(str).isin([o["id"] for o in s["owners"]])]
    assert s["selected_gpu_hours"] == pytest.approx(selected.eligible_gpu_hours.sum(), abs=.01)
    assert s["selected_jobs"] == len(selected)
    for owner in s["owners"]:
        for job in owner["example_jobs"]:
            row = cohort[cohort.id_job.eq(int(job["id"]))].iloc[0]
            assert str(int(row.id_user)) == owner["id"]
            assert job["eligible_gpu_hours"] == pytest.approx(row.eligible_gpu_hours, abs=.01)


def test_shortlist_price_and_scope_do_not_change_evidence():
    for action in ["cpu-placement", "idle-sessions"]:
        one, three, five = [shortlist(action, n) for n in [1, 3, 5]]
        assert 0 < one["selected_gpu_hours"] <= three["selected_gpu_hours"] <= five["selected_gpu_hours"] <= five["total_eligible_gpu_hours"]
        assert [o["id"] for o in one["owners"]] == [three["owners"][0]["id"]]
        high = shortlist(action, 3, 5)
        assert high["owners"] == three["owners"]
        assert high["reference_value_usd"] == pytest.approx(2 * three["reference_value_usd"], abs=.02)
    assert shortlist("idle-sessions", 3)["selected_share_percent"] == pytest.approx(31.5, abs=.1)


def test_commercial_confirmations_never_establish_cash_savings():
    checks = {"owned": ["reuse", "purchase"], "committed": ["terms", "release"], "usage": ["meter", "release"]}
    for model, required in checks.items():
        unreviewed = cash_path(TrialDraft(billing_model=model))
        assert not unreviewed["conditions_confirmed"]
        reviewed = cash_path(TrialDraft(billing_model=model, confirmations=required, contract_date="2026-12-31"))
        assert reviewed["conditions_confirmed"]
        assert reviewed["verified_bill_savings_usd"] is None
        assert "unverified" in reviewed["status"]
    no_date = cash_path(TrialDraft(billing_model="committed", confirmations=["terms", "release"]))
    assert not no_date["conditions_confirmed"]
    assert not cash_path(TrialDraft(billing_model="usage", confirmations=["reuse", "purchase"]))["conditions_confirmed"]


def test_brief_limits_and_missing_owner_remain_draft_and_html_is_escaped():
    draft = TrialDraft(responsible_person='<script>alert("x")</script>', max_jobs=4, spend_cap_usd=750)
    plan = draft_plan(draft)
    assert "review date" in " ".join(plan["missing"])
    assert "4 opt-in trial jobs in total" in plan["scope_note"]
    html = brief_html(draft)
    assert '<script>' not in html
    assert '&lt;script&gt;' in html
    assert '$750.00' in html and '4 jobs total' in html
    assert 'Bill reduction: not established.' in html
    warning = draft_plan(TrialDraft(action_id="idle-sessions"))
    assert "warnings only" in warning["success"]
    assert "expiry disabled" in warning["stop"]


def test_trial_api_validation_and_export_do_not_change_claims():
    with TestClient(app) as client:
        before = client.get('/api/reclaim/claims').json()
        assert client.get('/api/reclaim/trial-shortlist?owners=6').status_code == 422
        assert client.get('/api/reclaim/trial-shortlist?action_id=all-users').status_code == 422
        assert client.post('/api/reclaim/trial-plan', json={"max_jobs": 0}).status_code == 422
        assert client.post('/api/reclaim/trial-plan', json={"spend_cap_usd": -1}).status_code == 422
        assert client.post('/api/reclaim/trial-plan', json={"review_date": "tomorrow"}).status_code == 422
        assert client.post('/api/reclaim/trial-plan', json={"owners": 2}).status_code == 422
        brief = client.post('/api/reclaim/trial-brief', json={"billing_model": "usage", "confirmations": ["meter", "release"]})
        assert brief.status_code == 200
        assert 'attachment' in brief.headers['content-disposition']
        assert 'Bill reduction: not established.' in brief.text
        assert client.get('/api/reclaim/claims').json() == before
