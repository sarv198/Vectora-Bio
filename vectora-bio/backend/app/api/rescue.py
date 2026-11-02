"""Phenotypic rescue / perturbation reversal search."""

from fastapi import APIRouter

from app.api.deps import DbSession, SettingsDep, StoreDep
from app.schemas.common import ANALYSIS_ERROR_RESPONSES
from app.schemas.prediction import AnalysisResponse, RescueSearchRequest
from app.services import analysis_service

router = APIRouter(responses=ANALYSIS_ERROR_RESPONSES)


@router.post("/search", response_model=AnalysisResponse, summary="Rank compounds that oppose a perturbation phenotype")
def search_rescue(body: RescueSearchRequest, db: DbSession, settings: SettingsDep, store: StoreDep) -> AnalysisResponse:
    return analysis_service.search_rescue(body, store=store, db=db, settings=settings)
