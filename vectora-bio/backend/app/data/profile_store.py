"""Cached access to the processed Parquet profile files."""

import threading
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import TypeVar

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from app.config import Settings, get_settings
from app.core.similarity import similarity_background
from app.data.loaders import (
    AmbiguousContextError,
    ConsensusProfiles,
    available_contexts,
    build_consensus_profiles,
    filter_profiles,
    identify_feature_columns,
    is_metadata_column,
)
from app.errors import DataNotLoadedError, InvalidQueryError
from app.schemas.common import ProfileType
from app.schemas.profile import DatasetStatus

MODALITY_COLUMN = "Metadata_modality"
T = TypeVar("T")


def dataset_name(profile_type: ProfileType) -> str:
    return f"{profile_type.value}_profiles"


class ProfileStore:
    """Loads each processed profile file once and caches consensus profiles per context.

    Caches are invalidated when the file's modification time changes, so re-running
    the import pipeline is picked up without restarting the API.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._paths = {
            ProfileType.COMPOUND: settings.compound_profiles_path,
            ProfileType.GENETIC: settings.genetic_profiles_path,
            ProfileType.CONTROL: settings.control_profiles_path,
        }
        self._frames: dict[ProfileType, tuple[float, pd.DataFrame]] = {}
        self._consensus: dict[tuple, ConsensusProfiles] = {}
        self._backgrounds: dict[tuple, np.ndarray] = {}
        self._memo: dict[tuple, object] = {}
        self._lock = threading.Lock()

    def _context_key(self, profile_type: ProfileType, cell_line: str | None, timepoint: float | None) -> tuple:
        return (profile_type, cell_line.casefold() if cell_line else None, timepoint, self._settings.consensus_method)

    def path(self, profile_type: ProfileType) -> Path:
        return self._paths[profile_type]

    def is_available(self, profile_type: ProfileType) -> bool:
        return self.path(profile_type).is_file()

    def status(self) -> list[DatasetStatus]:
        statuses = []
        for profile_type, path in self._paths.items():
            status = DatasetStatus(
                name=dataset_name(profile_type), profile_type=profile_type, path=str(path), available=False
            )
            if not path.is_file():
                status.message = "Not imported."
            else:
                try:
                    metadata = pq.ParquetFile(path).metadata
                    names = metadata.schema.names
                    status.available = True
                    status.n_rows = metadata.num_rows
                    status.n_features = sum(1 for name in names if not is_metadata_column(name))
                except Exception as exc:  # noqa: BLE001 - surface any read failure as status
                    status.message = f"Unreadable: {exc}"
            statuses.append(status)
        return statuses

    def load(self, profile_type: ProfileType) -> pd.DataFrame:
        path = self.path(profile_type)
        if not path.is_file():
            raise DataNotLoadedError([dataset_name(profile_type)])
        mtime = path.stat().st_mtime
        with self._lock:
            cached = self._frames.get(profile_type)
            if cached is not None and cached[0] == mtime:
                return cached[1]
            frame = pd.read_parquet(path)
            frame["perturbation_id"] = frame["perturbation_id"].astype(str)
            frame["timepoint"] = pd.to_numeric(frame["timepoint"])
            self._frames[profile_type] = (mtime, frame)
            self._consensus = {key: value for key, value in self._consensus.items() if key[0] != profile_type}
            self._backgrounds = {key: value for key, value in self._backgrounds.items() if key[0] != profile_type}
            self._memo = {key: value for key, value in self._memo.items() if profile_type not in key[0]}
            return frame

    def feature_columns(self, profile_type: ProfileType) -> list[str]:
        return identify_feature_columns(self.load(profile_type))

    def consensus(
        self,
        profile_type: ProfileType,
        cell_line: str | None = None,
        timepoint: float | None = None,
    ) -> ConsensusProfiles:
        """Consensus profiles for one context. Raises ``InvalidQueryError`` when nothing matches."""
        frame = self.load(profile_type)
        key = self._context_key(profile_type, cell_line, timepoint)
        with self._lock:
            if key in self._consensus:
                return self._consensus[key]
        subset = filter_profiles(frame, cell_line=cell_line, timepoint=timepoint)
        if subset.empty:
            raise InvalidQueryError(
                f"No {profile_type.value} profiles match cell_line={cell_line!r}, timepoint={timepoint!r}.",
                details={"available_contexts": available_contexts(frame)},
            )
        try:
            consensus = build_consensus_profiles(
                subset, identify_feature_columns(frame), method=self._settings.consensus_method
            )
        except AmbiguousContextError as exc:
            raise InvalidQueryError(
                str(exc),
                details={
                    "perturbation_ids": exc.perturbation_ids[:10],
                    "available_contexts": available_contexts(frame),
                },
            ) from exc
        with self._lock:
            self._consensus[key] = consensus
        return consensus

    def similarity_background(
        self, profile_type: ProfileType, cell_line: str | None = None, timepoint: float | None = None
    ) -> np.ndarray:
        """Sorted pairwise cosine similarities among the consensus profiles of one context (cached)."""
        consensus = self.consensus(profile_type, cell_line, timepoint)
        key = self._context_key(profile_type, cell_line, timepoint)
        with self._lock:
            if key in self._backgrounds:
                return self._backgrounds[key]
        background = similarity_background(consensus.features)
        with self._lock:
            self._backgrounds[key] = background
        return background

    def memo(self, depends_on: tuple[ProfileType, ...], key: tuple, factory: Callable[[], T]) -> T:
        """Cache a derived result until any profile file in ``depends_on`` is reloaded."""
        for profile_type in depends_on:
            self.load(profile_type)  # reloads (and invalidates) if the file changed
        full_key = (depends_on, *key)
        with self._lock:
            if full_key in self._memo:
                return self._memo[full_key]  # type: ignore[return-value]
        value = factory()
        with self._lock:
            self._memo[full_key] = value
        return value

    def metadata_values(self, profile_type: ProfileType, column: str) -> pd.Series:
        """First non-null value of a ``Metadata_*`` column per perturbation; empty if the file lacks it."""
        frame = self.load(profile_type)
        if column not in frame.columns:
            return pd.Series(dtype=object)
        return frame.dropna(subset=[column]).groupby("perturbation_id")[column].first()

    def modality(self, profile_type: ProfileType, perturbation_id: str) -> str | None:
        """``Metadata_modality`` of a perturbation (compound / crispr / orf), if the file records it."""
        frame = self.load(profile_type)
        if MODALITY_COLUMN not in frame.columns:
            return None
        values = frame.loc[frame["perturbation_id"] == perturbation_id, MODALITY_COLUMN].dropna()
        return str(values.iloc[0]) if len(values) else None

    def control_consensus(self, cell_line: str, timepoint: float, modality: str | None = None) -> pd.Series:
        """Median of the matched control profiles for one context, as a single vector.

        Controls are matched on cell line, timepoint and, when the control file records it,
        modality: DMSO for compounds, negative-control guides for CRISPR, negative-control ORFs for ORF.
        """
        frame = self.load(ProfileType.CONTROL)
        subset = filter_profiles(frame, cell_line=cell_line, timepoint=timepoint)
        if modality is not None and MODALITY_COLUMN in subset.columns:
            subset = subset[subset[MODALITY_COLUMN] == modality]
        if subset.empty:
            raise DataNotLoadedError(
                ["control_profiles"],
                message=(
                    f"No matched control profiles for cell_line={cell_line!r}, timepoint={timepoint!r}"
                    + (f", modality={modality!r}." if modality else ".")
                ),
                hint="Import control profiles for this context or set subtract_matched_controls=false.",
            )
        features = identify_feature_columns(frame)
        return subset[features].median().astype(np.float64)


@lru_cache
def get_profile_store() -> ProfileStore:
    return ProfileStore(get_settings())
