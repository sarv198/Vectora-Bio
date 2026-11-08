"""Phase 1 build: selected raw plates -> processed Parquet profiles, metadata, and a manifest.

Outputs (paths from ``Settings``):
    profiles/{compound,genetic,control}_profiles.parquet   consensus profiles, one row per perturbation + context
    metadata/{compound,genetic}_metadata.parquet           annotations aligned with the profiles
    wells/{compound,genetic,control}_wells.parquet          normalized, feature-selected well-level profiles
    build/manifest.json, build/selected_features.txt       provenance
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import Settings, get_settings
from app.data.loaders import check_feature_compatibility, validate_profile_table
from app.errors import FeatureMismatchError
from app.pipeline.common import write_parquet_atomic
from app.preprocessing import sources
from app.preprocessing.aggregate import aggregate_replicates
from app.preprocessing.annotations import AnnotationReport, build_compound_metadata, build_genetic_metadata
from app.preprocessing.config import BuildConfig
from app.preprocessing.feature_selection import select_features
from app.preprocessing.normalize import normalize_by_plate
from app.schemas.common import PROFILE_METADATA_COLUMNS, ProfileType

PIPELINE_VERSION = "1"
# Per-well bookkeeping that is meaningless after aggregation.
_DROP_AFTER_AGGREGATION = ["Metadata_Plate", "Metadata_Well", "Metadata_is_negcon", "Metadata_anomaly"]


@dataclass
class BuildSummary:
    dataset: str
    n_plates: int
    n_wells: int
    n_features_raw: int
    n_features_selected: int
    outputs: dict[str, dict] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    manifest_path: str = ""
    database_loaded: bool = False


def _profile_table(consensus: pd.DataFrame, profile_type: ProfileType, features: list[str]) -> pd.DataFrame:
    """Canonical profile layout expected by the API (see docs/data_dictionary.md)."""
    table = consensus.drop(columns=[c for c in _DROP_AFTER_AGGREGATION if c in consensus.columns])
    table = table.assign(
        profile_type=profile_type.value,
        profile_id=table["perturbation_id"].astype(str)
        + ":"
        + table["cell_line"].astype(str)
        + ":"
        + table["timepoint"].map(lambda hours: f"{hours:g}h"),
    )
    extra = sorted(c for c in table.columns if c.startswith("Metadata_"))
    table = table[[*PROFILE_METADATA_COLUMNS, *extra, *features]].copy()
    table[features] = table[features].astype(np.float32)
    return table


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_dataset(config: BuildConfig, settings: Settings | None = None, *, dry_run: bool = False) -> BuildSummary:
    settings = settings or get_settings()

    # 1-2. Select plates for one cell line and the configured timepoints, then read them.
    plates = sources.select_plates(sources.read_experiment_metadata(config), config)
    table = sources.read_plates(plates, config)
    wells, raw_features = table.wells, table.feature_columns

    # 3. Separate roles. Matched controls = negative-control wells; positive controls are real perturbations.
    reference = (
        wells["Metadata_is_negcon"]
        if config.normalization.reference == "negcon"
        else pd.Series(True, index=wells.index)
    )

    # 4. Normalize every plate to its own reference wells.
    normalized, plate_report = normalize_by_plate(
        wells, raw_features, reference, config.normalization.method, config.normalization.epsilon
    )

    # Feature selection is fit once on all wells so every output shares the same columns.
    selection = select_features(normalized[raw_features], config.feature_selection)
    features = selection.selected
    metadata_columns = [c for c in normalized.columns if c not in raw_features]
    normalized = normalized[metadata_columns + features]

    is_negcon = normalized["Metadata_is_negcon"]
    is_compound = normalized["Metadata_modality"] == "compound"
    groups = {
        ProfileType.COMPOUND: normalized[~is_negcon & is_compound],
        ProfileType.GENETIC: normalized[~is_negcon & ~is_compound],
        ProfileType.CONTROL: normalized[is_negcon],
    }

    # 5. Aggregate replicate wells into consensus profiles.
    profiles = {
        profile_type: _profile_table(
            aggregate_replicates(group, features, config.aggregation.method, config.aggregation.min_replicates),
            profile_type,
            features,
        )
        for profile_type, group in groups.items()
    }
    for profile_type, frame in profiles.items():
        validate_profile_table(frame, expected_profile_type=profile_type).raise_if_invalid(
            f"{profile_type.value} consensus profiles"
        )
    compatibility = check_feature_compatibility(
        {t.value: list(f.columns[-len(features) :]) for t, f in profiles.items()}
    )
    if not compatibility.compatible:
        raise FeatureMismatchError("Output profiles do not share features.", details=compatibility.to_dict())

    annotation_report = AnnotationReport()
    compound_metadata = build_compound_metadata(
        _with_metadata(profiles[ProfileType.COMPOUND]),
        sources.read_metadata_table(config, "compound"),
        config.annotations,
        annotation_report,
    )
    genetic_metadata = build_genetic_metadata(
        _with_metadata(profiles[ProfileType.GENETIC]), config.annotations, annotation_report
    )

    summary = BuildSummary(
        dataset=config.source.name,
        n_plates=len(plates),
        n_wells=len(wells),
        n_features_raw=len(raw_features),
        n_features_selected=len(features),
        warnings=list(annotation_report.warnings),
    )
    if table.features_dropped_as_unshared:
        summary.warnings.append(f"{len(table.features_dropped_as_unshared)} feature(s) were not on every plate.")
    for row in plates.itertuples(index=False):
        if row.anomaly not in ("none", "nan"):
            summary.warnings.append(
                f"Plate {row.plate} ({row.modality}) has anomaly '{row.anomaly}' in experiment metadata."
            )

    processed = settings.processed_dir
    paths = {
        "compound_profiles": settings.compound_profiles_path,
        "genetic_profiles": settings.genetic_profiles_path,
        "control_profiles": settings.control_profiles_path,
        "compound_metadata": processed / "metadata" / "compound_metadata.parquet",
        "genetic_metadata": processed / "metadata" / "genetic_metadata.parquet",
    }
    outputs: dict[str, pd.DataFrame] = {
        "compound_profiles": profiles[ProfileType.COMPOUND],
        "genetic_profiles": profiles[ProfileType.GENETIC],
        "control_profiles": profiles[ProfileType.CONTROL],
        "compound_metadata": compound_metadata,
        "genetic_metadata": genetic_metadata,
    }
    if config.output.save_well_level:
        for profile_type, group in groups.items():
            name = f"{profile_type.value}_wells"
            paths[name] = processed / "wells" / f"{name}.parquet"
            outputs[name] = group.assign(**{f: group[f].astype(np.float32) for f in features})
    summary.outputs = {
        name: {"path": str(paths[name]), "rows": len(frame), "columns": frame.shape[1]}
        for name, frame in outputs.items()
    }
    summary.outputs["compound_profiles"]["contexts"] = _contexts(profiles[ProfileType.COMPOUND])
    summary.outputs["genetic_profiles"]["contexts"] = _contexts(profiles[ProfileType.GENETIC])
    summary.outputs["control_profiles"]["contexts"] = _contexts(profiles[ProfileType.CONTROL])
    if dry_run:
        return summary

    # 6. Write Parquet outputs and provenance.
    for name, frame in outputs.items():
        write_parquet_atomic(frame, paths[name])
    normalization_by_plate = {entry.plate: entry for entry in plate_report}
    build_dir = processed / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / "selected_features.txt").write_text("\n".join(features) + "\n", encoding="utf-8")
    manifest = {
        "pipeline_version": PIPELINE_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "config": config.model_dump(mode="json"),
        "plates": [
            {**plate, **asdict(normalization_by_plate[plate["plate"]])} for plate in plates.to_dict(orient="records")
        ],
        "inputs": {str(config.source.plate_file(p)): _sha256(config.source.plate_file(p)) for p in plates["plate"]},
        "feature_selection": selection.summary(),
        "features_not_on_every_plate": table.features_dropped_as_unshared,
        "annotations": asdict(annotation_report),
        "summary": asdict(summary),
    }
    manifest_path = build_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    summary.manifest_path = str(manifest_path)

    if config.output.load_database:
        summary.database_loaded = _load_database(outputs, paths, features, config)
        if not summary.database_loaded:
            summary.warnings.append("Outputs were written but the database could not be loaded.")
    return summary


def _with_metadata(profile: pd.DataFrame) -> pd.DataFrame:
    """Consensus rows with the ``Metadata_*`` names the annotation builders read."""
    defaults = {
        "Metadata_pert_iname": pd.NA,
        "Metadata_InChIKey": pd.NA,
        "Metadata_gene": pd.NA,
        "Metadata_control_type": pd.NA,
    }
    missing = {k: v for k, v in defaults.items() if k not in profile.columns}
    return profile.assign(**missing)


def _contexts(frame: pd.DataFrame) -> list[dict]:
    counts = frame.groupby(["Metadata_modality", "cell_line", "timepoint"]).size()
    return [
        {"modality": modality, "cell_line": cell_line, "timepoint": float(timepoint), "n_profiles": int(n)}
        for (modality, cell_line, timepoint), n in counts.items()
    ]


def _load_database(
    outputs: dict[str, pd.DataFrame], paths: dict[str, Path], features: list[str], config: BuildConfig
) -> bool:
    from sqlalchemy.exc import SQLAlchemyError

    from app.pipeline.import_metadata import MetadataImportError, prepare_metadata, upsert_rows
    from app.pipeline.import_profiles import register_dataset

    try:
        for kind, name in (("compounds", "compound_metadata"), ("genetic", "genetic_metadata")):
            upsert_rows(kind, prepare_metadata(outputs[name], kind))
    except (SQLAlchemyError, MetadataImportError):
        return False
    registered = [
        register_dataset(
            profile_type.value,
            str(paths[f"{profile_type.value}_profiles"]),
            f"{config.source.name} (build pipeline v{PIPELINE_VERSION})",
            outputs[f"{profile_type.value}_profiles"],
            features,
        )
        for profile_type in ProfileType
    ]
    return all(registered)
