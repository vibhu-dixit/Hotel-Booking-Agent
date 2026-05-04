from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_decision_service
from app.api.schemas import DecisionEvaluateRequest, DecisionEvaluateResponse
from app.application.decision_service import DecisionService

router = APIRouter()


@router.post("/decision/evaluate", response_model=DecisionEvaluateResponse)
def decision_evaluate(
    req: DecisionEvaluateRequest,
    svc: Annotated[DecisionService, Depends(get_decision_service)],
) -> DecisionEvaluateResponse:
    decision = svc.evaluate(req.trip_id)
    return DecisionEvaluateResponse(decision_id=decision.id, ranked=decision.ranked)
