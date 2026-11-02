"""Gene endpoints."""

from fastapi import APIRouter, HTTPException, Query

from app.schemas.gene import Gene
from app.services.data_loader import load_records

router = APIRouter()


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _gene_from_row(row: dict) -> Gene | None:
    symbol = _optional_text(row.get("symbol"))
    if symbol is None:
        return None
    return Gene(
        symbol=symbol,
        entrez_id=_optional_int(row.get("entrez_id")),
        name=_optional_text(row.get("name")),
    )


def _genes() -> list[Gene]:
    genes: list[Gene] = []
    for row in load_records("genes"):
        gene = _gene_from_row(row)
        if gene is not None:
            genes.append(gene)
    return genes


@router.get("", response_model=list[Gene])
def list_genes(
    query: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
) -> list[Gene]:
    genes = _genes()
    if query:
        needle = query.lower()
        genes = [gene for gene in genes if needle in gene.symbol.lower()]
    return genes[:limit]


@router.get("/{symbol}", response_model=Gene)
def get_gene(symbol: str) -> Gene:
    for gene in _genes():
        if gene.symbol.lower() == symbol.lower():
            return gene
    raise HTTPException(status_code=404, detail="Gene not found")
