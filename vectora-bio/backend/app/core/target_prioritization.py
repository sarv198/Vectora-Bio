"""Compound-to-gene matching and candidate target prioritization.

A compound that inhibits a target is expected to resemble loss-of-function of that
gene and may anti-correlate with its overexpression, so matching can rank by the
absolute cosine similarity while keeping the signed value as evidence.
"""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from app.core.similarity import calculate_cosine_similarity
from app.core.vectors import Vector, top_k_order


@dataclass(frozen=True)
class GeneMatch:
    perturbation_id: str
    similarity: float
    score: float
    rank: int
    gene_id: str | None = None
    gene_symbol: str | None = None
    perturbation_type: str | None = None


@dataclass(frozen=True)
class TargetCandidate:
    gene_key: str
    gene_symbol: str | None
    score: float
    rank: int
    supporting_matches: tuple[GeneMatch, ...]
    annotations: Mapping[str, Any] = field(default_factory=dict)

    @property
    def n_supporting_perturbations(self) -> int:
        return len(self.supporting_matches)


def match_compound_to_genes(
    compound_profile: Vector,
    genetic_profiles: pd.DataFrame,
    top_k: int = 10,
    *,
    perturbation_info: pd.DataFrame | None = None,
    use_absolute_similarity: bool = True,
) -> list[GeneMatch]:
    """Rank genetic perturbation profiles by similarity to a compound profile.

    Args:
        compound_profile: Consensus compound profile (``pd.Series`` by feature name, or array).
        genetic_profiles: One row per genetic perturbation (unique index), feature columns only.
        top_k: Maximum number of matches.
        perturbation_info: Optional table indexed by perturbation id with ``gene_id``,
            ``gene_symbol`` and ``perturbation_type`` columns.
        use_absolute_similarity: Rank by |cosine| instead of signed cosine.

    Returns:
        Matches ordered by ``score`` (|cosine| or cosine), highest first.
    """
    if not genetic_profiles.index.is_unique:
        raise ValueError("genetic_profiles must have one row per perturbation (aggregate replicates first).")
    if genetic_profiles.empty:
        return []
    similarity = calculate_cosine_similarity(compound_profile, genetic_profiles)
    scores = np.abs(similarity) if use_absolute_similarity else similarity
    ids = [str(index) for index in genetic_profiles.index]
    info = _info_lookup(perturbation_info)

    matches = []
    for rank, position in enumerate(top_k_order(scores, ids, top_k), start=1):
        details = info.get(ids[position], {})
        matches.append(
            GeneMatch(
                perturbation_id=ids[position],
                similarity=float(similarity[position]),
                score=float(scores[position]),
                rank=rank,
                gene_id=_optional_str(details.get("gene_id")),
                gene_symbol=_optional_str(details.get("gene_symbol")),
                perturbation_type=_optional_str(details.get("perturbation_type")),
            )
        )
    return matches


def prioritize_candidate_targets(
    matches: Sequence[GeneMatch],
    annotations: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[TargetCandidate]:
    """Aggregate perturbation-level matches into a ranked list of candidate target genes.

    Matches are grouped by ``gene_id`` (falling back to ``gene_symbol``, then the
    perturbation id). A gene's score is the maximum match score over its
    perturbations; ties are broken by the number of supporting perturbations.

    Args:
        matches: Output of ``match_compound_to_genes``. Pass a large ``top_k`` there so
            all perturbations of a gene are seen before aggregation.
        annotations: Optional per-gene annotations keyed by gene id or gene symbol. They are
            attached to candidates as evidence only and do not change the score.

    Returns:
        Candidates ordered by score, highest first.
    """
    annotations = annotations or {}
    groups: dict[str, list[GeneMatch]] = defaultdict(list)
    for match in matches:
        groups[match.gene_id or match.gene_symbol or match.perturbation_id].append(match)

    candidates = []
    for gene_key, group in groups.items():
        group_sorted = tuple(sorted(group, key=lambda m: (-m.score, m.perturbation_id)))
        symbol = next((m.gene_symbol for m in group_sorted if m.gene_symbol), None)
        gene_annotations = dict(annotations.get(gene_key, {}))
        if symbol is not None:
            gene_annotations.update(annotations.get(symbol, {}))
        candidates.append((gene_key, symbol, group_sorted[0].score, group_sorted, gene_annotations))

    candidates.sort(key=lambda c: (-c[2], -len(c[3]), c[0]))
    return [
        TargetCandidate(
            gene_key=gene_key,
            gene_symbol=symbol,
            score=float(score),
            rank=rank,
            supporting_matches=group,
            annotations=gene_annotations,
        )
        for rank, (gene_key, symbol, score, group, gene_annotations) in enumerate(candidates, start=1)
    ]


def _info_lookup(info: pd.DataFrame | None) -> dict[str, dict[str, Any]]:
    if info is None or info.empty:
        return {}
    table = info.set_index("perturbation_id") if "perturbation_id" in info.columns else info
    table = table[~table.index.duplicated(keep="first")]
    return {str(index): row for index, row in table.to_dict(orient="index").items()}


def _optional_str(value: object) -> str | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    text = str(value).strip()
    return text or None
