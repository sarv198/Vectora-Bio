"""Feature selection applied once, jointly over all modalities, so every output shares one feature set."""

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from app.preprocessing.config import FeatureSelectionConfig


@dataclass
class FeatureSelectionReport:
    n_input: int
    selected: list[str]
    removed: dict[str, list[str]] = field(default_factory=dict)

    def summary(self) -> dict:
        return {
            "n_input": self.n_input,
            "n_selected": len(self.selected),
            "removed_counts": {step: len(names) for step, names in self.removed.items()},
        }


def blocklisted(features: list[str], patterns: list[str]) -> list[str]:
    compiled = [re.compile(pattern) for pattern in patterns]
    return [f for f in features if any(p.search(f) for p in compiled)]


def missing_features(frame: pd.DataFrame) -> list[str]:
    """Features with any missing or non-finite value."""
    values = frame.to_numpy(dtype=np.float64)
    bad = ~np.isfinite(values).all(axis=0)
    return [frame.columns[i] for i in np.flatnonzero(bad)]


def low_variance_features(frame: pd.DataFrame, freq_cut: float, unique_cut: float) -> list[str]:
    """Constant features, and near-constant ones in the style of caret's ``nearZeroVar``.

    A feature is near-constant when the second most common value is rare relative to the
    most common (count ratio < ``freq_cut``) *and* few values are distinct
    (n_unique / n < ``unique_cut``).
    """
    n = len(frame)
    removed = []
    for column in frame.columns:
        counts = frame[column].value_counts(dropna=True)
        if len(counts) <= 1:
            removed.append(column)
            continue
        freq_ratio = counts.iloc[1] / counts.iloc[0]
        unique_ratio = len(counts) / n
        if freq_ratio < freq_cut and unique_ratio < unique_cut:
            removed.append(column)
    return removed


def correlated_features(frame: pd.DataFrame, threshold: float) -> list[str]:
    """Greedy redundancy filter: visit features from least to most correlated with the rest
    (mean |r|), keep a feature unless |r| with an already-kept feature exceeds ``threshold``.
    """
    if frame.shape[1] < 2:
        return []
    correlation = np.abs(np.corrcoef(frame.to_numpy(dtype=np.float64), rowvar=False))
    np.fill_diagonal(correlation, 0.0)
    correlation = np.nan_to_num(correlation, nan=0.0)
    order = np.argsort(correlation.mean(axis=0), kind="stable")
    kept: list[int] = []
    removed: list[int] = []
    for index in order:
        if kept and correlation[index, kept].max() > threshold:
            removed.append(index)
        else:
            kept.append(index)
    return [frame.columns[i] for i in sorted(removed)]


def select_features(frame: pd.DataFrame, config: FeatureSelectionConfig) -> FeatureSelectionReport:
    """Run blocklist -> missing -> low variance -> correlation, each on what the previous step kept."""
    remaining = list(frame.columns)
    report = FeatureSelectionReport(n_input=len(remaining), selected=[])

    def drop(step: str, names: list[str]) -> None:
        report.removed[step] = names
        dropped = set(names)
        remaining[:] = [f for f in remaining if f not in dropped]

    drop("blocklist", blocklisted(remaining, config.blocklist_patterns))
    if config.drop_missing:
        drop("missing", missing_features(frame[remaining]))
    drop("low_variance", low_variance_features(frame[remaining], config.variance_freq_cut, config.variance_unique_cut))
    if config.correlation_threshold is not None:
        drop("correlation", correlated_features(frame[remaining], config.correlation_threshold))

    if not remaining:
        raise ValueError("Feature selection removed every feature; relax the configuration.")
    report.selected = remaining
    return report
