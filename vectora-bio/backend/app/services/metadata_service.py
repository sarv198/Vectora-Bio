"""Queries over compound and genetic perturbation metadata stored in the database."""

from collections.abc import Iterator
from contextlib import contextmanager

import pandas as pd
from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import CompoundRecord, GeneticPerturbationRecord
from app.errors import DatabaseUnavailableError, DataNotLoadedError, NotFoundError
from app.schemas.common import GeneticPerturbationType, Page
from app.schemas.compound import Compound, CompoundDetail
from app.schemas.genetic import GeneDetail, GeneticPerturbation

COMPOUND_METADATA = "compound_metadata"
GENETIC_METADATA = "genetic_perturbation_metadata"


@contextmanager
def database_errors() -> Iterator[None]:
    """Translate driver/connection errors into a 503 with an actionable message."""
    try:
        yield
    except SQLAlchemyError as exc:
        raise DatabaseUnavailableError(
            "The database could not be queried. Check DATABASE_URL and that tables exist (`python -m app.db.init_db`).",
            details={"reason": exc.__class__.__name__},
        ) from exc


def _paginate(db: Session, statement: Select, limit: int, offset: int) -> tuple[list, int]:
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = db.scalars(statement.limit(limit).offset(offset)).all()
    return list(rows), int(total)


def _ensure_loaded(db: Session, model: type, dataset: str) -> None:
    if not db.scalar(select(func.count()).select_from(model)):
        raise DataNotLoadedError([dataset])


def list_compounds(
    db: Session,
    *,
    search: str | None = None,
    cell_line: str | None = None,
    timepoint: float | None = None,
    moa: str | None = None,
    annotated: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> Page[Compound]:
    statement = select(CompoundRecord)
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            or_(CompoundRecord.compound_id.ilike(pattern), CompoundRecord.compound_name.ilike(pattern))
        )
    if cell_line:
        statement = statement.where(func.lower(CompoundRecord.cell_line) == cell_line.strip().lower())
    if timepoint is not None:
        statement = statement.where(CompoundRecord.timepoint == timepoint)
    if moa:
        statement = statement.where(CompoundRecord.moa.ilike(f"%{moa.strip()}%"))
    if annotated is not None:
        has_moa = CompoundRecord.moa.is_not(None) & (CompoundRecord.moa != "")
        statement = statement.where(has_moa if annotated else ~has_moa)
    statement = statement.order_by(CompoundRecord.compound_id, CompoundRecord.cell_line, CompoundRecord.timepoint)
    with database_errors():
        rows, total = _paginate(db, statement, limit, offset)
        if total == 0:
            _ensure_loaded(db, CompoundRecord, COMPOUND_METADATA)
    return Page[Compound](items=[Compound.model_validate(row) for row in rows], total=total, limit=limit, offset=offset)


def get_compound(db: Session, compound_id: str) -> CompoundDetail:
    with database_errors():
        rows = db.scalars(
            select(CompoundRecord)
            .where(CompoundRecord.compound_id == compound_id)
            .order_by(CompoundRecord.cell_line, CompoundRecord.timepoint)
        ).all()
        if not rows:
            _ensure_loaded(db, CompoundRecord, COMPOUND_METADATA)
            raise NotFoundError(f"Compound '{compound_id}' was not found.")
    first = rows[0]
    return CompoundDetail(
        compound_id=first.compound_id,
        compound_name=first.compound_name,
        moa=next((row.moa for row in rows if row.moa), None),
        known_target=next((row.known_target for row in rows if row.known_target), None),
        contexts=[Compound.model_validate(row) for row in rows],
    )


def list_genetic_perturbations(
    db: Session,
    *,
    search: str | None = None,
    perturbation_type: GeneticPerturbationType | None = None,
    cell_line: str | None = None,
    timepoint: float | None = None,
    limit: int = 50,
    offset: int = 0,
) -> Page[GeneticPerturbation]:
    record = GeneticPerturbationRecord
    statement = select(record)
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            or_(record.gene_symbol.ilike(pattern), record.gene_id.ilike(pattern), record.perturbation_id.ilike(pattern))
        )
    if perturbation_type:
        statement = statement.where(record.perturbation_type == perturbation_type.value)
    if cell_line:
        statement = statement.where(func.lower(record.cell_line) == cell_line.strip().lower())
    if timepoint is not None:
        statement = statement.where(record.timepoint == timepoint)
    statement = statement.order_by(record.gene_symbol, record.perturbation_type, record.perturbation_id)
    with database_errors():
        rows, total = _paginate(db, statement, limit, offset)
        if total == 0:
            _ensure_loaded(db, record, GENETIC_METADATA)
    return Page[GeneticPerturbation](
        items=[GeneticPerturbation.model_validate(row) for row in rows], total=total, limit=limit, offset=offset
    )


def get_gene(db: Session, gene_id: str) -> GeneDetail:
    """Look up by gene id, falling back to a case-insensitive gene symbol match."""
    record = GeneticPerturbationRecord
    order = (record.perturbation_type, record.perturbation_id)
    with database_errors():
        rows = db.scalars(select(record).where(record.gene_id == gene_id).order_by(*order)).all()
        if not rows:
            rows = db.scalars(
                select(record).where(func.lower(record.gene_symbol) == gene_id.strip().lower()).order_by(*order)
            ).all()
        if not rows:
            _ensure_loaded(db, record, GENETIC_METADATA)
            raise NotFoundError(f"Gene '{gene_id}' was not found.")
    return GeneDetail(
        gene_id=rows[0].gene_id,
        gene_symbol=rows[0].gene_symbol,
        perturbations=[GeneticPerturbation.model_validate(row) for row in rows],
    )


def compound_annotations(db: Session) -> pd.DataFrame:
    """One row per compound id: ``compound_id, compound_name, moa, known_target``. May be empty."""
    with database_errors():
        rows = db.execute(
            select(
                CompoundRecord.compound_id,
                CompoundRecord.compound_name,
                CompoundRecord.moa,
                CompoundRecord.known_target,
            ).order_by(CompoundRecord.compound_id)
        ).all()
    frame = pd.DataFrame(rows, columns=["compound_id", "compound_name", "moa", "known_target"])
    if frame.empty:
        return frame
    # A compound imported for several contexts keeps the first non-null annotation.
    return frame.groupby("compound_id", as_index=False, sort=True).first()


def perturbation_info(db: Session) -> pd.DataFrame:
    """``perturbation_id, gene_id, gene_symbol, perturbation_type``; raises if nothing is imported."""
    record = GeneticPerturbationRecord
    with database_errors():
        rows = db.execute(
            select(record.perturbation_id, record.gene_id, record.gene_symbol, record.perturbation_type)
        ).all()
    if not rows:
        raise DataNotLoadedError([GENETIC_METADATA])
    frame = pd.DataFrame(rows, columns=["perturbation_id", "gene_id", "gene_symbol", "perturbation_type"])
    return frame.drop_duplicates("perturbation_id").set_index("perturbation_id")


def count_records(db: Session) -> tuple[int, int]:
    with database_errors():
        compounds = db.scalar(select(func.count()).select_from(CompoundRecord)) or 0
        genetic = db.scalar(select(func.count()).select_from(GeneticPerturbationRecord)) or 0
    return int(compounds), int(genetic)
