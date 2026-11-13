"""Compound-to-compound phenotypic similarity."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from app.core.vectors import (
    Matrix,
    Vector,
    align_features,
    as_matrix,
    as_vector,
    check_nonzero_norm,
    top_k_order,
)


@dataclass(frozen=True)
class SimilarCompound:
    candidate_id: str
    score: float
    rank: int
    metadata: Mapping[str, Any] = field(default_factory=dict)


def calculate_cosine_similarity(query_profile: Vector, candidate_profiles: Matrix) -> NDArray[np.float64]:
    """Cosine similarity between one query profile and each candidate profile.

    Args:
        query_profile: 1-D feature vector (array or ``pd.Series`` indexed by feature name).
        candidate_profiles: 2-D array (n_candidates x n_features) or ``pd.DataFrame`` whose
            columns are feature names. A 1-D input is treated as a single candidate.
            When both inputs are labelled, candidates are aligned to the query's feature order.

    Returns:
        Array of shape (n_candidates,) with values in [-1, 1].

    Raises:
        ValueError: on dimension mismatch, missing/non-finite values, or zero-norm vectors.
    """
    query_profile, candidate_profiles = align_features(query_profile, candidate_profiles)
    query = as_vector(query_profile, "query_profile")
    candidates = as_matrix(candidate_profiles, query.size, "candidate_profiles")

    query_norm = np.linalg.norm(query)
    check_nonzero_norm(np.array([query_norm]), "query_profile")
    candidate_norms = np.linalg.norm(candidates, axis=1)
    labels = list(candidate_profiles.index) if isinstance(candidate_profiles, pd.DataFrame) else None
    check_nonzero_norm(candidate_norms, "candidate_profiles", labels)

    similarity = (candidates @ query) / (candidate_norms * query_norm)
    return np.clip(similarity, -1.0, 1.0)


def rank_similar_compounds(
    compound_id: str,
    profiles: pd.DataFrame,
    metadata: pd.DataFrame | None = None,
    top_k: int = 10,
) -> list[SimilarCompound]:
    """Rank other compounds by cosine similarity to ``compound_id``.

    Args:
        compound_id: Query compound; must be in ``profiles.index``.
        profiles: Consensus profiles, one row per compound (unique index), feature columns only.
        metadata: Optional table indexed by compound id (or with a ``compound_id`` column);
            non-null fields are attached to each result.
        top_k: Maximum number of results.

    Returns:
        Up to ``top_k`` compounds, excluding the query, highest similarity first.

    Raises:
        KeyError: if ``compound_id`` is not in ``profiles``.
        ValueError: if the profile index is not unique or the profiles fail vector validation.
    """
    if not profiles.index.is_unique:
        raise ValueError("profiles must have one row per compound (aggregate replicates first).")
    if compound_id not in profiles.index:
        raise KeyError(compound_id)
    candidates = profiles.drop(index=compound_id)
    if candidates.empty:
        return []

    scores = calculate_cosine_similarity(profiles.loc[compound_id], candidates)
    ids = [str(index) for index in candidates.index]
    lookup = _metadata_lookup(metadata)

    return [
        SimilarCompound(
            candidate_id=ids[position],
            score=float(scores[position]),
            rank=rank,
            metadata=lookup.get(ids[position], {}),
        )
        for rank, position in enumerate(top_k_order(scores, ids, top_k), start=1)
    ]


def _unit_rows(profiles: pd.DataFrame) -> NDArray[np.float64]:
    values = as_matrix(profiles, profiles.shape[1], "profiles")
    norms = np.linalg.norm(values, axis=1)
    check_nonzero_norm(norms, "profiles", list(profiles.index))
    return values / norms[:, None]


def pairwise_cosine_similarity(profiles: pd.DataFrame) -> pd.DataFrame:
    """Cosine similarity between every pair of rows, as a labelled square matrix.

    Memory grows with n^2; use ``similarity_background`` for large libraries.
    """
    if profiles.empty:
        raise ValueError("profiles is empty.")
    if not profiles.index.is_unique:
        raise ValueError("profiles must have one row per compound (aggregate replicates first).")
    unit = _unit_rows(profiles)
    matrix = np.clip(unit @ unit.T, -1.0, 1.0)
    return pd.DataFrame(matrix, index=profiles.index, columns=profiles.index)


def similarity_background(profiles: pd.DataFrame, max_pairs: int = 200_000, seed: int = 0) -> NDArray[np.float64]:
    """Sorted cosine similarities of distinct compound pairs: the reference distribution for scores.

    Uses every pair when there are at most ``max_pairs``; otherwise a reproducible random
    sample of ``max_pairs`` distinct-index pairs.
    """
    n = len(profiles)
    if n < 2:
        raise ValueError("At least two profiles are needed for a similarity background.")
    unit = _unit_rows(profiles)
    n_pairs = n * (n - 1) // 2
    if n_pairs <= max_pairs:
        rows, cols = np.triu_indices(n, k=1)
    else:
        rng = np.random.default_rng(seed)
        rows = rng.integers(0, n, size=max_pairs)
        cols = (rows + rng.integers(1, n, size=max_pairs)) % n  # never equal to rows
    values = np.einsum("ij,ij->i", unit[rows], unit[cols])
    return np.sort(np.clip(values, -1.0, 1.0))


def cross_similarity_background(
    rows: pd.DataFrame,
    columns: pd.DataFrame,
    *,
    absolute: bool = False,
    max_pairs: int = 500_000,
    seed: int = 0,
) -> NDArray[np.float64]:
    """Sorted cosine similarities between every row of ``rows`` and every row of ``columns``.

    E.g. all compound-reagent pairs, as the reference for compound-to-gene match scores.
    ``absolute`` returns |cosine|. Above ``max_pairs`` a reproducible random sample of pairs is used.
    """
    if rows.empty or columns.empty:
        raise ValueError("Both profile sets must be non-empty.")
    if set(rows.columns) != set(columns.columns):
        raise ValueError("Profile sets have different features.")
    a, b = _unit_rows(rows), _unit_rows(columns[list(rows.columns)])
    if a.shape[0] * b.shape[0] <= max_pairs:
        values = (a @ b.T).ravel()
    else:
        rng = np.random.default_rng(seed)
        i = rng.integers(0, a.shape[0], size=max_pairs)
        j = rng.integers(0, b.shape[0], size=max_pairs)
        values = np.einsum("ij,ij->i", a[i], b[j])
    values = np.clip(values, -1.0, 1.0)
    return np.sort(np.abs(values) if absolute else values)


def score_percentile(scores: NDArray[np.float64] | float, background: NDArray[np.float64]) -> NDArray[np.float64]:
    """Percentage of background similarities that are <= each score (0-100).

    ``background`` must be sorted ascending, as ``similarity_background`` returns it.
    """
    if background.size == 0:
        raise ValueError("background is empty.")
    positions = np.searchsorted(background, np.asarray(scores, dtype=np.float64), side="right")
    return 100.0 * positions / background.size


def _metadata_lookup(metadata: pd.DataFrame | None) -> dict[str, dict[str, Any]]:
    if metadata is None or metadata.empty:
        return {}
    table = metadata.set_index("compound_id") if "compound_id" in metadata.columns else metadata
    table = table[~table.index.duplicated(keep="first")]
    return {
        str(index): {key: value for key, value in row.items() if pd.notna(value)}
        for index, row in table.to_dict(orient="index").items()
    }
