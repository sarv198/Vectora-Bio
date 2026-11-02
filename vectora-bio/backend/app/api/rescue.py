"""Rescue scoring endpoints."""

from fastapi import APIRouter, HTTPException

from app.schemas.prediction import RescueRequest, ReversalScore
from app.services import analysis_service

router = APIRouter()


@router.post("", response_model=ReversalScore)
def score_rescue(body: RescueRequest) -> ReversalScore:
    try:
        return analysis_service.score_rescue(
            body.values,
            reference_id=body.reference_id,
            query_id=body.query_id,
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Reference signature '{body.reference_id}' was not found",
        ) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
