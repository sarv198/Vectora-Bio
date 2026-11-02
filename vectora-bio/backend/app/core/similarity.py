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


def _metadata_lookup(metadata: pd.DataFrame | None) -> dict[str, dict[str, Any]]:
    if metadata is None or metadata.empty:
        return {}
    table = metadata.set_index("compound_id") if "compound_id" in metadata.columns else metadata
    table = table[~table.index.duplicated(keep="first")]
    return {
        str(index): {key: value for key, value in row.items() if pd.notna(value)}
        for index, row in table.to_dict(orient="index").items()
    }
