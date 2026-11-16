"""Phenotypic rescue: rank compounds whose profile opposes a perturbation signature.

Both inputs are expected relative to matched controls (e.g. control-normalized
profiles, or a perturbation consensus minus the control consensus), so that
"opposite direction" means "towards the control phenotype".
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from app.core.similarity import calculate_cosine_similarity
from app.core.vectors import Matrix, Vector, top_k_order


@dataclass(frozen=True)
class ReversalCandidate:
    compound_id: str
    score: float
    rank: int


def calculate_reversal_score(compound_profile: Vector, perturbation_signature: Vector) -> float:
    """Negative cosine similarity between a compound profile and a perturbation signature.

    Returns a value in [-1, 1]: 1 means the compound's profile points exactly opposite
    the signature, 0 means orthogonal, -1 means it mimics the perturbation.
    """
    return float(-_reversal_scores(perturbation_signature, compound_profile)[0])


def rank_reversal_candidates(
    perturbation_signature: Vector,
    compound_profiles: pd.DataFrame,
    top_k: int = 10,
) -> list[ReversalCandidate]:
    """Rank compounds (rows of ``compound_profiles``) by reversal score, highest first."""
    if not compound_profiles.index.is_unique:
        raise ValueError("compound_profiles must have one row per compound (aggregate replicates first).")
    if compound_profiles.empty:
        return []
    scores = -_reversal_scores(perturbation_signature, compound_profiles)
    ids = [str(index) for index in compound_profiles.index]
    return [
        ReversalCandidate(compound_id=ids[position], score=float(scores[position]), rank=rank)
        for rank, position in enumerate(top_k_order(scores, ids, top_k), start=1)
    ]


def _reversal_scores(signature: Vector, profiles: Matrix) -> NDArray[np.float64]:
    return calculate_cosine_similarity(signature, profiles)


def reversal_contributions(compound_profile: pd.Series, perturbation_signature: pd.Series) -> pd.Series:
    """Per-feature terms of the reversal score; they sum exactly to ``calculate_reversal_score``.

    Term i is ``-c_i * s_i / (|c| |s|)``: positive where the compound moves feature i opposite to
    the perturbation (driving reversal), negative where it moves it the same way.
    """
    signature = perturbation_signature.astype(np.float64)
    compound = compound_profile.astype(np.float64).reindex(signature.index)
    if compound.isna().any():
        raise ValueError("compound_profile lacks features present in the signature.")
    denominator = np.linalg.norm(compound.to_numpy()) * np.linalg.norm(signature.to_numpy())
    if denominator == 0:
        raise ValueError("Zero-norm compound profile or signature.")
    return -(compound * signature) / denominator
