"""Per-plate normalization of well-level profiles to matched reference wells."""

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from scipy.stats import median_abs_deviation

MIN_REFERENCE_WELLS = 3


@dataclass(frozen=True)
class PlateNormalization:
    plate: str
    n_wells: int
    n_reference_wells: int
    n_degenerate_features: int


def normalize_plate(
    features: pd.DataFrame,
    reference_mask: np.ndarray,
    method: Literal["mad_robustize", "standardize"] = "mad_robustize",
    epsilon: float = 1e-6,
) -> tuple[pd.DataFrame, int]:
    """Scale every well against the reference wells of the same plate.

    ``mad_robustize``: (x - median_ref) / MAD_ref, MAD scaled to be consistent with the
    standard deviation of normal data. ``standardize``: (x - mean_ref) / std_ref.
    Features whose reference spread is <= ``epsilon`` cannot be scaled and become NaN
    for this plate (feature selection later drops them).

    Returns the normalized frame and the number of degenerate features.
    """
    reference_mask = np.asarray(reference_mask, dtype=bool)
    if reference_mask.shape[0] != len(features):
        raise ValueError("reference_mask must have one entry per well.")
    if reference_mask.sum() < MIN_REFERENCE_WELLS:
        raise ValueError(f"At least {MIN_REFERENCE_WELLS} reference wells are needed, got {int(reference_mask.sum())}.")

    values = features.to_numpy(dtype=np.float64)
    reference = values[reference_mask]
    if method == "mad_robustize":
        center = np.nanmedian(reference, axis=0)
        scale = median_abs_deviation(reference, axis=0, scale="normal", nan_policy="omit")
    elif method == "standardize":
        center = np.nanmean(reference, axis=0)
        scale = np.nanstd(reference, axis=0)
    else:
        raise ValueError(f"Unknown normalization method: {method}")

    degenerate = ~np.isfinite(scale) | (scale <= epsilon)
    scale = np.where(degenerate, np.nan, scale)
    normalized = (values - center) / scale
    return pd.DataFrame(normalized, index=features.index, columns=features.columns), int(degenerate.sum())


def normalize_by_plate(
    wells: pd.DataFrame,
    feature_columns: list[str],
    reference_mask: pd.Series,
    method: Literal["mad_robustize", "standardize"] = "mad_robustize",
    epsilon: float = 1e-6,
    plate_column: str = "Metadata_Plate",
) -> tuple[pd.DataFrame, list[PlateNormalization]]:
    """Normalize each plate independently; metadata columns are returned unchanged."""
    normalized = wells.copy()
    report = []
    for plate, index in wells.groupby(plate_column, sort=True).groups.items():
        mask = reference_mask.loc[index].to_numpy()
        try:
            scaled, n_degenerate = normalize_plate(wells.loc[index, feature_columns], mask, method, epsilon)
        except ValueError as exc:
            raise ValueError(f"Plate {plate}: {exc}") from exc
        normalized.loc[index, feature_columns] = scaled.to_numpy()
        report.append(PlateNormalization(str(plate), len(index), int(mask.sum()), n_degenerate))
    return normalized, report
