"""Genetic perturbation endpoints."""

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.schemas.common import DATA_ERROR_RESPONSES, ErrorResponse, GeneticPerturbationType, Page
from app.schemas.genetic import GeneDetail, GeneticPerturbation
from app.services import metadata_service

router = APIRouter(responses=DATA_ERROR_RESPONSES)


@router.get("", response_model=Page[GeneticPerturbation], summary="List imported genetic perturbations")
def list_genes(
    db: DbSession,
    search: str | None = Query(default=None, description="Substring of gene symbol, gene id, or perturbation id."),
    perturbation_type: GeneticPerturbationType | None = None,
    cell_line: str | None = None,
    timepoint: float | None = Query(default=None, gt=0),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> Page[GeneticPerturbation]:
    return metadata_service.list_genetic_perturbations(
        db,
        search=search,
        perturbation_type=perturbation_type,
        cell_line=cell_line,
        timepoint=timepoint,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{gene_id}",
    response_model=GeneDetail,
    responses={404: {"model": ErrorResponse}},
    summary="Get a gene (by id or symbol) and its perturbations",
)
def get_gene(gene_id: str, db: DbSession) -> GeneDetail:
    return metadata_service.get_gene(db, gene_id)
