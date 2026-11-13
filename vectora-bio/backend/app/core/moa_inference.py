"""Similarity-based mechanism-of-action inference (weighted nearest-neighbour voting)."""

import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

from app.core.similarity import SimilarCompound

MOA_LABEL_SEPARATOR = "|"


@dataclass(frozen=True)
class MechanismCall:
    moa: str
    score: float
    rank: int
    vote_weight: float
    supporting_compounds: tuple[tuple[str, float], ...]


def split_moa_labels(value: str | Iterable[str] | None) -> list[str]:
    """Normalize an annotation to a list of distinct labels ('a|b' -> ['a', 'b']). Missing (None/NaN) -> []."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return []
    parts = value.split(MOA_LABEL_SEPARATOR) if isinstance(value, str) else list(value)
    labels: list[str] = []
    for part in parts:
        label = str(part).strip()
        if label and label not in labels:
            labels.append(label)
    return labels


def infer_mechanism(
    compound_id: str,
    similar_compounds: Sequence[SimilarCompound | tuple[str, float]],
    annotations: Mapping[str, str | Iterable[str] | None],
    top_k: int = 5,
) -> list[MechanismCall]:
    """Score MoA labels for ``compound_id`` from its annotated phenotypic neighbours.

    Each neighbour with positive similarity votes for each of its annotated labels with
    weight equal to its similarity. A label's score is its vote weight divided by the
    total weight of annotated, positively similar neighbours, so scores lie in [0, 1]
    and a label supported by every such neighbour scores 1. Neighbours with similarity
    <= 0, without annotations, or equal to the query are ignored. The query's own
    annotation is never used.

    Args:
        compound_id: Query compound.
        similar_compounds: Neighbours as ``SimilarCompound`` or ``(compound_id, similarity)``.
        annotations: Compound id -> MoA label(s), as 'a|b' strings or iterables.
        top_k: Maximum number of labels to return.

    Returns:
        Up to ``top_k`` mechanism calls, highest score first. Empty if no neighbour qualifies.
    """
    if top_k < 1:
        raise ValueError("top_k must be at least 1.")

    weights: dict[str, float] = defaultdict(float)
    support: dict[str, list[tuple[str, float]]] = defaultdict(list)
    total_weight = 0.0
    for neighbour in similar_compounds:
        neighbour_id, similarity = (
            (neighbour.candidate_id, neighbour.score) if isinstance(neighbour, SimilarCompound) else neighbour
        )
        if neighbour_id == compound_id or similarity <= 0:
            continue
        labels = split_moa_labels(annotations.get(neighbour_id))
        if not labels:
            continue
        total_weight += similarity
        for label in labels:
            weights[label] += similarity
            support[label].append((neighbour_id, float(similarity)))

    if total_weight == 0:
        return []

    ranked = sorted(weights.items(), key=lambda item: (-item[1], item[0]))[:top_k]
    return [
        MechanismCall(
            moa=label,
            score=weight / total_weight,
            rank=rank,
            vote_weight=weight,
            supporting_compounds=tuple(sorted(support[label], key=lambda pair: -pair[1])),
        )
        for rank, (label, weight) in enumerate(ranked, start=1)
    ]


def annotated_neighbor_count(
    compound_id: str,
    similar_compounds: Sequence[SimilarCompound | tuple[str, float]],
    annotations: Mapping[str, str | Iterable[str] | None],
) -> int:
    """Neighbours that could vote: positive similarity, annotated, and not the query itself."""
    count = 0
    for neighbour in similar_compounds:
        neighbour_id, similarity = (
            (neighbour.candidate_id, neighbour.score) if isinstance(neighbour, SimilarCompound) else neighbour
        )
        if neighbour_id != compound_id and similarity > 0 and split_moa_labels(annotations.get(neighbour_id)):
            count += 1
    return count


def leave_one_out_moa_calls(
    profiles: pd.DataFrame,
    annotations: Mapping[str, str | Iterable[str] | None],
    n_neighbors: int = 20,
    top_k: int = 5,
) -> pd.DataFrame:
    """MoA calls for every annotated compound with its own annotation hidden.

    Each annotated compound is treated as unknown: its ``n_neighbors`` most similar other
    compounds vote (``infer_mechanism``), and each returned call is marked correct if the
    label is among the compound's true labels. No compound ever sees its own annotation.

    Returns columns ``compound_id, moa, rank, score, n_supporting, correct``.
    """
    if n_neighbors < 1:
        raise ValueError("n_neighbors must be at least 1.")
    ids = [str(index) for index in profiles.index]
    values = profiles.to_numpy(dtype=np.float64)
    norms = np.linalg.norm(values, axis=1)
    if np.any(norms == 0):
        raise ValueError("profiles contain zero-norm rows.")
    unit = values / norms[:, None]

    rows = []
    for i, compound_id in enumerate(ids):
        truth = set(split_moa_labels(annotations.get(compound_id)))
        if not truth:
            continue
        similarity = unit @ unit[i]
        similarity[i] = -np.inf
        order = np.argsort(-similarity, kind="stable")[:n_neighbors]
        neighbours = [(ids[j], float(similarity[j])) for j in order]
        for call in infer_mechanism(compound_id, neighbours, annotations, top_k=top_k):
            rows.append(
                (compound_id, call.moa, call.rank, call.score, len(call.supporting_compounds), call.moa in truth)
            )
    return pd.DataFrame(rows, columns=["compound_id", "moa", "rank", "score", "n_supporting", "correct"])


@dataclass(frozen=True)
class ConfidenceCalibration:
    """Maps a vote share to the observed probability that such a call is correct.

    Fit with isotonic regression on leave-one-out calls, so confidence never decreases as the
    vote share increases.
    """

    model: IsotonicRegression
    n_calls: int
    n_compounds: int
    overall_precision: float
    top1_accuracy: float

    def predict(self, scores: Sequence[float] | np.ndarray) -> np.ndarray:
        return np.clip(self.model.predict(np.asarray(scores, dtype=np.float64)), 0.0, 1.0)


def fit_moa_confidence(calls: pd.DataFrame) -> ConfidenceCalibration | None:
    """Calibrate vote share -> P(correct) from ``leave_one_out_moa_calls`` output.

    Returns None when there are too few calls, or only one outcome, to calibrate.
    """
    if len(calls) < 2 or calls["correct"].nunique() < 2:
        return None
    model = IsotonicRegression(y_min=0.0, y_max=1.0, increasing=True, out_of_bounds="clip")
    model.fit(calls["score"].to_numpy(dtype=np.float64), calls["correct"].to_numpy(dtype=np.float64))
    top1 = calls[calls["rank"] == 1]
    return ConfidenceCalibration(
        model=model,
        n_calls=len(calls),
        n_compounds=int(calls["compound_id"].nunique()),
        overall_precision=float(calls["correct"].mean()),
        top1_accuracy=float(top1["correct"].mean()) if len(top1) else float("nan"),
    )
