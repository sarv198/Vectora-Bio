"""TOML configuration for a preprocessing build."""

import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import resolve_project_path

Modality = Literal["compound", "crispr", "orf"]
MODALITIES: tuple[Modality, ...] = ("compound", "crispr", "orf")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceConfig(_Strict):
    """Where the raw files live and which batch to use."""

    name: str = Field(description="Dataset name recorded in the manifest, e.g. 'cpjump1_u2os'.")
    batch: str = "2020_11_04_CPJUMP1"
    raw_dir: Path = Path("data/raw/cpjump1")
    profile_suffix: str = Field(
        default="augmented",
        description="Per-plate file to read: <plate>_<suffix>.csv.gz. 'augmented' = un-normalized well means.",
    )
    experiment_metadata: str = "experiment-metadata.tsv"
    compound_metadata: str = "JUMP-Target-1_compound_metadata_targets.tsv"
    crispr_metadata: str = "JUMP-Target-1_crispr_metadata.tsv"
    orf_metadata: str = "JUMP-Target-1_orf_metadata.tsv"

    @property
    def raw_path(self) -> Path:
        return resolve_project_path(self.raw_dir)

    def plate_file(self, plate: str) -> Path:
        return self.raw_path / "profiles" / self.batch / plate / f"{plate}_{self.profile_suffix}.csv.gz"

    def metadata_file(self, name: str) -> Path:
        return self.raw_path / "metadata" / name


class SelectionConfig(_Strict):
    """Which plates enter the build. One cell line; one timepoint per modality."""

    cell_type: str = "U2OS"
    timepoints: dict[Modality, float] = Field(
        default_factory=lambda: {"compound": 48.0, "orf": 48.0, "crispr": 144.0},
        description="Hours per modality. Omit a modality to leave it out of the build.",
    )
    density: float | None = 100
    antibiotics: str | None = "absent"
    exclude_anomalies: list[str] = Field(
        default_factory=list, description="Experiment-metadata 'Anomaly' values whose plates are skipped."
    )
    plates: list[str] | None = Field(default=None, description="Explicit plate barcodes; overrides the filters.")

    @field_validator("timepoints")
    @classmethod
    def _positive(cls, value: dict[str, float]) -> dict[str, float]:
        if not value:
            raise ValueError("At least one modality timepoint is required.")
        if any(hours <= 0 for hours in value.values()):
            raise ValueError("Timepoints must be positive hours.")
        return value


class NormalizationConfig(_Strict):
    method: Literal["mad_robustize", "standardize"] = "mad_robustize"
    reference: Literal["negcon", "all"] = Field(
        default="negcon", description="Per-plate reference wells: matched negative controls, or the whole plate."
    )
    epsilon: float = Field(default=1e-6, gt=0)


class FeatureSelectionConfig(_Strict):
    blocklist_patterns: list[str] = Field(
        default_factory=lambda: [
            r"_Location_",
            r"_AreaShape_Center_",
            r"_AreaShape_BoundingBox(Maximum|Minimum)_",
            r"_Number_Object_Number$",
            r"_Parent_",
        ],
        description="Regexes for positional/bookkeeping features that are not morphology.",
    )
    drop_missing: bool = True
    variance_freq_cut: float = Field(default=0.05, ge=0, le=1)
    variance_unique_cut: float = Field(default=0.01, ge=0, le=1)
    correlation_threshold: float | None = Field(default=0.9, gt=0, le=1)


class AggregationConfig(_Strict):
    method: Literal["median", "mean"] = "median"
    min_replicates: int = Field(default=1, ge=1)


class AnnotationConfig(_Strict):
    """Optional external annotation files (paths relative to vectora-bio/ unless absolute)."""

    moa_file: Path | None = Field(default=None, description="e.g. Drug Repurposing Hub drug annotations.")
    moa_key_column: str = "pert_iname"
    moa_match_on: Literal["pert_iname", "inchikey"] = "pert_iname"
    moa_column: str = "moa"
    moa_comment_prefix: str | None = "!"
    gene_id_file: Path | None = Field(default=None, description="Table mapping gene symbol to a stable gene id.")
    gene_symbol_column: str = "symbol"
    gene_id_column: str = "gene_id"


class OutputConfig(_Strict):
    save_well_level: bool = True
    load_database: bool = False


class BuildConfig(_Strict):
    source: SourceConfig
    selection: SelectionConfig = Field(default_factory=SelectionConfig)
    normalization: NormalizationConfig = Field(default_factory=NormalizationConfig)
    feature_selection: FeatureSelectionConfig = Field(default_factory=FeatureSelectionConfig)
    aggregation: AggregationConfig = Field(default_factory=AggregationConfig)
    annotations: AnnotationConfig = Field(default_factory=AnnotationConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)


def load_config(path: str | Path) -> BuildConfig:
    with Path(path).open("rb") as handle:
        return BuildConfig.model_validate(tomllib.load(handle))
