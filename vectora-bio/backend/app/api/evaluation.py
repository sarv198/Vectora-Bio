"""Model evaluation results."""

from fastapi import APIRouter, Query

from app.api.deps import DbSession, SettingsDep, StoreDep
from app.errors import FeatureDisabledError
from app.schemas.common import DATA_ERROR_RESPONSES
from app.schemas.evaluation import EvaluationListResponse, EvaluationRunRequest, EvaluationRunResponse
from app.services import evaluation_service

router = APIRouter(responses=DATA_ERROR_RESPONSES)


@router.get("", response_model=EvaluationListResponse, summary="List recorded evaluation metrics")
def list_evaluations(
    db: DbSession,
    metric_name: str | None = None,
    limit: int = Query(default=500, ge=1, le=2000),
) -> EvaluationListResponse:
    return evaluation_service.list_results(db, metric_name=metric_name, limit=limit)


@router.post("/run", response_model=EvaluationRunResponse, summary="Run the held-out benchmarks and store the metrics")
def run_evaluation(
    body: EvaluationRunRequest, db: DbSession, store: StoreDep, settings: SettingsDep
) -> EvaluationRunResponse:
    if not settings.evaluation_runs_enabled:
        raise FeatureDisabledError(
            "Benchmark runs are disabled on this server. Stored results remain available.",
            details={"setting": "EVALUATION_RUNS_ENABLED"},
        )
    return evaluation_service.run_benchmarks(store, db, body)
