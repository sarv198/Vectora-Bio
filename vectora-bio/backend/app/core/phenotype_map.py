"""Compartment x stain-channel summary of a phenotypic profile.

Profiles are robust z-scores against negative controls, so a cell of the map that is
close to 0 looks like control and a large value means that stain, measured in that
compartment, changed. Features without a stain channel (size/shape, neighbours) are
pooled in a "Shape" column.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.core.features import describe_feature

MAP_COMPARTMENTS = ("Cell", "Cytoplasm", "Nucleus")
MAP_CHANNELS = ("DNA", "RNA", "ER", "AGP", "Mito", "Brightfield", "Shape")


@dataclass(frozen=True)
class MapCell:
    compartment: str
    channel: str
    n_features: int
    rms: float
    mean: float
    top_feature: str | None
    top_label: str | None
    top_value: float | None


def _cell_keys(name: str) -> list[tuple[str, str]]:
    info = describe_feature(name)
    if info.compartment not in MAP_COMPARTMENTS:
        return []
    channels = [c for c in info.channels if c in MAP_CHANNELS] or ["Shape"]
    return [(info.compartment, channel) for channel in channels]


def phenotype_map(profile: pd.Series) -> list[MapCell]:
    """Root-mean-square change per (compartment, channel), with its largest single feature.

    A feature that measures two channels (e.g. a correlation) counts towards both cells.
    Cells with no features are omitted.
    """
    groups: dict[tuple[str, str], list[str]] = {}
    for name in profile.index:
        for key in _cell_keys(str(name)):
            groups.setdefault(key, []).append(str(name))
    cells = []
    for compartment in MAP_COMPARTMENTS:
        for channel in MAP_CHANNELS:
            names = groups.get((compartment, channel))
            if not names:
                continue
            values = profile[names].astype(np.float64)
            values = values[np.isfinite(values)]
            if values.empty:
                continue
            top = values.abs().idxmax()
            cells.append(
                MapCell(
                    compartment=compartment,
                    channel=channel,
                    n_features=int(values.size),
                    rms=float(np.sqrt(np.mean(values.to_numpy() ** 2))),
                    mean=float(values.mean()),
                    top_feature=str(top),
                    top_label=describe_feature(str(top)).label,
                    top_value=float(values[top]),
                )
            )
    return cells


def map_similarity(first: pd.Series, second: pd.Series) -> list[dict[str, float | str | int]]:
    """Cosine between two profiles restricted to each (compartment, channel) cell.

    Shows *where* two profiles agree (positive) or oppose each other (negative).
    """
    shared = first.index.intersection(second.index)
    groups: dict[tuple[str, str], list[str]] = {}
    for name in shared:
        for key in _cell_keys(str(name)):
            groups.setdefault(key, []).append(str(name))
    result = []
    for (compartment, channel), names in groups.items():
        a = first[names].to_numpy(np.float64)
        b = second[names].to_numpy(np.float64)
        denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
        if denominator == 0 or not np.isfinite(denominator):
            continue
        result.append(
            {
                "compartment": compartment,
                "channel": channel,
                "n_features": len(names),
                "cosine": float(np.dot(a, b) / denominator),
            }
        )
    return result
