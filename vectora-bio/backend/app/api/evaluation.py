"""Evaluation endpoints."""

from fastapi import APIRouter

from app.schemas.evaluation import EvaluationReport, EvaluationRequest
from app.services import analysis_service

router = APIRouter()


@router.post("", response_model=EvaluationReport)
def evaluate(body: EvaluationRequest) -> EvaluationReport:
    return analysis_service.evaluate(body.task)
