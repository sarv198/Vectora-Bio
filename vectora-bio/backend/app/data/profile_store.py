"""Cached access to the processed Parquet profile files."""

import threading
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from app.config import Settings, get_settings
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
        self._lock = threading.Lock()

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
        key = (profile_type, cell_line.casefold() if cell_line else None, timepoint, self._settings.consensus_method)
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

    def control_consensus(self, cell_line: str, timepoint: float) -> pd.Series:
        """Median of all matched control profiles for one context, as a single vector."""
        frame = self.load(ProfileType.CONTROL)
        subset = filter_profiles(frame, cell_line=cell_line, timepoint=timepoint)
        if subset.empty:
            raise DataNotLoadedError(
                ["control_profiles"],
                message=f"No matched control profiles for cell_line={cell_line!r}, timepoint={timepoint!r}.",
                hint="Import control profiles for this context or set subtract_matched_controls=false.",
            )
        features = identify_feature_columns(frame)
        return subset[features].median().astype(np.float64)


@lru_cache
def get_profile_store() -> ProfileStore:
    return ProfileStore(get_settings())
