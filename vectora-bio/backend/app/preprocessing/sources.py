"""JUMP Cell Painting pilot (cpg0000-jump-pilot / CPJUMP1) file locations, plate selection, and plate reading.

Raw layout under ``source.raw_dir`` (mirrors the upstream paths, created by ``app.pipeline.download_cpjump1``)::

    metadata/experiment-metadata.tsv                  one row per plate (Cell_type, Time, Density, ...)
    metadata/JUMP-Target-1_{compound,crispr,orf}_metadata*.tsv
    profiles/<batch>/<plate>/<plate>_augmented.csv.gz  one row per well: Metadata_* + CellProfiler features
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.preprocessing.config import MODALITIES, BuildConfig, Modality

PROFILES_BASE_URL = "https://cellpainting-gallery.s3.amazonaws.com/cpg0000-jump-pilot/source_4/workspace/profiles"
METADATA_BASE_URL = "https://raw.githubusercontent.com/jump-cellpainting/2024_Chandrasekaran_NatureMethods/main"
EXPERIMENT_METADATA_URL = f"{METADATA_BASE_URL}/benchmark/output/experiment-metadata.tsv"
EXTERNAL_METADATA_URL = f"{METADATA_BASE_URL}/metadata/external_metadata"

NEGCON = "negcon"
# Well metadata kept from the plate files (others are dropped). Missing ones are filled with NA.
WELL_METADATA = (
    "Metadata_Plate",
    "Metadata_Well",
    "Metadata_broad_sample",
    "Metadata_pert_iname",
    "Metadata_InChIKey",
    "Metadata_gene",
    "Metadata_pert_type",
    "Metadata_control_type",
    "Metadata_negcon_control_type",
)


class SourceError(ValueError):
    """Raw inputs are missing or inconsistent; the message says what to fix."""


def plate_url(batch: str, plate: str, suffix: str) -> str:
    return f"{PROFILES_BASE_URL}/{batch}/{plate}/{plate}_{suffix}.csv.gz"


def read_experiment_metadata(config: BuildConfig) -> pd.DataFrame:
    path = config.source.metadata_file(config.source.experiment_metadata)
    if not path.is_file():
        raise SourceError(f"Experiment metadata not found at {path}. Run `python -m app.pipeline.download_cpjump1`.")
    return pd.read_csv(path, sep="\t")


def select_plates(experiment: pd.DataFrame, config: BuildConfig) -> pd.DataFrame:
    """Plates for the configured batch, cell type, per-modality timepoint, density, and antibiotics.

    Returns columns ``plate, modality, cell_type, timepoint, anomaly``.
    """
    selection = config.selection
    frame = experiment[experiment["Batch"] == config.source.batch]
    if selection.plates is not None:
        frame = frame[frame["Assay_Plate_Barcode"].isin(selection.plates)]
        unknown = sorted(set(selection.plates) - set(frame["Assay_Plate_Barcode"]))
        if unknown:
            raise SourceError(f"Plates not in batch {config.source.batch}: {unknown}")
    else:
        frame = frame[frame["Cell_type"].str.casefold() == selection.cell_type.casefold()]
        if selection.density is not None:
            frame = frame[np.isclose(frame["Density"].astype(float), selection.density)]
        if selection.antibiotics is not None:
            frame = frame[frame["Antibiotics"].astype(str).str.casefold() == selection.antibiotics.casefold()]
        if selection.exclude_anomalies:
            frame = frame[~frame["Anomaly"].isin(selection.exclude_anomalies)]
        keep = pd.Series(False, index=frame.index)
        for modality, hours in selection.timepoints.items():
            keep |= (frame["Perturbation"] == modality) & np.isclose(frame["Time"].astype(float), hours)
        frame = frame[keep]

    plates = pd.DataFrame(
        {
            "plate": frame["Assay_Plate_Barcode"].astype(str),
            "modality": frame["Perturbation"].astype(str),
            "cell_type": frame["Cell_type"].astype(str),
            "timepoint": frame["Time"].astype(float),
            "anomaly": frame["Anomaly"].astype(str),
        }
    ).drop_duplicates("plate")
    plates = plates[plates["modality"].isin(MODALITIES)].sort_values(["modality", "plate"]).reset_index(drop=True)

    missing = [m for m in selection.timepoints if m not in set(plates["modality"])]
    if missing:
        raise SourceError(
            f"No plates match the selection for {missing} "
            f"(cell_type={selection.cell_type}, timepoints={selection.timepoints}, density={selection.density}, "
            f"antibiotics={selection.antibiotics}). Check experiment-metadata.tsv for available combinations."
        )
    return plates


def missing_plate_files(plates: pd.DataFrame, config: BuildConfig) -> list[str]:
    return [str(config.source.plate_file(p)) for p in plates["plate"] if not config.source.plate_file(p).is_file()]


@dataclass
class PlateTable:
    """All selected wells: standardized metadata plus raw features (shared columns only)."""

    wells: pd.DataFrame
    feature_columns: list[str]
    features_dropped_as_unshared: list[str]


def read_plates(plates: pd.DataFrame, config: BuildConfig) -> PlateTable:
    """Read every selected plate, tag modality/context, drop empty wells, and keep shared features."""
    missing = missing_plate_files(plates, config)
    if missing:
        raise SourceError(
            f"{len(missing)} plate file(s) are missing, e.g. {missing[:3]}. "
            "Run `python -m app.pipeline.download_cpjump1`."
        )
    frames: list[pd.DataFrame] = []
    feature_sets: list[set[str]] = []
    for row in plates.itertuples(index=False):
        frame = pd.read_csv(config.source.plate_file(row.plate), low_memory=False)
        features = [c for c in frame.columns if not c.startswith("Metadata_")]
        feature_sets.append(set(features))
        # Build the metadata block separately and join once; inserting columns one by one into a
        # ~5,800-column frame fragments it.
        metadata = pd.DataFrame(
            {column: frame[column] if column in frame.columns else pd.NA for column in WELL_METADATA},
            index=frame.index,
        ).assign(
            Metadata_Plate=row.plate,
            Metadata_modality=row.modality,
            Metadata_anomaly=row.anomaly,
            cell_line=row.cell_type,
            timepoint=row.timepoint,
        )
        frames.append(pd.concat([metadata, frame[features]], axis=1))

    shared = set.intersection(*feature_sets)
    union = set.union(*feature_sets)
    feature_columns = [c for c in frames[0].columns if c in shared]
    wells = pd.concat(
        [
            frame[
                [c for c in frame.columns if c.startswith("Metadata_") or c in ("cell_line", "timepoint")]
                + feature_columns
            ]
            for frame in frames
        ],
        ignore_index=True,
    )
    # Empty wells carry no perturbation type.
    wells = wells[wells["Metadata_pert_type"].notna()].reset_index(drop=True)
    wells["perturbation_id"] = _perturbation_ids(wells)
    wells["Metadata_is_negcon"] = wells["Metadata_control_type"].astype("string").fillna("") == NEGCON
    return PlateTable(wells=wells, feature_columns=feature_columns, features_dropped_as_unshared=sorted(union - shared))


def _perturbation_ids(wells: pd.DataFrame) -> pd.Series:
    """Broad sample id; DMSO and other solvent wells have none, so fall back to the perturbation name."""
    ids = wells["Metadata_broad_sample"].astype("string")
    fallback = wells["Metadata_pert_iname"].astype("string").fillna(wells["Metadata_control_type"].astype("string"))
    ids = ids.fillna(fallback)
    if ids.isna().any():
        raise SourceError(f"{int(ids.isna().sum())} well(s) have no broad_sample or pert_iname to identify them.")
    return ids.astype(str)


def read_metadata_table(config: BuildConfig, modality: Modality) -> pd.DataFrame:
    name = {
        "compound": config.source.compound_metadata,
        "crispr": config.source.crispr_metadata,
        "orf": config.source.orf_metadata,
    }[modality]
    path = config.source.metadata_file(name)
    if not path.is_file():
        raise SourceError(f"{modality} metadata not found at {path}. Run `python -m app.pipeline.download_cpjump1`.")
    return pd.read_csv(path, sep="\t", dtype=str)
