"""Is a compound's profile a real, specific response? Strength, density and generic-response checks.

All three compare compounds with what matched control wells (e.g. DMSO) produce by chance,
or with the compound population itself, so no fixed thresholds are hard-coded.

* **Response strength**: the norm of a consensus profile, as a percentile of norms obtained by
  taking the median of ``n_replicates`` random control wells (one per plate when possible).
  Profiles inside that null are indistinguishable from noise.
* **Cell density proxy**: in Cell Painting, loss of cells (toxicity, arrested growth) shows up
  as cells being farther apart and touching less. Uses neighbour features when present.
* **Generic response**: cosine with the average direction of all compound profiles. Many
  unrelated compounds share this direction (often stress or toxicity), so a profile dominated
  by it says little about a specific mechanism.
"""

from collections.abc import Sequence

import numpy as np
import pandas as pd
from numpy.typing import NDArray

# Neighbour features whose increase (+1) or decrease (-1) indicates fewer, sparser cells.
DENSITY_FEATURES: dict[str, int] = {
    "Cells_Neighbors_FirstClosestDistance_5": 1,
    "Cells_Neighbors_PercentTouching_Adjacent": -1,
    "Nuclei_Neighbors_NumberOfNeighbors_1": -1,
}


def pseudo_replicate_consensus(
    control_wells: pd.DataFrame,
    features: Sequence[str],
    n_replicates: int,
    *,
    plate_column: str = "Metadata_Plate",
    n_samples: int = 2000,
    seed: int = 0,
) -> NDArray[np.float64]:
    """Median profiles of ``n_replicates`` randomly drawn control wells, ``n_samples`` times.

    Wells are drawn from different plates in turn (mirroring replicate plates) when the
    plate column is present. Returns an array of shape (n_samples, n_features).
    """
    if n_replicates < 1:
        raise ValueError("n_replicates must be at least 1.")
    if control_wells.empty:
        raise ValueError("control_wells is empty.")
    rng = np.random.default_rng(seed)
    if plate_column in control_wells.columns and control_wells[plate_column].nunique() > 1:
        pools = [group[list(features)].to_numpy(np.float64) for _, group in control_wells.groupby(plate_column)]
    else:
        pools = [control_wells[list(features)].to_numpy(np.float64)]
    samples = np.empty((n_samples, len(features)))
    for s in range(n_samples):
        draws = [
            pools[(s + r) % len(pools)][rng.integers(len(pools[(s + r) % len(pools)]))] for r in range(n_replicates)
        ]
        samples[s] = np.median(np.stack(draws), axis=0)
    return samples


def strength_null(pseudo_consensus: NDArray[np.float64]) -> NDArray[np.float64]:
    """Sorted norms of pseudo-replicate control consensus profiles."""
    return np.sort(np.linalg.norm(pseudo_consensus, axis=1))


def empirical_percentile(
    values: NDArray[np.float64] | Sequence[float], null: NDArray[np.float64]
) -> NDArray[np.float64]:
    """Fraction (0-1) of the sorted null at or below each value."""
    if null.size == 0:
        raise ValueError("null distribution is empty.")
    return np.searchsorted(null, np.asarray(values, dtype=np.float64), side="right") / null.size


def density_scores(profiles: pd.DataFrame) -> pd.Series | None:
    """Cell-density-loss proxy per profile: mean of signed neighbour features (higher = sparser).

    Returns None when none of ``DENSITY_FEATURES`` are present.
    """
    present = {name: sign for name, sign in DENSITY_FEATURES.items() if name in profiles.columns}
    if not present:
        return None
    signed = sum(profiles[name].astype(np.float64) * sign for name, sign in present.items())
    return signed / len(present)


def generic_response_direction(profiles: pd.DataFrame) -> NDArray[np.float64]:
    """Unit vector of the average direction of all (non-zero) profiles."""
    values = profiles.to_numpy(np.float64)
    norms = np.linalg.norm(values, axis=1)
    unit = values[norms > 0] / norms[norms > 0, None]
    if unit.size == 0:
        raise ValueError("No non-zero profiles.")
    mean = unit.mean(axis=0)
    length = np.linalg.norm(mean)
    if length == 0:
        raise ValueError("Profiles have no shared direction.")
    return mean / length


def generic_response_scores(profiles: pd.DataFrame, direction: NDArray[np.float64]) -> pd.Series:
    """Cosine of each profile with the generic response direction."""
    values = profiles.to_numpy(np.float64)
    norms = np.linalg.norm(values, axis=1)
    scores = np.divide(values @ direction, norms, out=np.zeros(len(values)), where=norms > 0)
    return pd.Series(scores, index=profiles.index)
