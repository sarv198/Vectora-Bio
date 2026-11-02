"""Mechanism inference endpoints."""

from fastapi import APIRouter, HTTPException

from app.schemas.prediction import MechanismPrediction, MechanismRequest
from app.services import analysis_service

router = APIRouter()


@router.post("", response_model=list[MechanismPrediction])
def infer_mechanisms(body: MechanismRequest) -> list[MechanismPrediction]:
    try:
        return analysis_service.infer_mechanisms(body.values)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
