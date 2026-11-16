"""Analysis use cases: load the required data, call the scientific modules, build predictions."""

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.features import describe_feature, group_contributions
from app.core.moa_inference import (
    annotated_neighbor_count,
    fit_moa_confidence,
    infer_mechanism,
    leave_one_out_moa_calls,
    split_moa_labels,
)
from app.core.phenotype_quality import (
    density_scores,
    empirical_percentile,
    generic_response_direction,
    generic_response_scores,
    pseudo_replicate_consensus,
    strength_null,
)
from app.core.reversal import rank_reversal_candidates, reversal_contributions
from app.core.similarity import (
    calculate_cosine_similarity,
    cross_similarity_background,
    rank_similar_compounds,
    score_percentile,
)
from app.core.target_prioritization import (
    GeneMatch,
    match_compound_to_genes,
    neighbor_target_support,
    rank_candidate_targets,
)
from app.data.loaders import ConsensusProfiles, check_feature_compatibility
from app.data.profile_store import MODALITY_COLUMN, ProfileStore
from app.db.models import AnalysisRunRecord, PredictionRecord
from app.errors import DataNotLoadedError, FeatureMismatchError, InvalidQueryError, NotFoundError
from app.schemas.common import ProfileType
from app.schemas.prediction import (
    AnalysisResponse,
    AnalysisSummary,
    EvidenceItem,
    MoaInferenceRequest,
    Prediction,
    PredictionType,
    RescueSearchRequest,
    SimilarityRequest,
    TargetMatchRequest,
    TargetPrioritizationRequest,
)
from app.services import metadata_service

logger = logging.getLogger(__name__)

MAX_EVIDENCE_ITEMS = 5
REPLICATE_COSINE_COLUMN = "Metadata_replicate_cosine"
MOA_CALIBRATION_TOP_K = 5
MAX_CONTRIBUTING_FEATURES = 8
# Stress flags: denser cell loss than 99% of control pseudo-replicates, or among the 10% of
# compounds most aligned with the generic response direction.
STRESS_DENSITY_PERCENTILE = 0.99
STRESS_GENERIC_PERCENTILE = 0.90


def _check_top_k(settings: Settings, *values: int) -> None:
    for value in values:
        if value > settings.max_top_k:
            raise InvalidQueryError(f"Requested {value} results; the maximum is {settings.max_top_k}.")


def _require_features_match(datasets: dict[str, list[str]]) -> None:
    report = check_feature_compatibility(datasets)
    if not report.compatible:
        raise FeatureMismatchError(
            "Profile datasets do not share the same feature columns; re-import them with a common feature set.",
            details=report.to_dict(),
        )


def _query_profile(consensus: ConsensusProfiles, compound_id: str) -> pd.Series:
    if compound_id not in consensus.features.index:
        raise NotFoundError(
            f"No profile for compound '{compound_id}' in the selected cell line/timepoint.",
            details={"n_compounds_in_context": len(consensus)},
        )
    return consensus.features.loc[compound_id]


def _query_context(consensus: ConsensusProfiles, perturbation_id: str) -> tuple[str, float]:
    row = consensus.context.loc[perturbation_id]
    return str(row["cell_line"]), float(row["timepoint"])


def _annotation_map(annotations: pd.DataFrame, column: str) -> dict[str, str]:
    if annotations.empty:
        return {}
    present = annotations.dropna(subset=[column])
    return dict(zip(present["compound_id"].astype(str), present[column].astype(str), strict=True))


def _safe_value(value: Any) -> Any:
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    return value


def _record_run(db: Session, settings: Settings, response: AnalysisResponse) -> AnalysisResponse:
    """Persist the run when enabled. Failure to persist never fails the request."""
    if not settings.persist_analysis_runs:
        return response
    try:
        run = AnalysisRunRecord(
            prediction_type=response.prediction_type.value,
            query_id=response.query_id,
            parameters=response.parameters,
            predictions=[
                PredictionRecord(
                    query_id=p.query_id,
                    candidate_id=p.candidate_id,
                    prediction_type=p.prediction_type.value,
                    score=p.score,
                    rank=p.rank,
                    supporting_evidence=[e.model_dump() for e in p.supporting_evidence],
                )
                for p in response.predictions
            ],
        )
        db.add(run)
        db.commit()
        return response.model_copy(update={"run_id": run.id})
    except SQLAlchemyError:
        db.rollback()
        logger.warning("Could not persist analysis run for %s", response.query_id, exc_info=True)
        return response


def compound_similarity(
    request: SimilarityRequest, *, store: ProfileStore, db: Session, settings: Settings
) -> AnalysisResponse:
    """Rank compounds by cosine similarity of consensus profiles, with annotations and score context.

    Each score is also expressed as a percentile of all pairwise compound similarities in the
    same context, so a value like 0.6 can be read against what is typical for this dataset.
    """
    _check_top_k(settings, request.top_k)
    consensus = store.consensus(ProfileType.COMPOUND, request.cell_line, request.timepoint)
    _query_profile(consensus, request.compound_id)
    cell_line, timepoint = _query_context(consensus, request.compound_id)

    info = _compound_info(metadata_service.compound_annotations(db))
    reproducibility = store.metadata_values(ProfileType.COMPOUND, REPLICATE_COSINE_COLUMN)
    query_info = info.get(request.compound_id, {})
    query_moa = set(split_moa_labels(query_info.get("moa")))
    query_reproducibility = _finite_or_none(reproducibility.get(request.compound_id))

    candidates = consensus.features.index.drop(request.compound_id)
    n_before_filters = len(candidates)
    messages: list[str] = []
    if request.annotated_only:
        candidates = candidates[[bool(info.get(c, {}).get("moa")) for c in candidates]]
    if request.min_replicate_cosine is not None:
        if reproducibility.empty:
            messages.append("Replicate reproducibility is not recorded in these profiles; that filter was ignored.")
        else:
            values = reproducibility.reindex(candidates).astype(float)
            candidates = candidates[(values >= request.min_replicate_cosine).to_numpy()]
            if query_reproducibility is not None and query_reproducibility < request.min_replicate_cosine:
                messages.append(
                    f"The query's own replicates agree less (cosine {query_reproducibility:.2f}) than the "
                    "reproducibility threshold, so its neighbours may be unreliable."
                )
    if len(candidates) < n_before_filters:
        messages.append(f"{n_before_filters - len(candidates)} of {n_before_filters} candidates excluded by filters.")

    results = rank_similar_compounds(
        request.compound_id,
        consensus.features.loc[[request.compound_id, *candidates]],
        top_k=request.top_k,
    )
    background = store.similarity_background(ProfileType.COMPOUND, request.cell_line, request.timepoint)
    percentiles = score_percentile(np.array([r.score for r in results]), background) if results else []

    predictions = []
    for result, percentile in zip(results, percentiles, strict=True):
        candidate = info.get(result.candidate_id, {})
        candidate_moa = split_moa_labels(candidate.get("moa"))
        shared = sorted(query_moa & set(candidate_moa))
        evidence = [
            EvidenceItem(
                evidence_type="phenotypic_similarity",
                description=f"Cosine similarity of consensus profiles ({len(consensus.feature_columns)} features).",
                value=result.score,
                source_id=result.candidate_id,
            ),
            EvidenceItem(
                evidence_type="score_context",
                description=(f"Higher than {percentile:.1f}% of {background.size:,} compound pairs in this context."),
                value=float(percentile),
            ),
        ]
        if candidate_moa:
            evidence.append(
                EvidenceItem(
                    evidence_type="annotation",
                    description=(
                        f"Annotated MoA: {' | '.join(candidate_moa)}"
                        + (f" (shared with query: {', '.join(shared)})" if shared else "")
                    ),
                    source_id=result.candidate_id,
                )
            )
        predictions.append(
            Prediction(
                query_id=request.compound_id,
                candidate_id=result.candidate_id,
                prediction_type=PredictionType.COMPOUND_SIMILARITY,
                score=result.score,
                rank=result.rank,
                supporting_evidence=evidence,
                candidate_name=candidate.get("compound_name"),
                candidate_annotations={
                    "moa": candidate.get("moa"),
                    "known_target": candidate.get("known_target"),
                    "shared_moa": shared,
                    "score_percentile": round(float(percentile), 2),
                    "replicate_cosine": _finite_or_none(reproducibility.get(result.candidate_id)),
                },
            )
        )

    response = AnalysisResponse(
        query_id=request.compound_id,
        query_name=query_info.get("compound_name"),
        query_annotations={
            "moa": query_info.get("moa"),
            "known_target": query_info.get("known_target"),
            "replicate_cosine": query_reproducibility,
        },
        prediction_type=PredictionType.COMPOUND_SIMILARITY,
        predictions=predictions,
        parameters={"metric": "cosine", "consensus": settings.consensus_method, **request.model_dump(mode="json")},
        summary=AnalysisSummary(
            n_candidates=len(candidates),
            n_features=len(consensus.feature_columns),
            cell_line=cell_line,
            timepoint=timepoint,
        ),
        message=" ".join(messages) or None,
    )
    return _record_run(db, settings, response)


def _compound_info(annotations: pd.DataFrame) -> dict[str, dict[str, str | None]]:
    """compound_id -> {compound_name, moa, known_target}, with missing values as None."""
    if annotations.empty:
        return {}
    table = annotations.set_index("compound_id")[["compound_name", "moa", "known_target"]]
    table = table.astype(object).where(table.notna(), None)
    return table.to_dict(orient="index")


def _finite_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


@dataclass
class _TargetContext:
    compounds: ConsensusProfiles
    query: pd.Series
    cell_line: str
    timepoint: float
    genetic_features: pd.DataFrame
    info: pd.DataFrame
    matches: list[GeneMatch]
    percentiles: dict[str, float]
    n_unannotated: int


def _target_context(request: TargetMatchRequest, store: ProfileStore, db: Session) -> _TargetContext:
    """Shared setup for matching and prioritization: profiles, gene info, every reagent's match and percentile."""
    compounds = store.consensus(ProfileType.COMPOUND, request.cell_line, request.timepoint)
    query = _query_profile(compounds, request.compound_id)
    cell_line, timepoint = _query_context(compounds, request.compound_id)

    genetic = store.consensus(ProfileType.GENETIC, cell_line, request.genetic_timepoint)
    _require_features_match(
        {"compound_profiles": compounds.feature_columns, "genetic_profiles": genetic.feature_columns}
    )
    info = metadata_service.perturbation_info(db)

    genetic_features = genetic.features
    if request.perturbation_types:
        allowed = {value.value for value in request.perturbation_types}
        keep = info.index[info["perturbation_type"].isin(allowed)]
        genetic_features = genetic_features.loc[genetic_features.index.intersection(keep)]
    if genetic_features.empty:
        raise InvalidQueryError("No genetic profiles match the selected perturbation types in this context.")
    unannotated = genetic_features.index.difference(info.index)
    if len(unannotated) == len(genetic_features):
        raise DataNotLoadedError(
            [metadata_service.GENETIC_METADATA],
            message="None of the genetic profiles in this context have gene metadata.",
        )

    matches = match_compound_to_genes(
        query,
        genetic_features,
        top_k=len(genetic_features),
        perturbation_info=info,
        use_absolute_similarity=request.use_absolute_similarity,
    )
    # Each match is placed among all compound-reagent similarities in the same contexts.
    background = store.memo(
        (ProfileType.COMPOUND, ProfileType.GENETIC),
        (
            "compound_reagent_background",
            cell_line,
            request.timepoint,
            request.genetic_timepoint,
            tuple(sorted(genetic_features.index)),
            request.use_absolute_similarity,
        ),
        lambda: cross_similarity_background(
            compounds.features, genetic_features, absolute=request.use_absolute_similarity
        ),
    )
    scores = np.array([m.score for m in matches])
    percentiles = dict(
        zip([m.perturbation_id for m in matches], score_percentile(scores, background) / 100, strict=True)
    )
    return _TargetContext(
        compounds=compounds,
        query=query,
        cell_line=cell_line,
        timepoint=timepoint,
        genetic_features=genetic_features,
        info=info,
        matches=matches,
        percentiles=percentiles,
        n_unannotated=len(unannotated),
    )


def _target_summary(context: _TargetContext) -> AnalysisSummary:
    return AnalysisSummary(
        n_candidates=len(context.genetic_features),
        n_features=len(context.compounds.feature_columns),
        cell_line=context.cell_line,
        timepoint=context.timepoint,
    )


def match_genes(
    request: TargetMatchRequest, *, store: ProfileStore, db: Session, settings: Settings
) -> AnalysisResponse:
    """Compound-to-gene matching: genetic reagents ranked by how much their profile resembles the compound's."""
    _check_top_k(settings, request.top_k)
    context = _target_context(request, store, db)
    info = _compound_info(metadata_service.compound_annotations(db)).get(request.compound_id, {})

    predictions = []
    for match in context.matches[: request.top_k]:
        percentile = context.percentiles[match.perturbation_id]
        kind = (match.perturbation_type or "genetic").upper()
        predictions.append(
            Prediction(
                query_id=request.compound_id,
                candidate_id=match.perturbation_id,
                prediction_type=PredictionType.COMPOUND_GENE_MATCHING,
                score=match.score,
                rank=match.rank,
                candidate_name=match.gene_symbol,
                candidate_annotations={
                    "gene_id": match.gene_id,
                    "gene_symbol": match.gene_symbol,
                    "perturbation_type": match.perturbation_type,
                    "cosine": match.similarity,
                    "percentile": round(percentile * 100, 2),
                },
                supporting_evidence=[
                    EvidenceItem(
                        evidence_type="genetic_perturbation_match",
                        description=(
                            f"{kind} reagent for {match.gene_symbol or 'unknown gene'}: "
                            f"cosine {match.similarity:+.3f}, "
                            f"higher than {percentile:.1%} of compound-reagent pairs."
                        ),
                        value=match.similarity,
                        source_id=match.perturbation_id,
                    )
                ],
            )
        )

    response = AnalysisResponse(
        query_id=request.compound_id,
        query_name=info.get("compound_name"),
        query_annotations={"moa": info.get("moa"), "known_target": info.get("known_target")},
        prediction_type=PredictionType.COMPOUND_GENE_MATCHING,
        predictions=predictions,
        parameters={"metric": "cosine", **request.model_dump(mode="json")},
        summary=_target_summary(context),
        message=(
            f"{context.n_unannotated} genetic profile(s) without gene metadata were matched by perturbation id only."
            if context.n_unannotated
            else None
        ),
    )
    return _record_run(db, settings, response)


def prioritize_targets(
    request: TargetPrioritizationRequest, *, store: ProfileStore, db: Session, settings: Settings
) -> AnalysisResponse:
    """Target prioritization: genes ranked by phenotypic match plus targets of phenotypically similar compounds.

    The query's own annotated targets are never used in the score; they are only flagged for comparison.
    """
    _check_top_k(settings, request.top_k, request.n_neighbors)
    context = _target_context(request, store, db)
    info = _compound_info(metadata_service.compound_annotations(db))
    query_info = info.get(request.compound_id, {})
    query_targets = set(split_moa_labels(query_info.get("known_target")))

    compound_targets = {
        cid: split_moa_labels(row.get("known_target")) for cid, row in info.items() if cid != request.compound_id
    }
    neighbours = rank_similar_compounds(request.compound_id, context.compounds.features, top_k=request.n_neighbors)
    support = neighbor_target_support(
        request.compound_id, [(n.candidate_id, n.score) for n in neighbours], compound_targets
    )
    ranked = rank_candidate_targets(
        context.matches, context.percentiles, support, neighbor_weight=request.neighbor_weight
    )

    # Similarity of the query to every compound, for listing known compounds of each gene.
    others = context.compounds.features.drop(index=request.compound_id)
    similarity_to_query = dict(zip(others.index, calculate_cosine_similarity(context.query, others), strict=True))
    compounds_by_gene: dict[str, list[str]] = defaultdict(list)
    for cid, genes in compound_targets.items():
        for gene in genes:
            compounds_by_gene[gene].append(cid)

    def compound_entry(cid: str, similarity: float | None) -> dict[str, Any]:
        return {
            "compound_id": cid,
            "compound_name": info.get(cid, {}).get("compound_name"),
            "similarity": None if similarity is None else round(float(similarity), 4),
        }

    predictions = []
    for target in ranked[: request.top_k]:
        symbol = target.gene_symbol or target.gene_key
        best = target.reagents[0]
        best_percentile = target.reagent_percentiles[best.perturbation_id]
        known = sorted(compounds_by_gene.get(symbol, []), key=lambda cid: -similarity_to_query.get(cid, -np.inf))[
            :MAX_EVIDENCE_ITEMS
        ]
        evidence = [
            EvidenceItem(
                evidence_type="phenotypic_match",
                description=(
                    f"Best reagent {best.perturbation_id} ({(best.perturbation_type or 'genetic').upper()}): "
                    f"cosine {best.similarity:+.3f}, higher than {best_percentile:.1%} of compound-reagent pairs; "
                    f"{target.n_strong_reagents} of {len(target.reagents)} reagents in the top 10%."
                ),
                value=target.phenotypic_score,
                source_id=best.perturbation_id,
            )
        ]
        if target.neighbor_support > 0:
            names = ", ".join(
                info.get(cid, {}).get("compound_name") or cid for cid, _ in target.supporting_compounds[:3]
            )
            evidence.append(
                EvidenceItem(
                    evidence_type="neighbor_target",
                    description=(
                        f"Annotated target of {len(target.supporting_compounds)} of the {len(neighbours)} most similar "
                        f"compounds ({names}); {target.neighbor_support:.0%} of their similarity weight."
                    ),
                    value=target.neighbor_support,
                )
            )
        if symbol in query_targets:
            evidence.append(
                EvidenceItem(
                    evidence_type="annotation",
                    description="Listed as a known target of the query compound (not used in the score).",
                    source_id=request.compound_id,
                )
            )
        predictions.append(
            Prediction(
                query_id=request.compound_id,
                candidate_id=symbol,
                prediction_type=PredictionType.TARGET_PRIORITIZATION,
                score=target.priority,
                rank=target.rank,
                candidate_name=symbol,
                supporting_evidence=evidence,
                candidate_annotations={
                    "gene_id": best.gene_id or target.gene_key,
                    "phenotypic_score": round(target.phenotypic_score, 4),
                    "neighbor_support": round(target.neighbor_support, 4),
                    "n_reagents": len(target.reagents),
                    "n_strong_reagents": target.n_strong_reagents,
                    "reagents": [
                        {
                            "perturbation_id": m.perturbation_id,
                            "perturbation_type": m.perturbation_type,
                            "cosine": round(m.similarity, 4),
                            "percentile": round(target.reagent_percentiles[m.perturbation_id] * 100, 2),
                        }
                        for m in target.reagents
                    ],
                    "supporting_compounds": [compound_entry(cid, sim) for cid, sim in target.supporting_compounds],
                    "known_compounds": [compound_entry(cid, similarity_to_query.get(cid)) for cid in known],
                    "n_known_compounds": len(compounds_by_gene.get(symbol, [])),
                    "annotated_target_of_query": symbol in query_targets,
                },
            )
        )

    response = AnalysisResponse(
        query_id=request.compound_id,
        query_name=query_info.get("compound_name"),
        query_annotations={"moa": query_info.get("moa"), "known_target": query_info.get("known_target")},
        prediction_type=PredictionType.TARGET_PRIORITIZATION,
        predictions=predictions,
        parameters={
            "metric": "cosine",
            "score": "(phenotypic_percentile + neighbor_weight * neighbor_support) / (1 + neighbor_weight)",
            **request.model_dump(mode="json"),
        },
        summary=_target_summary(context),
        details={
            "n_genes": len(ranked),
            "neighbors": [compound_entry(n.candidate_id, n.score) for n in neighbours],
            "query_targets_in_ranking": sorted(
                ({"gene": t.gene_symbol, "rank": t.rank} for t in ranked if t.gene_symbol in query_targets),
                key=lambda item: item["rank"],
            ),
        },
        message=(
            f"{context.n_unannotated} genetic profile(s) without gene metadata were matched by perturbation id only."
            if context.n_unannotated
            else None
        ),
    )
    return _record_run(db, settings, response)


def _moa_calibration_calls(
    store: ProfileStore, consensus: ConsensusProfiles, moa_by_compound: dict[str, str], request: MoaInferenceRequest
) -> pd.DataFrame:
    """Leave-one-out calls for every annotated compound (cached per context, neighbourhood and annotations)."""
    annotation_key = hash(tuple(sorted(moa_by_compound.items())))
    return store.memo(
        (ProfileType.COMPOUND,),
        ("moa_loo_calls", request.cell_line, request.timepoint, request.n_neighbors, annotation_key),
        lambda: leave_one_out_moa_calls(
            consensus.features, moa_by_compound, n_neighbors=request.n_neighbors, top_k=MOA_CALIBRATION_TOP_K
        ),
    )


def infer_moa(
    request: MoaInferenceRequest, *, store: ProfileStore, db: Session, settings: Settings
) -> AnalysisResponse:
    """MoA candidates from annotated neighbours, with confidence calibrated by leave-one-out on annotated compounds.

    The query's own annotation is excluded from the vote and from the calibration of its confidence.
    """
    _check_top_k(settings, request.top_k, request.n_neighbors)
    consensus = store.consensus(ProfileType.COMPOUND, request.cell_line, request.timepoint)
    _query_profile(consensus, request.compound_id)
    cell_line, timepoint = _query_context(consensus, request.compound_id)

    info = _compound_info(metadata_service.compound_annotations(db))
    moa_by_compound = {cid: row["moa"] for cid, row in info.items() if row.get("moa")}
    if not moa_by_compound:
        raise DataNotLoadedError(
            ["compound_moa_annotations"],
            message="No imported compound has a MoA annotation, so mechanisms cannot be inferred.",
        )

    neighbours = rank_similar_compounds(request.compound_id, consensus.features, top_k=request.n_neighbors)
    calls = infer_mechanism(request.compound_id, neighbours, moa_by_compound, top_k=request.top_k)
    n_annotated = annotated_neighbor_count(request.compound_id, neighbours, moa_by_compound)

    loo_calls = _moa_calibration_calls(store, consensus, moa_by_compound, request)
    calibration = fit_moa_confidence(loo_calls[loo_calls["compound_id"] != request.compound_id])
    confidences = calibration.predict([c.score for c in calls]) if calibration and calls else [None] * len(calls)

    label_counts: dict[str, int] = defaultdict(int)
    for cid, value in moa_by_compound.items():
        if cid != request.compound_id:
            for label in split_moa_labels(value):
                label_counts[label] += 1
    query_labels = set(split_moa_labels(moa_by_compound.get(request.compound_id)))

    def name(cid: str) -> str | None:
        return info.get(cid, {}).get("compound_name")

    predictions = []
    for call, confidence in zip(calls, confidences, strict=True):
        supporters = call.supporting_compounds
        evidence = [
            EvidenceItem(
                evidence_type="neighbor_annotation",
                description=f"{name(cid) or cid} is annotated with this MoA (cosine {similarity:+.3f}).",
                value=similarity,
                source_id=cid,
            )
            for cid, similarity in supporters[:MAX_EVIDENCE_ITEMS]
        ]
        if confidence is not None:
            evidence.append(
                EvidenceItem(
                    evidence_type="calibrated_confidence",
                    description=(
                        f"In leave-one-out tests on {calibration.n_compounds - (1 if query_labels else 0)} annotated "
                        f"compounds, calls with this vote share were correct {confidence:.0%} of the time."
                    ),
                    value=float(confidence),
                )
            )
        predictions.append(
            Prediction(
                query_id=request.compound_id,
                candidate_id=call.moa,
                prediction_type=PredictionType.MOA_INFERENCE,
                score=call.score,
                rank=call.rank,
                candidate_name=call.moa,
                supporting_evidence=evidence,
                candidate_annotations={
                    "vote_share": round(call.score, 4),
                    "confidence": None if confidence is None else round(float(confidence), 4),
                    "n_supporting": len(supporters),
                    "n_annotated_neighbors": n_annotated,
                    "agreement": round(len(supporters) / n_annotated, 4) if n_annotated else None,
                    "mean_similarity": round(float(np.mean([s for _, s in supporters])), 4) if supporters else None,
                    "label_frequency": label_counts.get(call.moa, 0),
                    "supporting_compounds": [
                        {"compound_id": cid, "compound_name": name(cid), "similarity": round(similarity, 4)}
                        for cid, similarity in supporters
                    ],
                    "matches_query_annotation": (call.moa in query_labels) if query_labels else None,
                },
            )
        )

    messages = []
    if not calls:
        messages.append(
            f"None of the {len(neighbours)} nearest neighbours has a MoA annotation and positive similarity."
        )
    if query_labels:
        messages.append("The query's own annotation is hidden from inference and from confidence calibration.")
        if not any(label_counts.get(label) for label in query_labels):
            messages.append("No other compound shares the query's annotated MoA, so it cannot be recovered by voting.")

    response = AnalysisResponse(
        query_id=request.compound_id,
        query_name=name(request.compound_id),
        query_annotations={
            "moa": moa_by_compound.get(request.compound_id),
            "known_target": info.get(request.compound_id, {}).get("known_target"),
            "moa_shared_with_others": any(label_counts.get(label) for label in query_labels) if query_labels else None,
        },
        prediction_type=PredictionType.MOA_INFERENCE,
        predictions=predictions,
        parameters={"method": "similarity_weighted_knn_vote", **request.model_dump(mode="json")},
        summary=AnalysisSummary(
            n_candidates=len(neighbours),
            n_features=len(consensus.feature_columns),
            cell_line=cell_line,
            timepoint=timepoint,
        ),
        details={
            "neighbors": [
                {
                    "compound_id": n.candidate_id,
                    "compound_name": name(n.candidate_id),
                    "similarity": round(n.score, 4),
                    "moa": moa_by_compound.get(n.candidate_id),
                }
                for n in neighbours
            ],
            "n_annotated_neighbors": n_annotated,
            "calibration": None
            if calibration is None
            else {
                "method": "isotonic regression on leave-one-out calls (query excluded)",
                "n_compounds": calibration.n_compounds,
                "n_calls": calibration.n_calls,
                "top1_accuracy": round(calibration.top1_accuracy, 4),
                "call_precision": round(calibration.overall_precision, 4),
            },
        },
        message=" ".join(messages) or None,
    )
    return _record_run(db, settings, response)


def _compound_quality(
    store: ProfileStore, compounds: ConsensusProfiles, cell_line: str | None, timepoint: float | None
) -> pd.DataFrame:
    """Response strength, cell-density proxy and generic-response score for every compound (cached).

    Strength and density are judged against pseudo-replicate consensus profiles built from the
    matched control wells; the generic-response score against the compound population itself.
    Percentile columns are NaN when well-level controls are unavailable.
    """

    def build() -> pd.DataFrame:
        features = compounds.features
        quality = pd.DataFrame(index=features.index)
        quality["response_norm"] = np.linalg.norm(features.to_numpy(np.float64), axis=1)
        density = density_scores(features)
        quality["density_score"] = density if density is not None else np.nan
        direction = generic_response_direction(features)
        generic = generic_response_scores(features, direction)
        quality["generic_cosine"] = generic
        quality["generic_percentile"] = generic.rank(pct=True)
        reproducibility = store.metadata_values(ProfileType.COMPOUND, REPLICATE_COSINE_COLUMN)
        quality["replicate_cosine"] = reproducibility.reindex(features.index).astype(float)

        wells = store.wells(ProfileType.CONTROL)
        quality["response_percentile"] = np.nan
        quality["density_percentile"] = np.nan
        if wells is not None:
            controls = wells[wells.get(MODALITY_COLUMN, pd.Series("compound", index=wells.index)) == "compound"]
            if cell_line is not None:
                controls = controls[controls["cell_line"].astype(str).str.casefold() == cell_line.casefold()]
            if timepoint is not None:
                controls = controls[np.isclose(controls["timepoint"].astype(float), timepoint)]
            missing = [f for f in features.columns if f not in controls.columns]
            if len(controls) >= 3 and not missing:
                n_replicates = int(np.median(compounds.context["replicate_count"])) or 1
                pseudo = pseudo_replicate_consensus(controls, list(features.columns), n_replicates)
                quality["response_percentile"] = empirical_percentile(
                    quality["response_norm"].to_numpy(), strength_null(pseudo)
                )
                pseudo_density = density_scores(pd.DataFrame(pseudo, columns=features.columns))
                if density is not None and pseudo_density is not None:
                    quality["density_percentile"] = empirical_percentile(
                        quality["density_score"].to_numpy(), np.sort(pseudo_density.to_numpy())
                    )
        return quality

    return store.memo((ProfileType.COMPOUND, ProfileType.CONTROL), ("compound_quality", cell_line, timepoint), build)


def _stress_flags(row: pd.Series) -> list[str]:
    flags = []
    if row.get("density_percentile", np.nan) >= STRESS_DENSITY_PERCENTILE:
        flags.append("cell_loss")
    if row.get("generic_percentile", np.nan) >= STRESS_GENERIC_PERCENTILE:
        flags.append("generic_response")
    return flags


def _feature_entries(values: pd.Series, signature: pd.Series, compound: pd.Series | None = None) -> list[dict]:
    entries = []
    for name, value in values.items():
        info = describe_feature(str(name))
        entry = {
            "feature": str(name),
            "label": info.label,
            "value": round(float(value), 4),
            "signature": round(float(signature[name]), 3),
        }
        if compound is not None:
            entry["compound"] = round(float(compound[name]), 3)
        entries.append(entry)
    return entries


def search_rescue(
    request: RescueSearchRequest, *, store: ProfileStore, db: Session, settings: Settings
) -> AnalysisResponse:
    """Rank compounds whose profile opposes a perturbation signature, with filters and explanations.

    Weak responses (no stronger than control noise) are excluded by default; cell-loss and
    generic stress-like profiles are flagged (optionally excluded). For each candidate the score is
    decomposed into per-feature contributions that sum to it.
    """
    _check_top_k(settings, request.top_k)
    compounds = store.consensus(ProfileType.COMPOUND, request.cell_line, request.timepoint)
    compound_features = compounds.features
    perturbation: dict[str, Any] = {}

    if request.perturbation_id is not None:
        genetic = store.consensus(ProfileType.GENETIC, request.cell_line, request.perturbation_timepoint)
        _require_features_match(
            {"compound_profiles": compounds.feature_columns, "genetic_profiles": genetic.feature_columns}
        )
        if request.perturbation_id not in genetic.features.index:
            raise NotFoundError(f"No genetic profile for perturbation '{request.perturbation_id}' in this context.")
        signature = genetic.features.loc[request.perturbation_id]
        modality = store.modality(ProfileType.GENETIC, request.perturbation_id)
        if request.subtract_matched_controls:
            signature = signature - store.control_consensus(
                *_query_context(genetic, request.perturbation_id), modality=modality
            )
        query_id = request.perturbation_id
        cell, hours = _query_context(genetic, request.perturbation_id)
        perturbation = {"perturbation_type": modality, "cell_line": cell, "timepoint": hours}
        try:
            info = metadata_service.perturbation_info(db)
            if request.perturbation_id in info.index:
                row = info.loc[request.perturbation_id]
                perturbation.update(gene_id=row["gene_id"], gene_symbol=row["gene_symbol"])
                perturbation["perturbation_type"] = modality or row["perturbation_type"]
        except DataNotLoadedError:
            pass
    else:
        signature = pd.Series(request.signature, dtype=np.float64)
        _require_features_match({"compound_profiles": compounds.feature_columns, "signature": list(signature.index)})
        query_id = "custom_signature"

    if request.subtract_matched_controls:
        _require_features_match(
            {
                "compound_profiles": compounds.feature_columns,
                "control_profiles": store.feature_columns(ProfileType.CONTROL),
            }
        )
        compound_features = compound_features.copy()
        for (cell_line, timepoint), ids in compounds.context.groupby(["cell_line", "timepoint"]).groups.items():
            control = store.control_consensus(str(cell_line), float(timepoint), modality="compound")
            compound_features.loc[ids] = compound_features.loc[ids] - control[compound_features.columns]

    try:
        ranked = rank_reversal_candidates(signature, compound_features, top_k=len(compound_features))
    except ValueError as exc:
        raise InvalidQueryError(str(exc)) from exc

    quality = _compound_quality(store, compounds, request.cell_line, request.timepoint)
    strength_available = bool(quality["response_percentile"].notna().any())
    messages: list[str] = []
    excluded = {"weak_response": 0, "stress_like": 0}
    kept = []
    for candidate in ranked:
        row = quality.loc[candidate.compound_id]
        if (
            request.exclude_weak_responses
            and strength_available
            and not row["response_percentile"] >= request.min_response_percentile
        ):
            excluded["weak_response"] += 1
            continue
        if request.exclude_stress_like and _stress_flags(row):
            excluded["stress_like"] += 1
            continue
        kept.append(candidate)
    if request.exclude_weak_responses and not strength_available:
        messages.append("Well-level control profiles are unavailable, so weak responses could not be filtered.")
    if excluded["weak_response"]:
        messages.append(
            f"{excluded['weak_response']} of {len(ranked)} compounds excluded as weak responses "
            "(no stronger than control noise)."
        )
    if excluded["stress_like"]:
        messages.append(f"{excluded['stress_like']} compounds excluded as cell-loss or stress-like.")

    info_by_compound = _compound_info(metadata_service.compound_annotations(db))
    signature_density = density_scores(signature.to_frame().T)
    predictions = []
    for rank, candidate in enumerate(kept[: request.top_k], start=1):
        row = quality.loc[candidate.compound_id]
        compound_profile = compound_features.loc[candidate.compound_id]
        contributions = reversal_contributions(compound_profile, signature)
        flags = _stress_flags(row)
        name = info_by_compound.get(candidate.compound_id, {}).get("compound_name")
        evidence = [
            EvidenceItem(
                evidence_type="phenotypic_reversal",
                description=(
                    "Negative cosine between the compound profile and the perturbation signature"
                    + (" after subtracting matched controls." if request.subtract_matched_controls else ".")
                ),
                value=candidate.score,
                source_id=candidate.compound_id,
            )
        ]
        if not np.isnan(row["response_percentile"]):
            evidence.append(
                EvidenceItem(
                    evidence_type="response_strength",
                    description=(
                        f"Response stronger than {row['response_percentile']:.0%} of control pseudo-replicates."
                    ),
                    value=float(row["response_percentile"]),
                )
            )
        if "cell_loss" in flags:
            evidence.append(
                EvidenceItem(
                    evidence_type="stress_flag",
                    description="Cell-density features suggest cell loss (possible toxicity or arrested growth).",
                    value=float(row["density_percentile"]),
                )
            )
        if "generic_response" in flags:
            evidence.append(
                EvidenceItem(
                    evidence_type="stress_flag",
                    description="Profile follows the generic response shared by many compounds (often stress).",
                    value=float(row["generic_cosine"]),
                )
            )
        predictions.append(
            Prediction(
                query_id=query_id,
                candidate_id=candidate.compound_id,
                prediction_type=PredictionType.PHENOTYPIC_RESCUE,
                score=candidate.score,
                rank=rank,
                candidate_name=name,
                supporting_evidence=evidence,
                candidate_annotations={
                    "moa": info_by_compound.get(candidate.compound_id, {}).get("moa"),
                    "response_percentile": _finite_or_none(row["response_percentile"]),
                    "replicate_cosine": _finite_or_none(row["replicate_cosine"]),
                    "density_percentile": _finite_or_none(row["density_percentile"]),
                    "generic_cosine": _finite_or_none(row["generic_cosine"]),
                    "stress_flags": flags,
                    "reversing_features": _feature_entries(
                        contributions[contributions > 0].nlargest(MAX_CONTRIBUTING_FEATURES),
                        signature,
                        compound_profile,
                    ),
                    "opposing_features": _feature_entries(
                        contributions.nsmallest(3)[lambda s: s < 0], signature, compound_profile
                    ),
                    "by_measurement": {
                        k: round(v, 4) for k, v in group_contributions(contributions, "measurement").items()
                    },
                    "by_channel": {k: round(v, 4) for k, v in group_contributions(contributions, "channel").items()},
                },
            )
        )

    largest = signature.abs().nlargest(MAX_CONTRIBUTING_FEATURES).index
    contexts = compounds.context[["cell_line", "timepoint"]].drop_duplicates()
    single = len(contexts) == 1
    if signature_density is not None:
        perturbation["signature_density_score"] = round(float(signature_density.iloc[0]), 3)
    response = AnalysisResponse(
        query_id=query_id,
        query_name=perturbation.get("gene_symbol"),
        query_annotations=perturbation,
        prediction_type=PredictionType.PHENOTYPIC_RESCUE,
        predictions=predictions,
        parameters={
            "metric": "negative_cosine",
            **request.model_dump(mode="json", exclude={"signature"}),
            "signature_features": None if request.signature is None else len(request.signature),
        },
        summary=AnalysisSummary(
            n_candidates=len(kept),
            n_features=len(compounds.feature_columns),
            cell_line=str(contexts.iloc[0]["cell_line"]) if single else None,
            timepoint=_safe_value(contexts.iloc[0]["timepoint"]) if single else None,
        ),
        details={
            "signature_norm": round(float(np.linalg.norm(signature.to_numpy())), 3),
            "signature_top_features": [
                {
                    "feature": str(name),
                    "label": describe_feature(str(name)).label,
                    "value": round(float(signature[name]), 3),
                }
                for name in largest
            ],
            "excluded": excluded,
            "n_compounds": len(ranked),
            "quality_checks": {
                "response_strength_available": strength_available,
                "min_response_percentile": request.min_response_percentile,
                "cell_loss_flag_percentile": STRESS_DENSITY_PERCENTILE,
                "generic_flag_percentile": STRESS_GENERIC_PERCENTILE,
            },
        },
        message=" ".join(messages) or None,
    )
    return _record_run(db, settings, response)
