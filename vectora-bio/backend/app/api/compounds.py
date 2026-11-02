"""Compound endpoints."""

from fastapi import APIRouter, HTTPException, Query

from app.schemas.compound import Compound
from app.services import compound_service

router = APIRouter()


@router.get("", response_model=list[Compound])
def list_compounds(
    query: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
) -> list[Compound]:
    return compound_service.list_compounds(query=query, limit=limit)


@router.get("/{compound_id}", response_model=Compound)
def get_compound(compound_id: str) -> Compound:
    compound = compound_service.get_compound(compound_id)
    if compound is None:
        raise HTTPException(status_code=404, detail="Compound not found")
    return compound
