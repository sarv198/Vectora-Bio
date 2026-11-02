"""Analysis request and response models."""

from pydantic import BaseModel, Field


class MechanismRequest(BaseModel):
    values: dict[str, float] = Field(min_length=1)


class MechanismPrediction(BaseModel):
    label: str
    score: float
    supporting_genes: list[str] = Field(default_factory=list)


class RescueRequest(BaseModel):
    values: dict[str, float] = Field(min_length=1)
    reference_id: str = Field(min_length=1)
    query_id: str | None = None


class ReversalScore(BaseModel):
    query_id: str
    reference_id: str
    score: float
    method: str


class SimilarityHit(BaseModel):
    compound_id: str
    score: float
    method: str


class TargetScore(BaseModel):
    symbol: str
    score: float
    evidence: str | None = None
