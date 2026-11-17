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


class PhenotypeMapCell(BaseModel):
    """Root-mean-square change (robust z vs. controls) of one compartment x stain channel."""

    compartment: str
    channel: str
    n_features: int
    rms: float
    mean: float
    top_feature: str | None = None
    top_label: str | None = None
    top_value: float | None = None


class FeatureChange(BaseModel):
    feature: str
    label: str
    value: float


class WellImageRef(BaseModel):
    """A replicate well of the perturbation and the control well used as its display reference."""

    plate: str
    well: str
    control_well: str | None = None


class ImageSourceInfo(BaseModel):
    available: bool
    source: str
    fields: list[int]
    default_field: int
    channels: list[str]
    channel_colors: dict[str, str]
    pixel_size_um: float
    image_size_px: int
    message: str | None = None


class ProfileOverview(BaseModel):
    perturbation_id: str
    profile_type: ProfileType
    name: str | None = None
    gene: str | None = None
    modality: str | None = None
    cell_line: str
    timepoint: float
    n_replicates: int | None = None
    replicate_cosine: float | None = None
    n_features: int
    response_norm: float
    strength_percentile: float | None = Field(
        default=None, description="Share (0-1) of control pseudo-replicates with a weaker profile."
    )
    phenotype_map: list[PhenotypeMapCell]
    top_features: list[FeatureChange]
    wells: list[WellImageRef]
    images: ImageSourceInfo


class MapAgreement(BaseModel):
    compartment: str
    channel: str
    n_features: int
    cosine: float


class ProfileComparison(BaseModel):
    first_id: str
    second_id: str
    cosine: float
    subtract_controls: bool
    cells: list[MapAgreement]


class PlateSummary(BaseModel):
    plate: str
    modality: str | None = None
    cell_line: str | None = None
    timepoint: float | None = None
    n_wells: int
    n_controls: int


class PlateWell(BaseModel):
    well: str
    kind: str = Field(description="compound, crispr, orf or control")
    perturbation_id: str | None = None
    profile_type: ProfileType
    label: str | None = None


class PlateLayout(BaseModel):
    plate: str
    modality: str | None = None
    cell_line: str | None = None
    timepoint: float | None = None
    wells: list[PlateWell]
