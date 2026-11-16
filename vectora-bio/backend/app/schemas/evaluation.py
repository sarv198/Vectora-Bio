"""Evaluation models."""

import math
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import DatasetSplit


class Evaluation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    metric_name: str = Field(min_length=1, max_length=128)
    metric_value: float
    evaluation_method: str = Field(min_length=1, max_length=256)
    dataset_split: DatasetSplit
    sample_count: int = Field(ge=0)

    @field_validator("metric_value")
    @classmethod
    def _finite_value(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("metric_value must be finite")
        return value


class EvaluationRecord(Evaluation):
    id: int
    parameters: dict[str, Any] | None = None
    created_at: datetime | None = None


class EvaluationListResponse(BaseModel):
    results: list[EvaluationRecord]
    message: str | None = None


class EvaluationRunRequest(BaseModel):
    """Settings for a held-out benchmark run."""

    cell_line: str | None = None
    timepoint: float | None = Field(default=None, gt=0)
    split_strategies: list[Literal["random", "target_group"]] = Field(
        default_factory=lambda: ["random", "target_group"],
        min_length=1,
        description="'target_group' keeps compounds that share a designed target in the same fold.",
    )
    n_folds: int = Field(default=5, ge=2, le=20)
    seed: int = 0
    k: int = Field(default=10, ge=1, le=100)
    n_neighbors: int = Field(default=10, ge=1, le=100)
    neighbor_weight: float = Field(default=2.0, ge=0)
    n_permutations: int = Field(default=20, ge=1, le=200, description="Random orderings for ranking baselines.")


class EvaluationRunResponse(BaseModel):
    run_id: str
    results: list[EvaluationRecord]
    audit: dict[str, Any]
    notes: list[str] = Field(default_factory=list)
