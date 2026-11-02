"""Prediction models and analysis request/response bodies."""

import math
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import GeneticPerturbationType, PredictionType


class EvidenceItem(BaseModel):
    """One interpretable piece of support for a prediction."""

    evidence_type: str = Field(description="e.g. 'phenotypic_similarity', 'neighbor_annotation', 'annotation'.")
    description: str
    value: float | None = None
    source_id: str | None = Field(default=None, description="Compound, perturbation, or record the evidence refers to.")


class Prediction(BaseModel):
    query_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    prediction_type: PredictionType
    score: float
    rank: int = Field(ge=1)
    supporting_evidence: list[EvidenceItem] = Field(default_factory=list)

    @field_validator("score")
    @classmethod
    def _finite_score(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("score must be finite")
        return value


class ContextFilter(BaseModel):
    cell_line: str | None = Field(default=None, description="Restrict profiles to this cell line.")
    timepoint: float | None = Field(default=None, gt=0, description="Restrict profiles to this timepoint (hours).")


class SimilarityRequest(ContextFilter):
    compound_id: str = Field(min_length=1)
    top_k: int = Field(default=10, ge=1)


class TargetPrioritizationRequest(ContextFilter):
    compound_id: str = Field(min_length=1)
    genetic_timepoint: float | None = Field(
        default=None,
        gt=0,
        description="Timepoint for genetic profiles. Genetic screens often use a different timepoint than compounds.",
    )
    perturbation_types: list[GeneticPerturbationType] | None = None
    use_absolute_similarity: bool = Field(
        default=True,
        description="Rank by |cosine| so anti-correlated perturbations (e.g. overexpression) are also surfaced.",
    )
    top_k: int = Field(default=10, ge=1)


class MoaInferenceRequest(ContextFilter):
    compound_id: str = Field(min_length=1)
    n_neighbors: int = Field(default=20, ge=1, description="Number of most similar compounds that vote.")
    top_k: int = Field(default=5, ge=1)


class RescueSearchRequest(ContextFilter):
    perturbation_id: str | None = Field(
        default=None, description="Genetic perturbation whose phenotype should be reversed."
    )
    signature: dict[str, float] | None = Field(
        default=None, description="Custom perturbation signature keyed by feature name."
    )
    perturbation_timepoint: float | None = Field(default=None, gt=0)
    subtract_matched_controls: bool = Field(
        default=True,
        description="Subtract the matched control consensus (same cell line and timepoint) before scoring.",
    )
    top_k: int = Field(default=10, ge=1)

    @model_validator(mode="after")
    def _one_signature_source(self) -> "RescueSearchRequest":
        if (self.perturbation_id is None) == (self.signature is None):
            raise ValueError("Provide exactly one of 'perturbation_id' or 'signature'.")
        if self.signature is not None and not self.signature:
            raise ValueError("'signature' must contain at least one feature.")
        return self


class AnalysisSummary(BaseModel):
    n_candidates: int = Field(ge=0)
    n_features: int = Field(ge=0)
    cell_line: str | None = None
    timepoint: float | None = None


class AnalysisResponse(BaseModel):
    query_id: str
    prediction_type: PredictionType
    predictions: list[Prediction]
    parameters: dict[str, Any] = Field(default_factory=dict)
    summary: AnalysisSummary
    message: str | None = None
    run_id: int | None = Field(
        default=None, description="Id of the persisted analysis run, when persistence is enabled."
    )
