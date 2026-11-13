"""Compound-to-gene matching and candidate target prioritization.

Two separate questions:

* **Matching** (``match_compound_to_genes``): which genetic perturbations produce cellular
  profiles that resemble this compound's? Ranked by absolute cosine by default, because
  knockout and overexpression profiles of a target do not reliably mirror each other; the
  signed value is kept as evidence.
* **Prioritization** (``rank_candidate_targets``): which genes have the strongest combined
  evidence as candidate targets? Combines the phenotypic match (as a percentile of all
  compound-reagent similarities) with "neighbour target" evidence: genes that the query's
  most phenotypically similar compounds are annotated to act on.

Neither establishes a direct molecular target; results are candidate associations.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
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


@dataclass(frozen=True)
class PrioritizedTarget:
    """A candidate target gene with the evidence behind its priority score."""

    gene_key: str
    gene_symbol: str | None
    priority: float
    rank: int
    phenotypic_score: float
    neighbor_support: float
    reagents: tuple[GeneMatch, ...]
    reagent_percentiles: Mapping[str, float]
    supporting_compounds: tuple[tuple[str, float], ...] = ()
    n_strong_reagents: int = 0


def neighbor_target_support(
    compound_id: str,
    neighbors: Sequence[tuple[str, float]],
    compound_targets: Mapping[str, Iterable[str]],
) -> dict[str, tuple[float, tuple[tuple[str, float], ...]]]:
    """Similarity-weighted share of the query's neighbours annotated to act on each gene.

    Each neighbour with positive similarity contributes its similarity to every gene in its
    annotated target list; totals are divided by the summed similarity of all positive
    neighbours, giving values in [0, 1]. The query's own annotation is never used.

    Returns gene symbol -> (support, ((compound_id, similarity), ...) of contributing neighbours).
    """
    positive = [(cid, float(sim)) for cid, sim in neighbors if cid != compound_id and sim > 0]
    total = sum(sim for _, sim in positive)
    if total == 0:
        return {}
    weights: dict[str, float] = defaultdict(float)
    contributors: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for cid, sim in positive:
        for gene in {str(g).strip() for g in compound_targets.get(cid, ()) if str(g).strip()}:
            weights[gene] += sim
            contributors[gene].append((cid, sim))
    return {
        gene: (weight / total, tuple(sorted(contributors[gene], key=lambda pair: -pair[1])))
        for gene, weight in weights.items()
    }


def rank_candidate_targets(
    matches: Sequence[GeneMatch],
    match_percentiles: Mapping[str, float],
    neighbor_support: Mapping[str, tuple[float, tuple[tuple[str, float], ...]]] | None = None,
    *,
    neighbor_weight: float = 2.0,
    strong_percentile: float = 0.9,
) -> list[PrioritizedTarget]:
    """Combine phenotypic matching and neighbour-target evidence into one priority per gene.

    ``phenotypic_score`` is the best reagent's match percentile (0-1) for the gene.
    ``neighbor_support`` (0-1) comes from ``neighbor_target_support`` keyed by gene symbol.
    ``priority = (phenotypic_score + neighbor_weight * neighbor_support) / (1 + neighbor_weight)``.
    ``n_strong_reagents`` counts reagents at or above ``strong_percentile``: agreement between
    independent reagents for the same gene, shown as evidence.

    Ties are broken by phenotypic score, then gene key.
    """
    if neighbor_weight < 0:
        raise ValueError("neighbor_weight must be non-negative.")
    neighbor_support = neighbor_support or {}
    groups: dict[str, list[GeneMatch]] = defaultdict(list)
    for match in matches:
        groups[match.gene_id or match.gene_symbol or match.perturbation_id].append(match)

    scored = []
    for gene_key, group in groups.items():
        percentiles = {m.perturbation_id: float(match_percentiles.get(m.perturbation_id, 0.0)) for m in group}
        reagents = tuple(sorted(group, key=lambda m: (-percentiles[m.perturbation_id], m.perturbation_id)))
        symbol = next((m.gene_symbol for m in reagents if m.gene_symbol), None)
        phenotypic = max(percentiles.values())
        support, contributors = neighbor_support.get(symbol or gene_key, (0.0, ()))
        priority = (phenotypic + neighbor_weight * support) / (1 + neighbor_weight)
        strong = sum(value >= strong_percentile for value in percentiles.values())
        scored.append((gene_key, symbol, priority, phenotypic, support, reagents, percentiles, contributors, strong))

    scored.sort(key=lambda item: (-item[2], -item[3], item[0]))
    return [
        PrioritizedTarget(
            gene_key=gene_key,
            gene_symbol=symbol,
            priority=float(priority),
            rank=rank,
            phenotypic_score=float(phenotypic),
            neighbor_support=float(support),
            reagents=reagents,
            reagent_percentiles=percentiles,
            supporting_compounds=contributors,
            n_strong_reagents=int(strong),
        )
        for rank, (
            gene_key,
            symbol,
            priority,
            phenotypic,
            support,
            reagents,
            percentiles,
            contributors,
            strong,
        ) in enumerate(scored, start=1)
    ]
