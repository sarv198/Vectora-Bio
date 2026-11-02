"""Evaluation request and response models."""

from pydantic import BaseModel, Field


class EvaluationRequest(BaseModel):
    task: str = Field(min_length=1)


class MetricResult(BaseModel):
    name: str
    value: float
    n: int | None = None


class EvaluationReport(BaseModel):
    task: str
    metrics: list[MetricResult]
