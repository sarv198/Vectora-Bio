"""Evaluation models."""

import math
from datetime import datetime
from typing import Any

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
