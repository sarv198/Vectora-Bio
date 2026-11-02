"""Input validation shared by the scientific modules."""

from collections.abc import Sequence

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike, NDArray

ZERO_NORM_TOLERANCE = 1e-12

Vector = ArrayLike | pd.Series
Matrix = ArrayLike | pd.DataFrame


def as_vector(values: Vector, name: str = "vector") -> NDArray[np.float64]:
    """A finite, non-empty 1-D float array."""
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1:
        raise ValueError(f"{name} must be 1-dimensional, got shape {array.shape}.")
    if array.size == 0:
        raise ValueError(f"{name} is empty.")
    if not np.all(np.isfinite(array)):
        n_bad = int((~np.isfinite(array)).sum())
        raise ValueError(f"{name} contains {n_bad} missing or non-finite value(s).")
    return array


def as_matrix(values: Matrix, n_features: int, name: str = "matrix") -> NDArray[np.float64]:
    """A finite 2-D float array with ``n_features`` columns. A 1-D input is one row."""
    array = np.asarray(values, dtype=np.float64)
    if array.ndim == 1:
        array = array.reshape(1, -1)
    if array.ndim != 2:
        raise ValueError(f"{name} must be 2-dimensional, got shape {array.shape}.")
    if array.shape[1] != n_features:
        raise ValueError(f"{name} has {array.shape[1]} feature(s) but the query has {n_features}.")
    if not np.all(np.isfinite(array)):
        bad_rows = np.flatnonzero(~np.isfinite(array).all(axis=1))
        raise ValueError(
            f"{name} contains missing or non-finite values in {bad_rows.size} row(s), "
            f"e.g. rows {bad_rows[:5].tolist()}."
        )
    return array


def align_features(query: Vector, candidates: Matrix) -> tuple[Vector, Matrix]:
    """Reorder labelled candidates to the query's feature order; reject mismatched feature sets.

    Unlabelled (array) inputs are returned unchanged and checked by position only.
    """
    if not isinstance(query, pd.Series) or not isinstance(candidates, (pd.Series, pd.DataFrame)):
        return query, candidates
    query_features = list(query.index)
    candidate_features = candidates.index if isinstance(candidates, pd.Series) else candidates.columns
    if set(query_features) != set(candidate_features):
        only_query = sorted(set(query_features) - set(candidate_features))
        only_candidates = sorted(set(candidate_features) - set(query_features))
        raise ValueError(
            "Feature sets differ between query and candidates: "
            f"{len(only_query)} only in query (e.g. {only_query[:3]}), "
            f"{len(only_candidates)} only in candidates (e.g. {only_candidates[:3]})."
        )
    if isinstance(candidates, pd.Series):
        return query, candidates.reindex(query_features)
    return query, candidates[query_features]


def check_nonzero_norm(norms: NDArray[np.float64], name: str, labels: Sequence[object] | None = None) -> None:
    zero = np.flatnonzero(norms <= ZERO_NORM_TOLERANCE)
    if zero.size:
        examples = [labels[i] for i in zero[:5]] if labels is not None else zero[:5].tolist()
        raise ValueError(f"{name} has {zero.size} zero-norm vector(s) (cosine is undefined), e.g. {examples}.")


def top_k_order(scores: NDArray[np.float64], ids: Sequence[str], top_k: int) -> list[int]:
    """Indices of the ``top_k`` highest scores; ties broken by identifier for determinism."""
    if top_k < 1:
        raise ValueError("top_k must be at least 1.")
    order = np.lexsort((np.asarray(ids, dtype=str), -scores))
    return order[:top_k].tolist()
