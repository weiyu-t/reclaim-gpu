"""Bounded trial planning; commercial inputs never become telemetry claims."""
from datetime import date
from html import escape
from typing import Literal

from pydantic import BaseModel, Field

from .analysis import DEFAULT_PRICE, analysis, number


ActionId = Literal["cpu-placement", "idle-sessions"]
BillingModel = Literal["owned", "committed", "usage"]

BILLING_PATHS = {
    "owned": {
        "label": "Owned equipment",
        "outcome": "Reuse existing capacity; investigate a deferred purchase",
        "explanation": "Freeing time on equipment already purchased does not refund its purchase price. A future purchase could be deferred if the freed capacity meets that need.",
        "checks": [
            {"id": "reuse", "label": "Operations identified other work that can use this hardware."},
            {"id": "purchase", "label": "Finance identified a specific planned purchase that could be deferred."},
        ],
        "next_step": "Compare the proposed purchase with measured capacity freed and confirm that performance requirements still hold.",
    },
    "committed": {
        "label": "Prepaid or committed capacity",
        "outcome": "Potential reduction at the next contract change",
        "explanation": "Lower GPU use may leave the current payment unchanged. Finance must confirm when the commitment can be reduced and operations must identify capacity that can actually be released.",
        "checks": [
            {"id": "terms", "label": "Finance confirmed the commitment can be reduced at the date below."},
            {"id": "release", "label": "Operations mapped this workload to billed capacity that can be released."},
        ],
        "next_step": "Measure the trial, confirm replacement costs, and obtain the revised commitment or renewal quote.",
    },
    "usage": {
        "label": "Usage-based billing",
        "outcome": "Potential reduction in usage charges",
        "explanation": "The bill can fall if fewer billable resources are reserved or running. A quieter GPU inside an unchanged billed machine may cost exactly the same.",
        "checks": [
            {"id": "meter", "label": "Finance confirmed which billed units would decrease."},
            {"id": "release", "label": "Operations confirmed those billed resources can be stopped or reduced."},
        ],
        "next_step": "Compare matched billed usage before and after the trial, including replacement CPU charges and other added costs.",
    },
}


def shortlist(action_id: str, owners: int = 3, price: float = DEFAULT_PRICE):
    a = analysis()
    c = a.cohorts[action_id]
    action = next(x for x in a.actions(price) if x["id"] == action_id)
    grouped = c.groupby("id_user", dropna=False).agg(
        eligible_gpu_hours=("eligible_gpu_hours", "sum"), jobs=("id_job", "size")
    ).reset_index().sort_values(["eligible_gpu_hours", "id_user"], ascending=[False, True])
    total = float(grouped.eligible_gpu_hours.sum())
    selected = grouped.head(owners)
    rows = []
    for row in selected.itertuples():
        owner_jobs = c[c.id_user.eq(row.id_user)].sort_values(
            ["eligible_gpu_hours", "id_job"], ascending=[False, True])
        rows.append({
            "id": str(int(row.id_user)), "label": f"Researcher {int(row.id_user)}",
            "jobs": int(row.jobs), "eligible_gpu_hours": number(row.eligible_gpu_hours),
            "share_percent": number(100 * row.eligible_gpu_hours / total) if total else 0,
            "example_jobs": [{"id": str(int(j.id_job)), "eligible_gpu_hours": number(j.eligible_gpu_hours)}
                             for j in owner_jobs.head(3).itertuples()],
        })
    hours = float(selected.eligible_gpu_hours.sum())
    return {
        "action_id": action_id, "title": action["title"],
        "total_owners": len(grouped), "total_jobs": len(c),
        "total_eligible_gpu_hours": number(total), "owners": rows,
        "selected_owners": len(rows), "selected_jobs": int(selected.jobs.sum()),
        "selected_gpu_hours": number(hours), "selected_share_percent": number(100 * hours / total) if total else 0,
        "reference_value_usd": number(hours * price), "price": price,
        "owners_for_80_percent": int((grouped.eligible_gpu_hours.cumsum() < total * .8).sum() + 1) if total else 0,
        "basis": "Rank anonymized jobs.id_user by the sum of eligible GPU-hours in the existing, disjoint action cohorts. CPU placement owns overlaps. Hours are capped and retries excluded; session hours also exclude the four-hour grace period. Ties use ascending user ID.",
        "limitation": "This ranks historical time to investigate, not proven waste or future savings. Researcher IDs do not identify named people, teams, or budget owners. A trial must obtain owner agreement and verify repeatability.",
    }


class TrialDraft(BaseModel):
    action_id: ActionId = "cpu-placement"
    owners: Literal[1, 3, 5] = 3
    price: float = Field(default=DEFAULT_PRICE, gt=0, le=100)
    billing_model: BillingModel = "owned"
    confirmations: list[str] = Field(default_factory=list, max_length=4)
    contract_date: date | None = None
    responsible_person: str = Field(default="", max_length=120)
    review_date: date | None = None
    max_jobs: int = Field(default=5, ge=1, le=100)
    duration_days: int = Field(default=7, ge=1, le=30)
    spend_cap_usd: float = Field(default=500, ge=0, le=100000, allow_inf_nan=False)
    max_slowdown_percent: float = Field(default=10, ge=0, le=100, allow_inf_nan=False)


def cash_path(draft: TrialDraft):
    route = BILLING_PATHS[draft.billing_model]
    allowed = {c["id"] for c in route["checks"]}
    checked = set(draft.confirmations) & allowed
    missing = [c["label"] for c in route["checks"] if c["id"] not in checked]
    if draft.billing_model == "committed" and draft.contract_date is None:
        missing.append("Enter the next date finance says the commitment can change.")
    return {
        **route, "billing_model": draft.billing_model,
        "checks": [{**c, "confirmed": c["id"] in checked} for c in route["checks"]],
        "conditions_confirmed": not missing, "missing": missing,
        "status": "Conditions entered; financial result still unverified" if not missing else "Commercial conditions need review",
        "verified_bill_savings_usd": None,
        "evidence_status": "No invoices, contracts, or measured trial results are present in this dataset. Checked conditions are user statements, not independently verified evidence.",
    }


def draft_plan(draft: TrialDraft):
    scope = shortlist(draft.action_id, draft.owners, draft.price)
    cpu = draft.action_id == "cpu-placement"
    success = (f"Repeat a small set of agreed jobs on CPUs; outputs must match and runtime may increase by no more than {draft.max_slowdown_percent:g}% versus comparable GPU runs. Record CPU use and any added charges."
               if cpu else "Run warnings only. Ask owners whether each warning was useful, record voluntary releases and interruptions, and measure continuous inactivity before considering a timeout.")
    stop = ("Stop on the first output mismatch, a runtime breach, or reaching the spending cap. Restore GPU placement and review CPU queue delays."
            if cpu else "Pause warnings if an owner reports interference with useful work or the spending cap is reached. Keep automatic expiry disabled.")
    missing = []
    if not scope["selected_jobs"] or scope["selected_gpu_hours"] <= 0:
        missing.append("No eligible workload supports this trial in the loaded dataset.")
    if not draft.responsible_person.strip():
        missing.append("Assign a responsible person.")
    if draft.review_date is None:
        missing.append("Set a review date.")
    return {
        "scope": scope, "cash": cash_path(draft), "success": success, "stop": stop,
        "missing": missing, "eligible": scope["selected_gpu_hours"] > 0,
        "status": "No supported trial" if scope["selected_gpu_hours"] <= 0 else "Draft for owner review" if not missing else "Draft — details still needed",
        "decision": "No trial is supported by the current screening rules." if scope["selected_gpu_hours"] <= 0 else "Agree a bounded trial with the selected workload owners. No operational change is authorized or executed by this brief.",
        "scope_note": f"At most {draft.max_jobs} opt-in trial jobs in total across the selected owners, over {draft.duration_days} days. These are future trial limits, not a claim that the historical jobs will repeat.",
    }


def brief_html(draft: TrialDraft):
    plan = draft_plan(draft)
    if not plan["eligible"]:
        raise ValueError("No eligible GPU time supports this trial; a trial brief cannot be exported.")
    scope, cash = plan["scope"], plan["cash"]
    e = lambda x: escape(str(x), quote=True)
    money = lambda x: f"${x:,.2f}"
    owners = ", ".join(x["label"] for x in scope["owners"])
    checks = "".join(f"<li>{'User confirmed' if c['confirmed'] else 'To confirm'}: {e(c['label'])}</li>" for c in cash["checks"])
    review = draft.review_date.isoformat() if draft.review_date else "Not set"
    contract = draft.contract_date.isoformat() if draft.contract_date else "Not entered"
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Reclaim — draft trial brief</title><style>
@page{{size:A4;margin:14mm}}*{{box-sizing:border-box}}body{{font:13px/1.5 Arial,sans-serif;color:#233b30;max-width:780px;margin:30px auto;padding:0 20px}}h1{{font-size:25px;margin:4px 0 8px}}h2{{font-size:14px;margin:16px 0 6px}}p{{margin:5px 0}}small,.muted{{color:#56675d}}.tag{{font-size:11px;letter-spacing:1px}}.summary{{background:#edf2e7;padding:14px;margin:14px 0}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px 25px}}ul{{padding-left:18px;margin:6px 0}}footer{{border-top:1px solid #ccd6c7;margin-top:18px;padding-top:10px;font-size:10px}}@media print{{body{{font-size:12px;line-height:1.4;margin:0;padding:0;max-width:none}}h1{{font-size:21px}}h2{{margin-top:12px}}.summary{{padding:10px}}footer{{font-size:9px}}section{{break-inside:avoid}}}}
</style></head><body><div class="tag">RECLAIM / DRAFT TRIAL BRIEF</div>
<h1>{e(scope['title'])}</h1><p>{e(plan['decision'])}</p>
<div class="summary grid"><div><b>Responsible person</b><br>{e(draft.responsible_person.strip() or 'Not assigned')}</div><div><b>Review date</b><br>{e(review)}</div><div><b>Proposed spending cap</b><br>{e(money(draft.spend_cap_usd))} total incremental trial spend</div><div><b>Trial limit</b><br>{draft.max_jobs} jobs total / {draft.duration_days} days</div></div>
<section><h2>1. Owners to consult and historical evidence</h2><p>{e(owners)}</p><p>{scope['selected_jobs']} historical jobs account for {scope['selected_gpu_hours']:,.2f} eligible GPU-hours — {scope['selected_share_percent']:.1f}% of this action’s eligible time. Reference value: {e(money(scope['reference_value_usd']))} at {e(money(draft.price))}/GPU-hour.</p><p class="muted">This is time to investigate, not forecast trial earnings or demonstrated savings. Owners must agree to participate.</p></section>
<section><h2>2. Proposed trial and decision criteria</h2><p>{e(plan['scope_note'])}</p><p><b>Success:</b> {e(plan['success'])}</p><p><b>Stop / reverse:</b> {e(plan['stop'])}</p><p class="muted">The responsible person must monitor and enforce these proposed limits; this application does not control workloads or spending.</p></section>
<section><h2>3. Path to a financial outcome</h2><p><b>{e(cash['label'])}:</b> {e(cash['outcome'])}</p><p>{e(cash['explanation'])}</p><ul>{checks}</ul>{f'<p>Next contract change: {e(contract)}</p>' if draft.billing_model == 'committed' else ''}<p><b>Next verification:</b> {e(cash['next_step'])}</p><p><b>Bill reduction: not established.</b> {e(cash['evidence_status'])}</p></section>
<section><h2>4. Review and record the decision</h2><p>{e(plan['status'])}. {' '.join(e(x) for x in plan['missing'])}</p><p>Decision: ____________________ &nbsp; Reviewer: ____________________ &nbsp; Date: __________</p></section>
<footer>Source: {e(analysis().s.metadata['name'])}, snapshot {e(analysis().s.revision)}. {e(scope['basis'])}<br>Researcher IDs are accounts, not named budget owners. Dates, spending caps and commercial confirmations are user inputs. This brief does not alter claims.json. Open this file in a browser and print to save a PDF.</footer></body></html>'''
