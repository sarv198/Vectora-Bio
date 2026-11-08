"""Read, validate, filter, and aggregate cellular profile tables.

A profile table is wide: one row per profile (typically one well), the canonical
metadata columns in ``PROFILE_METADATA_COLUMNS``, optional ``Metadata_*`` columns,
and one numeric column per morphological feature.
"""

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from app.errors import ProfileValidationError
from app.schemas.common import EXTRA_METADATA_PREFIX, PROFILE_METADATA_COLUMNS, ProfileType

REPLICATE_COUNT_COLUMN = "Metadata_n_replicates"
SUPPORTED_SUFFIXES = (".parquet", ".pq", ".csv", ".csv.gz", ".tsv", ".tsv.gz")
_ISSUE_PREVIEW = 10


def read_table(path: str | Path) -> pd.DataFrame:
    """Read a Parquet, CSV, or TSV file (optionally gzipped) into a DataFrame."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    name = path.name.lower()
    if name.endswith((".parquet", ".pq")):
        return pd.read_parquet(path)
    if name.endswith((".csv", ".csv.gz")):
        return pd.read_csv(path, low_memory=False)
    if name.endswith((".tsv", ".tsv.gz")):
        return pd.read_csv(path, sep="\t", low_memory=False)
    raise ValueError(f"Unsupported file type for {path.name}. Expected one of: {', '.join(SUPPORTED_SUFFIXES)}")


def is_metadata_column(column: str) -> bool:
    return column in PROFILE_METADATA_COLUMNS or column.startswith(EXTRA_METADATA_PREFIX)


def identify_feature_columns(frame: pd.DataFrame) -> list[str]:
    """Columns that are neither canonical metadata nor ``Metadata_*``, in file order."""
    return [str(column) for column in frame.columns if not is_metadata_column(str(column))]


def feature_hash(feature_columns: Iterable[str]) -> str:
    """Order-independent fingerprint of a feature set, used to compare datasets."""
    joined = "\n".join(sorted(feature_columns))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ValidationIssue:
    level: Literal["error", "warning"]
    code: str
    message: str
    examples: list[str] = field(default_factory=list)


@dataclass
class ValidationReport:
    n_rows: int
    n_features: int
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.level == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.level == "warning"]

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def add(self, level: Literal["error", "warning"], code: str, message: str, examples: Iterable[object] = ()) -> None:
        preview = [str(example) for example in list(examples)[:_ISSUE_PREVIEW]]
        self.issues.append(ValidationIssue(level=level, code=code, message=message, examples=preview))

    def to_dict(self) -> dict:
        return {
            "n_rows": self.n_rows,
            "n_features": self.n_features,
            "issues": [issue.__dict__ for issue in self.issues],
        }

    def raise_if_invalid(self, context: str = "Profile table") -> None:
        if not self.is_valid:
            summary = "; ".join(issue.message for issue in self.errors)
            raise ProfileValidationError(f"{context} failed validation: {summary}", details=self.to_dict())


def validate_profile_table(
    frame: pd.DataFrame,
    expected_profile_type: ProfileType | str | None = None,
) -> ValidationReport:
    """Check metadata, identifiers, and feature values. Never mutates ``frame``.

    Errors: missing metadata columns, missing metadata values, non-positive or
    non-numeric timepoints, unexpected profile types, duplicate profile ids,
    no features, non-numeric features, missing or non-finite feature values,
    and zero-norm profiles (cosine similarity is undefined for them).
    Warnings: constant features, and zero-norm profiles when validating control profiles.
    """
    features = identify_feature_columns(frame)
    report = ValidationReport(n_rows=len(frame), n_features=len(features))

    if frame.empty:
        report.add("error", "empty_table", "The table has no rows.")
        return report

    missing_columns = [column for column in PROFILE_METADATA_COLUMNS if column not in frame.columns]
    if missing_columns:
        report.add(
            "error",
            "missing_metadata_columns",
            f"Missing required metadata column(s): {', '.join(missing_columns)}.",
            missing_columns,
        )

    for column in PROFILE_METADATA_COLUMNS:
        if column not in frame.columns:
            continue
        values = frame[column]
        blank = values.isna() | (values.astype(str).str.strip() == "")
        if blank.any():
            report.add(
                "error",
                "missing_metadata_values",
                f"Column '{column}' has {int(blank.sum())} missing value(s).",
                frame.index[blank],
            )

    if "timepoint" in frame.columns:
        numeric = pd.to_numeric(frame["timepoint"], errors="coerce")
        bad = frame["timepoint"].notna() & (numeric.isna() | (numeric <= 0))
        if bad.any():
            report.add(
                "error",
                "invalid_timepoint",
                f"{int(bad.sum())} timepoint value(s) are not positive numbers (hours).",
                frame.loc[bad, "timepoint"].unique(),
            )

    if "profile_type" in frame.columns:
        allowed = {member.value for member in ProfileType}
        observed = set(frame["profile_type"].dropna().astype(str).unique())
        unknown = observed - allowed
        if unknown:
            report.add(
                "error",
                "unknown_profile_type",
                f"Unknown profile_type value(s); expected one of {sorted(allowed)}.",
                sorted(unknown),
            )
        if expected_profile_type is not None:
            expected = ProfileType(expected_profile_type).value
            other = observed - {expected} - unknown
            if other:
                report.add(
                    "error",
                    "unexpected_profile_type",
                    f"Expected only '{expected}' profiles but found {sorted(other)}.",
                    sorted(other),
                )

    if "profile_id" in frame.columns:
        duplicated = frame["profile_id"].duplicated(keep=False) & frame["profile_id"].notna()
        if duplicated.any():
            report.add(
                "error",
                "duplicate_profile_ids",
                f"{int(frame.loc[duplicated, 'profile_id'].nunique())} profile_id value(s) occur more than once.",
                frame.loc[duplicated, "profile_id"].unique(),
            )

    if not features:
        report.add("error", "no_features", "No feature columns found (all columns are metadata).")
        return report

    non_numeric = [column for column in features if not pd.api.types.is_numeric_dtype(frame[column])]
    if non_numeric:
        report.add(
            "error",
            "non_numeric_features",
            f"{len(non_numeric)} feature column(s) are not numeric. Rename true metadata with a "
            f"'{EXTRA_METADATA_PREFIX}' prefix or drop them.",
            non_numeric,
        )
    numeric_features = [column for column in features if column not in non_numeric]
    if not numeric_features:
        return report

    values = frame[numeric_features].to_numpy(dtype=np.float64)
    missing = np.isnan(values)
    if missing.any():
        columns_with_missing = [numeric_features[i] for i in np.flatnonzero(missing.any(axis=0))]
        report.add(
            "error",
            "missing_feature_values",
            f"{int(missing.sum())} missing feature value(s) across {len(columns_with_missing)} column(s) "
            f"and {int(missing.any(axis=1).sum())} row(s).",
            columns_with_missing,
        )
    infinite = np.isinf(values)
    if infinite.any():
        report.add(
            "error",
            "non_finite_feature_values",
            f"{int(infinite.sum())} feature value(s) are infinite.",
            [numeric_features[i] for i in np.flatnonzero(infinite.any(axis=0))],
        )

    finite_values = np.where(np.isfinite(values), values, 0.0)
    zero_norm = np.linalg.norm(finite_values, axis=1) == 0
    if zero_norm.any():
        ids = frame["profile_id"] if "profile_id" in frame.columns else pd.Series(frame.index)
        # Control consensus profiles can legitimately be ~0 after normalizing to controls; they are
        # subtracted, never compared by cosine, so this is only a warning for them.
        is_control = expected_profile_type is not None and ProfileType(expected_profile_type) == ProfileType.CONTROL
        report.add(
            "warning" if is_control else "error",
            "zero_norm_profiles",
            f"{int(zero_norm.sum())} profile(s) have an all-zero feature vector.",
            ids.to_numpy()[zero_norm],
        )

    if len(frame) > 1:
        constant = np.nanstd(np.where(np.isfinite(values), values, np.nan), axis=0) == 0
        if constant.any():
            report.add(
                "warning",
                "constant_features",
                f"{int(constant.sum())} feature column(s) are constant and carry no information.",
                [numeric_features[i] for i in np.flatnonzero(constant)],
            )

    return report


@dataclass(frozen=True)
class FeatureCompatibilityReport:
    compatible: bool
    n_shared_features: int
    missing_by_dataset: dict[str, list[str]]

    def to_dict(self) -> dict:
        return {
            "compatible": self.compatible,
            "n_shared_features": self.n_shared_features,
            "missing_by_dataset": {name: missing[:_ISSUE_PREVIEW] for name, missing in self.missing_by_dataset.items()},
            "missing_counts": {name: len(missing) for name, missing in self.missing_by_dataset.items()},
        }


def check_feature_compatibility(
    datasets: Mapping[str, pd.DataFrame | Sequence[str]],
) -> FeatureCompatibilityReport:
    """Compare feature sets across datasets. Compatible means identical sets (order may differ).

    Values may be DataFrames (features are detected) or explicit feature-name sequences.
    """
    if len(datasets) < 2:
        raise ValueError("At least two datasets are required to check compatibility.")
    feature_sets: dict[str, set[str]] = {}
    for name, value in datasets.items():
        columns = identify_feature_columns(value) if isinstance(value, pd.DataFrame) else list(value)
        feature_sets[name] = set(columns)
    union = set().union(*feature_sets.values())
    shared = set.intersection(*feature_sets.values())
    missing = {name: sorted(union - features) for name, features in feature_sets.items()}
    return FeatureCompatibilityReport(
        compatible=all(not names for names in missing.values()),
        n_shared_features=len(shared),
        missing_by_dataset=missing,
    )


def filter_profiles(
    frame: pd.DataFrame,
    cell_line: str | None = None,
    timepoint: float | None = None,
) -> pd.DataFrame:
    """Rows matching the given cell line (case-insensitive) and timepoint. ``None`` means no filter."""
    mask = pd.Series(True, index=frame.index)
    if cell_line is not None:
        mask &= frame["cell_line"].astype(str).str.casefold() == cell_line.strip().casefold()
    if timepoint is not None:
        mask &= np.isclose(pd.to_numeric(frame["timepoint"], errors="coerce"), float(timepoint))
    return frame.loc[mask]


def available_contexts(frame: pd.DataFrame) -> list[dict[str, object]]:
    """Distinct (cell_line, timepoint) pairs with profile counts."""
    if frame.empty:
        return []
    counts = frame.groupby(["cell_line", "timepoint"], sort=True).size()
    return [
        {"cell_line": str(cell_line), "timepoint": float(timepoint), "n_profiles": int(count)}
        for (cell_line, timepoint), count in counts.items()
    ]


@dataclass(frozen=True)
class ConsensusProfiles:
    """Replicate-aggregated profiles. ``features`` and ``context`` share a ``perturbation_id`` index."""

    features: pd.DataFrame
    context: pd.DataFrame

    @property
    def feature_columns(self) -> list[str]:
        return list(self.features.columns)

    def __len__(self) -> int:
        return len(self.features)


class AmbiguousContextError(ValueError):
    def __init__(self, perturbation_ids: list[str]) -> None:
        preview = ", ".join(perturbation_ids[:_ISSUE_PREVIEW])
        super().__init__(
            f"{len(perturbation_ids)} perturbation(s) have profiles in more than one cell line/timepoint "
            f"({preview}). Specify cell_line and timepoint."
        )
        self.perturbation_ids = perturbation_ids


def build_consensus_profiles(
    frame: pd.DataFrame,
    feature_columns: Sequence[str] | None = None,
    method: Literal["median", "mean"] = "median",
) -> ConsensusProfiles:
    """Aggregate replicate profiles to one vector per ``perturbation_id``.

    Raises ``AmbiguousContextError`` if a perturbation appears in more than one
    (cell_line, timepoint) context, because pooling across contexts would mix phenotypes.
    """
    if method not in ("median", "mean"):
        raise ValueError(f"Unsupported consensus method: {method}")
    features = list(feature_columns) if feature_columns is not None else identify_feature_columns(frame)
    if frame.empty:
        empty = pd.DataFrame(columns=features, dtype=np.float64)
        empty.index.name = "perturbation_id"
        context = pd.DataFrame(columns=["cell_line", "timepoint", "replicate_count"])
        context.index.name = "perturbation_id"
        return ConsensusProfiles(features=empty, context=context)

    n_contexts = frame.groupby("perturbation_id")[["cell_line", "timepoint"]].nunique().max(axis=1)
    ambiguous = n_contexts[n_contexts > 1].index.astype(str).tolist()
    if ambiguous:
        raise AmbiguousContextError(ambiguous)

    grouped = frame.groupby("perturbation_id", sort=True)
    consensus = grouped[features].median() if method == "median" else grouped[features].mean()
    context = grouped.agg(
        cell_line=("cell_line", "first"),
        timepoint=("timepoint", "first"),
        replicate_count=("profile_id", "size"),
    )
    if REPLICATE_COUNT_COLUMN in frame.columns:
        # Rows are already consensus profiles (e.g. from the build pipeline); count the wells behind them.
        context["replicate_count"] = grouped[REPLICATE_COUNT_COLUMN].sum().astype(int)
    consensus.index = consensus.index.astype(str)
    context.index = context.index.astype(str)
    return ConsensusProfiles(features=consensus.astype(np.float64), context=context)
