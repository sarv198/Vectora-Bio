"""Health check models."""

from typing import Literal

from pydantic import BaseModel

from app.schemas.profile import DatasetStatus


class DatabaseStatus(BaseModel):
    status: Literal["ok", "unavailable"]
    dialect: str
    message: str | None = None
    compound_count: int | None = None
    genetic_perturbation_count: int | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    app_name: str
    version: str
    environment: str
    database: DatabaseStatus
    datasets: list[DatasetStatus]
