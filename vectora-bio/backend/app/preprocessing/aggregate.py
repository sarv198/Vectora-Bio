"""Aggregate replicate wells into one consensus profile per perturbation and context."""

from typing import Literal

import numpy as np
import pandas as pd

GROUP_COLUMNS = ["Metadata_modality", "perturbation_id", "cell_line", "timepoint"]


def mean_pairwise_cosine(values: np.ndarray) -> float:
    """Mean cosine similarity over all pairs of rows; NaN with fewer than two usable rows.

    Uses ||sum u_i||^2 = k + sum_{i != j} u_i . u_j for unit vectors u_i.
    """
    norms = np.linalg.norm(values, axis=1)
    usable = values[norms > 0] / norms[norms > 0, None]
    k = len(usable)
    if k < 2:
        return float("nan")
    total = usable.sum(axis=0)
    return float((total @ total - k) / (k * (k - 1)))


def aggregate_replicates(
    wells: pd.DataFrame,
    feature_columns: list[str],
    method: Literal["median", "mean"] = "median",
    min_replicates: int = 1,
) -> pd.DataFrame:
    """One row per (modality, perturbation, cell line, timepoint).

    Adds ``Metadata_n_replicates``, ``Metadata_n_plates`` and ``Metadata_replicate_cosine``
    (mean pairwise cosine of the replicate wells: a reproducibility indicator, NaN for
    single replicates). Groups with fewer than ``min_replicates`` wells are dropped.
    Other ``Metadata_*`` columns keep their first value per group.
    """
    if method not in ("median", "mean"):
        raise ValueError(f"Unsupported aggregation method: {method}")
    grouped = wells.groupby(GROUP_COLUMNS, sort=True, dropna=False)
    consensus = grouped[feature_columns].median() if method == "median" else grouped[feature_columns].mean()

    extra_metadata = [c for c in wells.columns if c.startswith("Metadata_") and c not in GROUP_COLUMNS]
    metadata = grouped[extra_metadata].first() if extra_metadata else pd.DataFrame(index=consensus.index)
    metadata["Metadata_n_replicates"] = grouped.size()
    metadata["Metadata_n_plates"] = grouped["Metadata_Plate"].nunique()
    metadata["Metadata_replicate_cosine"] = grouped[feature_columns].apply(
        lambda group: mean_pairwise_cosine(group.to_numpy(dtype=np.float64))
    )

    result = metadata.join(consensus).reset_index()
    result = result[result["Metadata_n_replicates"] >= min_replicates].reset_index(drop=True)
    return result.drop(columns=["Metadata_Well"], errors="ignore")
