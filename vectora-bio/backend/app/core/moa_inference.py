"""Similarity-based mechanism-of-action inference (weighted nearest-neighbour voting)."""

import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

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
