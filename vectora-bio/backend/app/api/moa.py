"""Similarity-based mechanism-of-action inference."""

from fastapi import APIRouter

from app.api.deps import DbSession, SettingsDep, StoreDep
from app.schemas.common import ANALYSIS_ERROR_RESPONSES
from app.schemas.prediction import AnalysisResponse, MoaInferenceRequest
from app.services import analysis_service

router = APIRouter(responses=ANALYSIS_ERROR_RESPONSES)


@router.post("/infer", response_model=AnalysisResponse, summary="Infer MoA from annotated phenotypic neighbours")
def infer_moa(body: MoaInferenceRequest, db: DbSession, settings: SettingsDep, store: StoreDep) -> AnalysisResponse:
    return analysis_service.infer_moa(body, store=store, db=db, settings=settings)
