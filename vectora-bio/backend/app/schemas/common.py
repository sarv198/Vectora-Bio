"""Shared enums and envelope models."""

from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")

# Canonical metadata columns every processed profile table must carry.
PROFILE_METADATA_COLUMNS: tuple[str, ...] = (
    "profile_id",
    "perturbation_id",
    "profile_type",
    "cell_line",
    "timepoint",
)
# Source columns with this prefix are kept as metadata and never treated as features.
EXTRA_METADATA_PREFIX = "Metadata_"


class ProfileType(StrEnum):
    COMPOUND = "compound"
    GENETIC = "genetic"
    CONTROL = "control"


class GeneticPerturbationType(StrEnum):
    CRISPR = "crispr"
    ORF = "orf"
    SIRNA = "sirna"


class PredictionType(StrEnum):
    COMPOUND_SIMILARITY = "compound_similarity"
    COMPOUND_GENE_MATCHING = "compound_gene_matching"
    TARGET_PRIORITIZATION = "target_prioritization"
    MOA_INFERENCE = "moa_inference"
    PHENOTYPIC_RESCUE = "phenotypic_rescue"


class DatasetSplit(StrEnum):
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"
    ALL = "all"


class ErrorResponse(BaseModel):
    error: str = Field(description="Machine-readable error code, e.g. 'data_not_loaded'.")
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


# Responses shared by every router that reads imported data.
DATA_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    503: {"model": ErrorResponse, "description": "Required data or database is not available."},
}
ANALYSIS_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    **DATA_ERROR_RESPONSES,
    400: {"model": ErrorResponse, "description": "Query cannot be answered as posed (e.g. ambiguous context)."},
    404: {"model": ErrorResponse, "description": "Query compound or perturbation has no profile."},
    409: {"model": ErrorResponse, "description": "Profile datasets have incompatible feature sets."},
}
