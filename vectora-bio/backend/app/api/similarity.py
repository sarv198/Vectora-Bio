"""Compound-to-compound phenotypic similarity."""

from fastapi import APIRouter

from app.api.deps import DbSession, SettingsDep, StoreDep
from app.schemas.common import ANALYSIS_ERROR_RESPONSES
from app.schemas.prediction import AnalysisResponse, SimilarityRequest
from app.services import analysis_service

router = APIRouter(responses=ANALYSIS_ERROR_RESPONSES)


@router.post("/compounds", response_model=AnalysisResponse, summary="Rank compounds by phenotypic similarity")
def similar_compounds(
    body: SimilarityRequest, db: DbSession, settings: SettingsDep, store: StoreDep
) -> AnalysisResponse:
    return analysis_service.compound_similarity(body, store=store, db=db, settings=settings)
