"""Relational records: perturbation metadata, dataset registry, analysis runs, evaluations.

High-dimensional feature vectors stay in Parquet. These tables hold only metadata,
provenance, and results.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


class CompoundRecord(Base):
    __tablename__ = "compounds"
    __table_args__ = (UniqueConstraint("compound_id", "cell_line", "timepoint", name="uq_compound_context"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    compound_id: Mapped[str] = mapped_column(String(128), index=True)
    compound_name: Mapped[str] = mapped_column(String(512), index=True)
    moa: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    known_target: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    cell_line: Mapped[str] = mapped_column(String(128), index=True)
    timepoint: Mapped[float] = mapped_column(Float)
    replicate_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GeneticPerturbationRecord(Base):
    __tablename__ = "genetic_perturbations"
    __table_args__ = (UniqueConstraint("perturbation_id", "cell_line", "timepoint", name="uq_genetic_context"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    perturbation_id: Mapped[str] = mapped_column(String(128), index=True)
    gene_id: Mapped[str] = mapped_column(String(64), index=True)
    gene_symbol: Mapped[str] = mapped_column(String(64), index=True)
    perturbation_type: Mapped[str] = mapped_column(String(16), index=True)
    cell_line: Mapped[str] = mapped_column(String(128), index=True)
    timepoint: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProfileDatasetRecord(Base):
    """Provenance for each imported Parquet profile file."""

    __tablename__ = "profile_datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_type: Mapped[str] = mapped_column(String(16), unique=True)
    file_path: Mapped[str] = mapped_column(Text)
    source_path: Mapped[str] = mapped_column(Text)
    n_profiles: Mapped[int] = mapped_column(Integer)
    n_features: Mapped[int] = mapped_column(Integer)
    feature_hash: Mapped[str] = mapped_column(String(64))
    cell_lines: Mapped[list[str]] = mapped_column(JSONType)
    timepoints: Mapped[list[float]] = mapped_column(JSONType)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AnalysisRunRecord(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prediction_type: Mapped[str] = mapped_column(String(32), index=True)
    query_id: Mapped[str] = mapped_column(String(128), index=True)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    predictions: Mapped[list["PredictionRecord"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="PredictionRecord.rank"
    )


class PredictionRecord(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True)
    query_id: Mapped[str] = mapped_column(String(128), index=True)
    candidate_id: Mapped[str] = mapped_column(String(128), index=True)
    prediction_type: Mapped[str] = mapped_column(String(32))
    score: Mapped[float] = mapped_column(Float)
    rank: Mapped[int] = mapped_column(Integer)
    supporting_evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSONType)

    run: Mapped[AnalysisRunRecord] = relationship(back_populates="predictions")


class EvaluationResultRecord(Base):
    __tablename__ = "evaluation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    metric_name: Mapped[str] = mapped_column(String(128), index=True)
    metric_value: Mapped[float] = mapped_column(Float)
    evaluation_method: Mapped[str] = mapped_column(String(256))
    dataset_split: Mapped[str] = mapped_column(String(16))
    sample_count: Mapped[int] = mapped_column(Integer)
    parameters: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
