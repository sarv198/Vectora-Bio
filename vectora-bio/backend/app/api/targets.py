"""Compound-to-gene matching and candidate target prioritization."""

from fastapi import APIRouter

from app.api.deps import DbSession, SettingsDep, StoreDep
from app.schemas.common import ANALYSIS_ERROR_RESPONSES
from app.schemas.prediction import AnalysisResponse, TargetPrioritizationRequest
from app.services import analysis_service

router = APIRouter(responses=ANALYSIS_ERROR_RESPONSES)


@router.post("/prioritize", response_model=AnalysisResponse, summary="Rank candidate target genes for a compound")
def prioritize_targets(
    body: TargetPrioritizationRequest, db: DbSession, settings: SettingsDep, store: StoreDep
) -> AnalysisResponse:
    return analysis_service.prioritize_targets(body, store=store, db=db, settings=settings)
