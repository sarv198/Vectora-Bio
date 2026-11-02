"""Compound metadata endpoints."""

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.schemas.common import DATA_ERROR_RESPONSES, ErrorResponse, Page
from app.schemas.compound import Compound, CompoundDetail
from app.services import metadata_service

router = APIRouter(responses=DATA_ERROR_RESPONSES)


@router.get("", response_model=Page[Compound], summary="List imported compounds")
def list_compounds(
    db: DbSession,
    search: str | None = Query(default=None, description="Substring of compound id or name."),
    cell_line: str | None = None,
    timepoint: float | None = Query(default=None, gt=0),
    moa: str | None = Query(default=None, description="Substring of the MoA annotation."),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> Page[Compound]:
    return metadata_service.list_compounds(
        db, search=search, cell_line=cell_line, timepoint=timepoint, moa=moa, limit=limit, offset=offset
    )


@router.get(
    "/{compound_id}",
    response_model=CompoundDetail,
    responses={404: {"model": ErrorResponse}},
    summary="Get a compound and all of its imported contexts",
)
def get_compound(compound_id: str, db: DbSession) -> CompoundDetail:
    return metadata_service.get_compound(db, compound_id)
