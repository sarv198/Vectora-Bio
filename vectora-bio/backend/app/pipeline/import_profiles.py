"""Import a locally downloaded profile table into the processed Parquet store.

Example (JUMP compound profiles, after downloading them yourself)::

    python -m app.pipeline.import_profiles \\
        --input ../data/raw/compound_profiles.parquet \\
        --profile-type compound \\
        --column-map config/jump_column_map.example.json \\
        --set cell_line=U2OS --set timepoint=48 \\
        --profile-id-columns Metadata_Source Metadata_Plate Metadata_Well

The table is renamed to canonical columns, validated, checked for feature compatibility
with any previously imported profile types, written to the configured Parquet path,
and registered in the ``profile_datasets`` table.
"""

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings, get_settings
from app.data.loaders import (
    check_feature_compatibility,
    feature_hash,
    filter_profiles,
    identify_feature_columns,
    is_metadata_column,
    read_table,
    validate_profile_table,
)
from app.data.profile_store import dataset_name
from app.db.models import ProfileDatasetRecord
from app.db.session import get_session_factory, init_db
from app.errors import FeatureMismatchError, VectoraError
from app.pipeline.common import (
    apply_column_map,
    apply_constants,
    load_column_map,
    parse_assignments,
    write_parquet_atomic,
)
from app.schemas.common import PROFILE_METADATA_COLUMNS, ProfileType

MissingStrategy = Literal["error", "drop-features", "drop-rows"]


@dataclass
class ImportSummary:
    profile_type: str
    source_path: str
    output_path: str
    n_profiles: int
    n_perturbations: int
    n_features: int
    contexts: list[dict]
    dropped_features: list[str] = field(default_factory=list)
    dropped_rows: int = 0
    warnings: list[str] = field(default_factory=list)
    registered: bool = False
    dry_run: bool = False


def prepare_profiles(
    frame: pd.DataFrame,
    profile_type: ProfileType,
    *,
    column_map: dict[str, str] | None = None,
    constants: dict[str, object] | None = None,
    profile_id_columns: list[str] | None = None,
    drop_columns: list[str] | None = None,
) -> pd.DataFrame:
    """Rename and complete metadata so the table follows the canonical profile layout."""
    frame = apply_column_map(frame, column_map or {})
    if drop_columns:
        frame = frame.drop(columns=[column for column in drop_columns if column in frame.columns])
    frame = apply_constants(frame, constants or {})
    if "profile_type" not in frame.columns:
        frame = frame.assign(profile_type=profile_type.value)
    if "profile_id" not in frame.columns:
        if not profile_id_columns:
            raise ValueError(
                "The input has no 'profile_id' column. Map one with --column-map or build it with --profile-id-columns."
            )
        missing = [column for column in profile_id_columns if column not in frame.columns]
        if missing:
            raise ValueError(f"--profile-id-columns not found in input: {missing}.")
        frame = frame.assign(profile_id=frame[profile_id_columns].astype(str).agg(":".join, axis=1))
    for column in ("profile_id", "perturbation_id", "cell_line"):
        if column in frame.columns:
            frame[column] = frame[column].where(frame[column].isna(), frame[column].astype(str).str.strip())
    if "timepoint" in frame.columns:
        frame["timepoint"] = pd.to_numeric(frame["timepoint"], errors="coerce")
    return frame


def restrict_features(frame: pd.DataFrame, feature_list: list[str]) -> pd.DataFrame:
    """Keep only the listed features (in that order). Every listed feature must be present."""
    missing = [feature for feature in feature_list if feature not in frame.columns]
    if missing:
        raise FeatureMismatchError(
            f"{len(missing)} listed feature(s) are absent from the input.",
            details={"missing_features": missing[:20]},
        )
    metadata = [column for column in frame.columns if is_metadata_column(str(column))]
    return frame[metadata + feature_list]


def handle_missing_features(frame: pd.DataFrame, strategy: MissingStrategy) -> tuple[pd.DataFrame, list[str], int]:
    """Apply the missing-value strategy. Returns the frame, dropped features, and dropped row count."""
    if strategy == "error":
        return frame, [], 0
    features = identify_feature_columns(frame)
    numeric = frame[features].apply(pd.to_numeric, errors="coerce")
    invalid = ~np.isfinite(numeric.to_numpy(dtype=np.float64))
    if strategy == "drop-features":
        dropped = [features[i] for i in np.flatnonzero(invalid.any(axis=0))]
        return frame.drop(columns=dropped), dropped, 0
    keep = ~invalid.any(axis=1)
    return frame.loc[keep].reset_index(drop=True), [], int((~keep).sum())


def existing_feature_sets(settings: Settings, exclude: ProfileType) -> dict[str, list[str]]:
    paths = {
        ProfileType.COMPOUND: settings.compound_profiles_path,
        ProfileType.GENETIC: settings.genetic_profiles_path,
        ProfileType.CONTROL: settings.control_profiles_path,
    }
    feature_sets = {}
    for profile_type, path in paths.items():
        if profile_type != exclude and path.is_file():
            names = pq.ParquetFile(path).schema_arrow.names
            feature_sets[dataset_name(profile_type)] = [name for name in names if not is_metadata_column(name)]
    return feature_sets


def import_profiles(
    input_path: str | Path,
    profile_type: ProfileType,
    *,
    settings: Settings | None = None,
    column_map: dict[str, str] | None = None,
    constants: dict[str, object] | None = None,
    profile_id_columns: list[str] | None = None,
    drop_columns: list[str] | None = None,
    feature_list: list[str] | None = None,
    cell_line: str | None = None,
    timepoint: float | None = None,
    missing: MissingStrategy = "error",
    allow_feature_mismatch: bool = False,
    register: bool = True,
    dry_run: bool = False,
) -> ImportSummary:
    settings = settings or get_settings()
    frame = read_table(input_path)
    frame = prepare_profiles(
        frame,
        profile_type,
        column_map=column_map,
        constants=constants,
        profile_id_columns=profile_id_columns,
        drop_columns=drop_columns,
    )
    if cell_line is not None or timepoint is not None:
        frame = filter_profiles(frame, cell_line=cell_line, timepoint=timepoint).reset_index(drop=True)
    if feature_list:
        frame = restrict_features(frame, feature_list)
    frame, dropped_features, dropped_rows = handle_missing_features(frame, missing)

    report = validate_profile_table(frame, expected_profile_type=profile_type)
    report.raise_if_invalid(f"{profile_type.value} profiles from {Path(input_path).name}")
    features = identify_feature_columns(frame)

    others = existing_feature_sets(settings, exclude=profile_type)
    warnings = [issue.message for issue in report.warnings]
    if others:
        compatibility = check_feature_compatibility({dataset_name(profile_type): features, **others})
        if not compatibility.compatible:
            if not allow_feature_mismatch:
                raise FeatureMismatchError(
                    "Features differ from already imported profile datasets. Use --feature-list to restrict "
                    "every dataset to a shared feature set, or --allow-feature-mismatch to import anyway.",
                    details=compatibility.to_dict(),
                )
            warnings.append(f"Feature sets differ from existing datasets: {compatibility.to_dict()['missing_counts']}")

    metadata_columns = [column for column in frame.columns if is_metadata_column(str(column))]
    ordered = [*PROFILE_METADATA_COLUMNS, *[c for c in metadata_columns if c not in PROFILE_METADATA_COLUMNS]]
    output = frame[ordered + features].copy()
    output[features] = output[features].astype(np.float32)

    contexts = (
        output.groupby(["cell_line", "timepoint"])
        .agg(n_profiles=("profile_id", "size"), n_perturbations=("perturbation_id", "nunique"))
        .reset_index()
        .to_dict(orient="records")
    )
    output_path = {
        ProfileType.COMPOUND: settings.compound_profiles_path,
        ProfileType.GENETIC: settings.genetic_profiles_path,
        ProfileType.CONTROL: settings.control_profiles_path,
    }[profile_type]
    summary = ImportSummary(
        profile_type=profile_type.value,
        source_path=str(Path(input_path).resolve()),
        output_path=str(output_path),
        n_profiles=len(output),
        n_perturbations=int(output["perturbation_id"].nunique()),
        n_features=len(features),
        contexts=contexts,
        dropped_features=dropped_features,
        dropped_rows=dropped_rows,
        warnings=warnings,
        dry_run=dry_run,
    )
    if dry_run:
        return summary

    write_parquet_atomic(output, output_path)
    if register:
        summary.registered = register_dataset(
            summary.profile_type, summary.output_path, summary.source_path, output, features
        )
        if not summary.registered:
            summary.warnings.append("Profiles were written but could not be registered in the database.")
    return summary


def register_dataset(
    profile_type: str, output_path: str, source_path: str, frame: pd.DataFrame, features: list[str]
) -> bool:
    """Record (or update) the provenance row for one profile type. Returns False if the database is unusable."""
    try:
        init_db()
        with get_session_factory()() as db:
            record = db.scalar(select(ProfileDatasetRecord).where(ProfileDatasetRecord.profile_type == profile_type))
            record = record or ProfileDatasetRecord(profile_type=profile_type)
            record.file_path = output_path
            record.source_path = source_path
            record.n_profiles = len(frame)
            record.n_features = len(features)
            record.feature_hash = feature_hash(features)
            record.cell_lines = sorted(frame["cell_line"].astype(str).unique().tolist())
            record.timepoints = sorted(float(t) for t in frame["timepoint"].unique())
            db.add(record)
            db.commit()
        return True
    except SQLAlchemyError:
        return False


def _read_feature_list(path: str | None) -> list[str] | None:
    if path is None:
        return None
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True, help="Parquet/CSV/TSV file with one row per profile.")
    parser.add_argument("--profile-type", required=True, choices=[t.value for t in ProfileType])
    parser.add_argument("--column-map", help="JSON object mapping source columns to canonical columns.")
    parser.add_argument("--set", action="append", metavar="COLUMN=VALUE", help="Constant column, e.g. cell_line=U2OS.")
    parser.add_argument("--profile-id-columns", nargs="+", help="Columns joined with ':' to build profile_id.")
    parser.add_argument("--drop-columns", nargs="+", help="Non-feature columns to discard before validation.")
    parser.add_argument("--feature-list", help="Text file with one feature name per line to keep.")
    parser.add_argument("--cell-line", help="Import only this cell line.")
    parser.add_argument("--timepoint", type=float, help="Import only this timepoint (hours).")
    parser.add_argument(
        "--missing",
        choices=["error", "drop-features", "drop-rows"],
        default="error",
        help="How to handle missing/non-finite feature values (default: fail validation).",
    )
    parser.add_argument("--allow-feature-mismatch", action="store_true")
    parser.add_argument("--no-register", action="store_true", help="Do not record the import in the database.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and summarize without writing.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        summary = import_profiles(
            args.input,
            ProfileType(args.profile_type),
            column_map=load_column_map(args.column_map),
            constants=parse_assignments(args.set),
            profile_id_columns=args.profile_id_columns,
            drop_columns=args.drop_columns,
            feature_list=_read_feature_list(args.feature_list),
            cell_line=args.cell_line,
            timepoint=args.timepoint,
            missing=args.missing,
            allow_feature_mismatch=args.allow_feature_mismatch,
            register=not args.no_register,
            dry_run=args.dry_run,
        )
    except VectoraError as exc:
        print(f"Import failed: {exc.message}", file=sys.stderr)
        print(json.dumps(exc.details, indent=2, default=str), file=sys.stderr)
        return 1
    except (FileNotFoundError, ValueError) as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(asdict(summary), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
