"""Per-perturbation phenotype summaries and microscopy references for the UI."""

import numpy as np
import pandas as pd

from app.config import Settings
from app.core.features import describe_feature
from app.core.phenotype_map import map_similarity, phenotype_map
from app.core.phenotype_quality import empirical_percentile, pseudo_replicate_consensus, strength_null
from app.data.cell_images import (
    CHANNEL_COLORS,
    DEFAULT_FIELD,
    FIELDS,
    FLUORESCENT_CHANNELS,
    IMAGE_SIZE_PX,
    PIXEL_SIZE_UM,
)
from app.data.profile_store import MODALITY_COLUMN, ProfileStore
from app.errors import DataNotLoadedError, InvalidQueryError, NotFoundError
from app.schemas.common import ProfileType
from app.schemas.profile import (
    FeatureChange,
    ImageSourceInfo,
    MapAgreement,
    PhenotypeMapCell,
    PlateLayout,
    PlateSummary,
    PlateWell,
    ProfileComparison,
    ProfileOverview,
    WellImageRef,
)

TOP_FEATURES = 8
IMAGE_SOURCE = "JUMP Cell Painting pilot (cpg0000-jump-pilot), Cell Painting Gallery"


def _hex(color: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{round(c * 255):02x}" for c in color)


def _first(rows: pd.DataFrame, column: str):
    if column not in rows.columns:
        return None
    values = rows[column].dropna()
    return values.iloc[0] if len(values) else None


def _profile_rows(store: ProfileStore, profile_type: ProfileType, perturbation_id: str) -> pd.DataFrame:
    if profile_type == ProfileType.CONTROL:
        raise InvalidQueryError("Overviews are available for compound and genetic perturbations.")
    frame = store.load(profile_type)
    rows = frame[frame["perturbation_id"] == perturbation_id]
    if rows.empty:
        raise NotFoundError(f"No {profile_type.value} profile for {perturbation_id!r}.")
    return rows


def _profile_vector(store: ProfileStore, profile_type: ProfileType, rows: pd.DataFrame) -> pd.Series:
    return rows[store.feature_columns(profile_type)].median().astype(np.float64)


def _strength_percentile(
    store: ProfileStore,
    features: list[str],
    modality: str | None,
    cell_line: str,
    timepoint: float,
    n_replicates: int,
    norm: float,
) -> float | None:
    """Where the profile's norm falls among medians of ``n_replicates`` random control wells."""
    wells = store.wells(ProfileType.CONTROL)
    if wells is None:
        return None

    def build() -> np.ndarray | None:
        controls = wells
        if modality is not None and MODALITY_COLUMN in controls.columns:
            controls = controls[controls[MODALITY_COLUMN] == modality]
        controls = controls[controls["cell_line"].astype(str).str.casefold() == cell_line.casefold()]
        controls = controls[np.isclose(controls["timepoint"].astype(float), timepoint)]
        if len(controls) < 3 or any(f not in controls.columns for f in features):
            return None
        return strength_null(pseudo_replicate_consensus(controls, features, max(1, n_replicates)))

    null = store.memo(
        (ProfileType.CONTROL,), ("strength_null", modality, cell_line.casefold(), timepoint, n_replicates), build
    )
    return None if null is None else float(empirical_percentile([norm], null)[0])


def _image_wells(store: ProfileStore, profile_type: ProfileType, perturbation_id: str) -> list[WellImageRef]:
    """Replicate wells, each paired with a negative-control well on the same plate."""
    wells = store.wells(profile_type)
    if wells is None or "Metadata_Plate" not in wells.columns:
        return []
    own = wells[wells["perturbation_id"].astype(str) == perturbation_id]
    controls = store.wells(ProfileType.CONTROL)
    refs = []
    for plate, well in own[["Metadata_Plate", "Metadata_Well"]].drop_duplicates().itertuples(index=False):
        control_well = None
        if controls is not None:
            on_plate = sorted(controls.loc[controls["Metadata_Plate"] == plate, "Metadata_Well"].astype(str))
            # The middle control well of the plate: deterministic and away from the plate edge.
            control_well = on_plate[len(on_plate) // 2] if on_plate else None
        refs.append(WellImageRef(plate=str(plate), well=str(well), control_well=control_well))
    return sorted(refs, key=lambda r: (r.plate, r.well))


def _image_info(settings: Settings, has_wells: bool) -> ImageSourceInfo:
    message = None
    if not settings.cell_images_enabled:
        message = "Cell images are disabled (CELL_IMAGES_ENABLED=false)."
    elif not has_wells:
        message = "No plate/well positions for this perturbation (well-level files missing)."
    return ImageSourceInfo(
        available=settings.cell_images_enabled and has_wells,
        source=IMAGE_SOURCE,
        fields=list(FIELDS),
        default_field=DEFAULT_FIELD,
        channels=[*FLUORESCENT_CHANNELS, "Brightfield"],
        channel_colors={name: _hex(color) for name, color in CHANNEL_COLORS.items()},
        pixel_size_um=PIXEL_SIZE_UM,
        image_size_px=IMAGE_SIZE_PX,
        message=message,
    )


def profile_overview(
    store: ProfileStore, settings: Settings, profile_type: ProfileType, perturbation_id: str
) -> ProfileOverview:
    rows = _profile_rows(store, profile_type, perturbation_id)
    profile = _profile_vector(store, profile_type, rows)
    cell_line = str(rows["cell_line"].iloc[0])
    timepoint = float(rows["timepoint"].iloc[0])
    modality = _first(rows, MODALITY_COLUMN)
    n_replicates = _first(rows, "Metadata_n_replicates")
    replicate_cosine = _first(rows, "Metadata_replicate_cosine")
    norm = float(np.linalg.norm(profile.to_numpy()))
    n_rep = int(n_replicates) if n_replicates is not None else 1

    top = profile.reindex(profile.abs().sort_values(ascending=False).index[:TOP_FEATURES])
    wells = _image_wells(store, profile_type, perturbation_id)
    return ProfileOverview(
        perturbation_id=perturbation_id,
        profile_type=profile_type,
        name=_first(rows, "Metadata_pert_iname"),
        gene=_first(rows, "Metadata_gene"),
        modality=modality,
        cell_line=cell_line,
        timepoint=timepoint,
        n_replicates=int(n_replicates) if n_replicates is not None else None,
        replicate_cosine=float(replicate_cosine) if replicate_cosine is not None else None,
        n_features=int(profile.size),
        response_norm=norm,
        strength_percentile=_strength_percentile(
            store, list(profile.index), modality, cell_line, timepoint, n_rep, norm
        ),
        phenotype_map=[PhenotypeMapCell(**vars(cell)) for cell in phenotype_map(profile)],
        top_features=[
            FeatureChange(feature=str(name), label=describe_feature(str(name)).label, value=float(value))
            for name, value in top.items()
        ],
        wells=wells,
        images=_image_info(settings, bool(wells)),
    )


def compare_profiles(
    store: ProfileStore,
    first: tuple[ProfileType, str],
    second: tuple[ProfileType, str],
    subtract_controls: bool = False,
) -> ProfileComparison:
    """Overall cosine and per compartment x channel agreement between two perturbations."""
    vectors = []
    for profile_type, perturbation_id in (first, second):
        rows = _profile_rows(store, profile_type, perturbation_id)
        vector = _profile_vector(store, profile_type, rows)
        if subtract_controls:
            control = store.control_consensus(
                str(rows["cell_line"].iloc[0]), float(rows["timepoint"].iloc[0]), _first(rows, MODALITY_COLUMN)
            )
            vector = vector - control.reindex(vector.index).fillna(0.0)
        vectors.append(vector)
    a, b = vectors
    shared = a.index.intersection(b.index)
    a, b = a[shared], b[shared]
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    cosine = float(np.dot(a, b) / denominator) if denominator else 0.0
    return ProfileComparison(
        first_id=first[1],
        second_id=second[1],
        cosine=cosine,
        subtract_controls=subtract_controls,
        cells=[MapAgreement(**cell) for cell in map_similarity(a, b)],
    )


def _plate_rows(store: ProfileStore) -> pd.DataFrame:
    """One row per imaged well across compound, genetic and control well files."""
    frames = []
    for profile_type in (ProfileType.COMPOUND, ProfileType.GENETIC, ProfileType.CONTROL):
        wells = store.wells(profile_type)
        if wells is None or "Metadata_Plate" not in wells.columns:
            continue
        columns = [
            c
            for c in (
                "Metadata_Plate",
                "Metadata_Well",
                "perturbation_id",
                "cell_line",
                "timepoint",
                MODALITY_COLUMN,
                "Metadata_pert_iname",
                "Metadata_gene",
            )
            if c in wells.columns
        ]
        frames.append(wells[columns].assign(profile_type=profile_type.value))
    if not frames:
        raise DataNotLoadedError(
            ["well_profiles"],
            hint="Run the Phase 1 build (app.pipeline.build_profiles) to write data/processed/wells/.",
        )
    return pd.concat(frames, ignore_index=True)


def list_plates(store: ProfileStore) -> list[PlateSummary]:
    rows = _plate_rows(store)
    summaries = []
    for plate, group in rows.groupby("Metadata_Plate"):
        summaries.append(
            PlateSummary(
                plate=str(plate),
                modality=_first(group[group["profile_type"] != "control"], MODALITY_COLUMN),
                cell_line=_first(group, "cell_line"),
                timepoint=float(group["timepoint"].iloc[0]) if "timepoint" in group else None,
                n_wells=int(len(group)),
                n_controls=int((group["profile_type"] == "control").sum()),
            )
        )
    return summaries


def plate_layout(store: ProfileStore, plate: str) -> PlateLayout:
    rows = _plate_rows(store)
    group = rows[rows["Metadata_Plate"] == plate]
    if group.empty:
        raise NotFoundError(f"Plate {plate!r} is not part of the imported dataset.")
    wells = []
    for row in group.itertuples(index=False):
        record = row._asdict()
        profile_type = ProfileType(record["profile_type"])
        name = record.get("Metadata_pert_iname")
        gene = record.get("Metadata_gene")
        label = name if isinstance(name, str) else (gene if isinstance(gene, str) else None)
        kind = (
            "control" if profile_type == ProfileType.CONTROL else str(record.get(MODALITY_COLUMN) or profile_type.value)
        )
        wells.append(
            PlateWell(
                well=str(record["Metadata_Well"]),
                kind=kind,
                perturbation_id=None if profile_type == ProfileType.CONTROL else str(record["perturbation_id"]),
                profile_type=profile_type,
                label=label if profile_type != ProfileType.CONTROL else (label or "negative control"),
            )
        )
    return PlateLayout(
        plate=plate,
        modality=_first(group[group["profile_type"] != "control"], MODALITY_COLUMN),
        cell_line=_first(group, "cell_line"),
        timepoint=float(group["timepoint"].iloc[0]),
        wells=sorted(wells, key=lambda w: (w.well[0], int(w.well[1:]))),
    )
