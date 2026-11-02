"""Profile and dataset models."""

import math

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ProfileType


class Profile(BaseModel):
    """One cellular phenotypic profile: metadata plus a vector of named features."""

    profile_id: str = Field(min_length=1)
    perturbation_id: str = Field(min_length=1)
    profile_type: ProfileType
    cell_line: str = Field(min_length=1)
    timepoint: float = Field(gt=0, description="Hours after perturbation.")
    feature_values: dict[str, float] = Field(min_length=1)

    @field_validator("feature_values")
    @classmethod
    def _finite_features(cls, values: dict[str, float]) -> dict[str, float]:
        bad = [name for name, value in values.items() if not math.isfinite(value)]
        if bad:
            preview = ", ".join(bad[:5])
            raise ValueError(f"{len(bad)} feature value(s) are missing or not finite: {preview}")
        return values


class DatasetStatus(BaseModel):
    name: str
    profile_type: ProfileType
    path: str
    available: bool
    n_rows: int | None = None
    n_features: int | None = None
    message: str | None = None
