"""Model evaluation results."""

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.schemas.common import DATA_ERROR_RESPONSES
from app.schemas.evaluation import EvaluationListResponse
from app.services import evaluation_service

router = APIRouter(responses=DATA_ERROR_RESPONSES)


@router.get("", response_model=EvaluationListResponse, summary="List recorded evaluation metrics")
def list_evaluations(
    db: DbSession,
    metric_name: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
) -> EvaluationListResponse:
    return evaluation_service.list_results(db, metric_name=metric_name, limit=limit)
