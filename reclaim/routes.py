from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
import json
from .analysis import analysis
from .research import research

router = APIRouter(prefix="/api/reclaim", tags=["Reclaim — decision workspace"])


@router.get("/overview")
def overview(price: float = Query(2.5, gt=0, le=100)):
    return analysis().overview(price)


@router.get("/actions/{action_id}")
def evidence(action_id: str, price: float = Query(2.5, gt=0, le=100),
             offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100)):
    try:
        return analysis().evidence(action_id, price, offset, limit)
    except KeyError:
        raise HTTPException(404, "Unknown recommendation")


@router.get("/jobs/{job_id}")
def job(job_id: int):
    try:
        return analysis().raw_job(job_id)
    except KeyError:
        raise HTTPException(404, "Job not found")


@router.get("/findings/{finding_id}")
def finding(finding_id: str):
    f = analysis().by_finding.get(finding_id)
    if not f:
        raise HTTPException(404, "Finding not found")
    return f


@router.get("/causal-case")
def causal_case():
    from api.main import causal
    from api.models import CausalRequest
    case = analysis().causal_case()
    if case:
        case["causal"] = causal(CausalRequest(finding_id=case["finding_id"])).model_dump()
    return case


@router.get("/rules")
def rules():
    from api.main import rules as official_rules
    return official_rules().model_dump()


@router.get("/scenario")
def scenario(price: float = Query(2.5, gt=0, le=100),
             recovery: float = Query(1, ge=0, le=1.5),
             false_positive: float = Query(.02, ge=0, le=1),
             cash_realization: float = Query(0, ge=0, le=1),
             engineer_hours_per_job: float = Query(.5, ge=0, le=100),
             engineer_rate: float = Query(95, ge=0, le=1000)):
    return analysis().scenario(price, recovery, false_positive, cash_realization,
                               engineer_hours_per_job, engineer_rate)


@router.get("/claims")
def claims(price: float = Query(2.5, gt=0, le=100)):
    return Response(json.dumps(analysis().claims(price), indent=2), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="claims.json"'})


@router.get("/node-audit")
def node_audit(price: float = Query(2.5, gt=0, le=100)):
    return research().node_audit(price)


@router.get("/drain-scenario")
def drain_scenario(price: float = Query(2.5, gt=0, le=100),
                   duration: float = Query(4, ge=0, le=168),
                   recurrence: float = Query(.5, ge=0, le=1),
                   operator_hours: float = Query(1, ge=0, le=24),
                   nodes: int = Query(1, ge=1, le=5)):
    return research().drain(price, duration, recurrence, operator_hours, nodes)


@router.get("/card-imbalance")
def card_imbalance(price: float = Query(2.5, gt=0, le=100),
                   offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    return research().cards(price, offset, limit)


@router.get("/agent/status")
def agent_status():
    from .investigator import settings
    s = settings()
    return {"configured": bool(s["key"]), "provider": "Featherless",
            "model": s["model"], "tools": "MantisGrid MCP"}


class InvestigationRequest(BaseModel):
    action_id: str = Field(pattern=r"^(cpu-placement|idle-sessions|causal-case|node-audit)$")
    price: float = Field(default=2.5, gt=0, le=100)


@router.post("/investigate")
async def investigate(req: InvestigationRequest):
    from .investigator import investigate as run
    return await run(req.action_id, req.price)
