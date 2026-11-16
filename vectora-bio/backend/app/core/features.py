"""Readable descriptions of CellProfiler feature names.

JUMP feature names follow ``<Compartment>_<Measurement>_<details...>``, e.g.
``Nuclei_Texture_Contrast_DNA_3_01_256``. Channels: DNA (nucleus), RNA (nucleoli and
cytoplasmic RNA), ER (endoplasmic reticulum), AGP (actin, Golgi, plasma membrane),
Mito (mitochondria), Brightfield.
"""

from dataclasses import dataclass

import pandas as pd

COMPARTMENTS = {"Cells": "Cell", "Cytoplasm": "Cytoplasm", "Nuclei": "Nucleus"}
MEASUREMENTS = {
    "AreaShape": "size/shape",
    "Intensity": "intensity",
    "Texture": "texture",
    "Granularity": "granularity",
    "RadialDistribution": "radial distribution",
    "Correlation": "channel correlation",
    "Neighbors": "neighbours/density",
    "Location": "location",
}
CHANNELS = ("DNA", "RNA", "ER", "AGP", "Mito", "Brightfield")
_CHANNEL_ALIASES = {"HighZBF": "Brightfield", "LowZBF": "Brightfield", "BFHigh": "Brightfield", "BFLow": "Brightfield"}


@dataclass(frozen=True)
class FeatureInfo:
    name: str
    compartment: str
    measurement: str
    channels: tuple[str, ...]
    label: str


def describe_feature(name: str) -> FeatureInfo:
    """Split a CellProfiler feature name into compartment, measurement and stain channels."""
    parts = name.split("_")
    compartment = COMPARTMENTS.get(parts[0], parts[0])
    measurement = MEASUREMENTS.get(parts[1], parts[1]) if len(parts) > 1 else "other"
    channels: list[str] = []
    for part in parts[2:]:
        channel = _CHANNEL_ALIASES.get(part, part if part in CHANNELS else None)
        if channel and channel not in channels:
            channels.append(channel)
    detail = " ".join(p for p in parts[2:] if p not in CHANNELS and p not in _CHANNEL_ALIASES and not p.isdigit())
    channel_text = f" [{'/'.join(channels)}]" if channels else ""
    label = f"{compartment} {measurement}{': ' + detail if detail else ''}{channel_text}"
    return FeatureInfo(name, compartment, measurement, tuple(channels), label)


def group_contributions(contributions: pd.Series, by: str) -> pd.Series:
    """Sum per-feature contributions by ``compartment``, ``measurement`` or ``channel``.

    A feature measuring two channels (e.g. a correlation) splits its contribution evenly.
    """
    if by not in ("compartment", "measurement", "channel"):
        raise ValueError(f"Unknown grouping: {by}")
    totals: dict[str, float] = {}
    for name, value in contributions.items():
        info = describe_feature(str(name))
        if by == "channel":
            keys = info.channels or ("none",)
            share = float(value) / len(keys)
            for key in keys:
                totals[key] = totals.get(key, 0.0) + share
        else:
            key = info.compartment if by == "compartment" else info.measurement
            totals[key] = totals.get(key, 0.0) + float(value)
    return pd.Series(totals).sort_values(ascending=False)
