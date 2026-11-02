"""Analysis use cases: load the required data, call the scientific modules, build predictions."""

import logging
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.moa_inference import infer_mechanism, split_moa_labels
from app.core.reversal import rank_reversal_candidates
from app.core.similarity import rank_similar_compounds
from app.core.target_prioritization import match_compound_to_genes, prioritize_candidate_targets
from app.data.loaders import ConsensusProfiles, check_feature_compatibility
from app.data.profile_store import ProfileStore
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
    TargetPrioritizationRequest,
)
from app.services import metadata_service

logger = logging.getLogger(__name__)

MAX_EVIDENCE_ITEMS = 5


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
    _check_top_k(settings, request.top_k)
    consensus = store.consensus(ProfileType.COMPOUND, request.cell_line, request.timepoint)
    _query_profile(consensus, request.compound_id)
    cell_line, timepoint = _query_context(consensus, request.compound_id)

    annotations = metadata_service.compound_annotations(db)
    moa_by_compound = _annotation_map(annotations, "moa")
    query_moa = set(split_moa_labels(moa_by_compound.get(request.compound_id)))

    results = rank_similar_compounds(
        request.compound_id,
        consensus.features,
        annotations.set_index("compound_id") if not annotations.empty else None,
        top_k=request.top_k,
    )

    predictions = []
    for result in results:
        evidence = [
            EvidenceItem(
                evidence_type="phenotypic_similarity",
                description=f"Cosine similarity of consensus profiles ({len(consensus.feature_columns)} features).",
                value=result.score,
                source_id=result.candidate_id,
            )
        ]
        candidate_moa = set(split_moa_labels(result.metadata.get("moa")))
        if candidate_moa:
            shared = sorted(query_moa & candidate_moa)
            evidence.append(
                EvidenceItem(
                    evidence_type="annotation",
                    description=(
                        f"Annotated MoA: {' | '.join(sorted(candidate_moa))}"
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
            )
        )

    response = AnalysisResponse(
        query_id=request.compound_id,
        prediction_type=PredictionType.COMPOUND_SIMILARITY,
        predictions=predictions,
        parameters={"metric": "cosine", "consensus": settings.consensus_method, **request.model_dump(mode="json")},
        summary=AnalysisSummary(
            n_candidates=len(consensus) - 1,
            n_features=len(consensus.feature_columns),
            cell_line=cell_line,
            timepoint=timepoint,
        ),
    )
    return _record_run(db, settings, response)


def prioritize_targets(
    request: TargetPrioritizationRequest, *, store: ProfileStore, db: Session, settings: Settings
) -> AnalysisResponse:
    _check_top_k(settings, request.top_k)
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
    unannotated = genetic_features.index.difference(info.index)
    if len(unannotated) == len(genetic_features):
        raise DataNotLoadedError(
            [metadata_service.GENETIC_METADATA],
            message="None of the genetic profiles in this context have gene metadata.",
        )

    annotations = metadata_service.compound_annotations(db)
    known_targets = split_moa_labels(_annotation_map(annotations, "known_target").get(request.compound_id))
    gene_annotations = {symbol: {"annotated_target_of_query": True} for symbol in known_targets}

    matches = match_compound_to_genes(
        query,
        genetic_features,
        top_k=len(genetic_features),
        perturbation_info=info,
        use_absolute_similarity=request.use_absolute_similarity,
    )
    candidates = prioritize_candidate_targets(matches, gene_annotations)[: request.top_k]

    predictions = []
    for candidate in candidates:
        evidence = [
            EvidenceItem(
                evidence_type="genetic_perturbation_match",
                description=(
                    f"{(match.perturbation_type or 'genetic').upper()} perturbation {match.perturbation_id}"
                    f" ({match.gene_symbol or 'unknown gene'}): cosine {match.similarity:+.3f}"
                ),
                value=match.similarity,
                source_id=match.perturbation_id,
            )
            for match in candidate.supporting_matches[:MAX_EVIDENCE_ITEMS]
        ]
        if candidate.annotations.get("annotated_target_of_query"):
            evidence.append(
                EvidenceItem(
                    evidence_type="annotation",
                    description="Listed as a known target of the query compound in imported metadata.",
                    source_id=request.compound_id,
                )
            )
        predictions.append(
            Prediction(
                query_id=request.compound_id,
                candidate_id=candidate.gene_symbol or candidate.gene_key,
                prediction_type=PredictionType.TARGET_PRIORITIZATION,
                score=candidate.score,
                rank=candidate.rank,
                supporting_evidence=evidence,
            )
        )

    response = AnalysisResponse(
        query_id=request.compound_id,
        prediction_type=PredictionType.TARGET_PRIORITIZATION,
        predictions=predictions,
        parameters={"metric": "cosine", "aggregation": "max_per_gene", **request.model_dump(mode="json")},
        summary=AnalysisSummary(
            n_candidates=len(genetic_features),
            n_features=len(compounds.feature_columns),
            cell_line=cell_line,
            timepoint=timepoint,
        ),
        message=(
            f"{len(unannotated)} genetic profile(s) without gene metadata were matched by perturbation id only."
            if len(unannotated)
            else None
        ),
    )
    return _record_run(db, settings, response)


def infer_moa(
    request: MoaInferenceRequest, *, store: ProfileStore, db: Session, settings: Settings
) -> AnalysisResponse:
    _check_top_k(settings, request.top_k, request.n_neighbors)
    consensus = store.consensus(ProfileType.COMPOUND, request.cell_line, request.timepoint)
    _query_profile(consensus, request.compound_id)
    cell_line, timepoint = _query_context(consensus, request.compound_id)

    moa_by_compound = _annotation_map(metadata_service.compound_annotations(db), "moa")
    if not moa_by_compound:
        raise DataNotLoadedError(
            ["compound_moa_annotations"],
            message="No imported compound has a MoA annotation, so mechanisms cannot be inferred.",
        )

    neighbours = rank_similar_compounds(request.compound_id, consensus.features, top_k=request.n_neighbors)
    calls = infer_mechanism(request.compound_id, neighbours, moa_by_compound, top_k=request.top_k)

    predictions = [
        Prediction(
            query_id=request.compound_id,
            candidate_id=call.moa,
            prediction_type=PredictionType.MOA_INFERENCE,
            score=call.score,
            rank=call.rank,
            supporting_evidence=[
                EvidenceItem(
                    evidence_type="neighbor_annotation",
                    description=f"Neighbour {compound_id} is annotated with this MoA (cosine {similarity:+.3f}).",
                    value=similarity,
                    source_id=compound_id,
                )
                for compound_id, similarity in call.supporting_compounds[:MAX_EVIDENCE_ITEMS]
            ],
        )
        for call in calls
    ]

    messages = []
    if not calls:
        messages.append(
            f"None of the {len(neighbours)} nearest neighbours has a MoA annotation and positive similarity."
        )
    if request.compound_id in moa_by_compound:
        messages.append(
            f"Query compound is annotated as '{moa_by_compound[request.compound_id]}'; "
            "its own annotation was not used for inference."
        )

    response = AnalysisResponse(
        query_id=request.compound_id,
        prediction_type=PredictionType.MOA_INFERENCE,
        predictions=predictions,
        parameters={"method": "similarity_weighted_knn_vote", **request.model_dump(mode="json")},
        summary=AnalysisSummary(
            n_candidates=len(neighbours),
            n_features=len(consensus.feature_columns),
            cell_line=cell_line,
            timepoint=timepoint,
        ),
        message=" ".join(messages) or None,
    )
    return _record_run(db, settings, response)


def search_rescue(
    request: RescueSearchRequest, *, store: ProfileStore, db: Session, settings: Settings
) -> AnalysisResponse:
    _check_top_k(settings, request.top_k)
    compounds = store.consensus(ProfileType.COMPOUND, request.cell_line, request.timepoint)
    compound_features = compounds.features

    if request.perturbation_id is not None:
        genetic = store.consensus(ProfileType.GENETIC, request.cell_line, request.perturbation_timepoint)
        _require_features_match(
            {"compound_profiles": compounds.feature_columns, "genetic_profiles": genetic.feature_columns}
        )
        if request.perturbation_id not in genetic.features.index:
            raise NotFoundError(f"No genetic profile for perturbation '{request.perturbation_id}' in this context.")
        signature = genetic.features.loc[request.perturbation_id]
        if request.subtract_matched_controls:
            signature = signature - store.control_consensus(*_query_context(genetic, request.perturbation_id))
        query_id = request.perturbation_id
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
            control = store.control_consensus(str(cell_line), float(timepoint))
            compound_features.loc[ids] = compound_features.loc[ids] - control[compound_features.columns]

    try:
        ranked = rank_reversal_candidates(signature, compound_features, top_k=request.top_k)
    except ValueError as exc:
        raise InvalidQueryError(str(exc)) from exc

    names = _annotation_map(metadata_service.compound_annotations(db), "compound_name")
    predictions = [
        Prediction(
            query_id=query_id,
            candidate_id=candidate.compound_id,
            prediction_type=PredictionType.PHENOTYPIC_RESCUE,
            score=candidate.score,
            rank=candidate.rank,
            supporting_evidence=[
                EvidenceItem(
                    evidence_type="phenotypic_reversal",
                    description=(
                        "Negative cosine between the compound profile and the perturbation signature"
                        + (" after subtracting matched controls" if request.subtract_matched_controls else "")
                        + (f" ({names[candidate.compound_id]})" if candidate.compound_id in names else "")
                        + "."
                    ),
                    value=candidate.score,
                    source_id=candidate.compound_id,
                )
            ],
        )
        for candidate in ranked
    ]

    contexts = compounds.context[["cell_line", "timepoint"]].drop_duplicates()
    single = len(contexts) == 1
    response = AnalysisResponse(
        query_id=query_id,
        prediction_type=PredictionType.PHENOTYPIC_RESCUE,
        predictions=predictions,
        parameters={
            "metric": "negative_cosine",
            **request.model_dump(mode="json", exclude={"signature"}),
            "signature_features": None if request.signature is None else len(request.signature),
        },
        summary=AnalysisSummary(
            n_candidates=len(compound_features),
            n_features=len(compounds.feature_columns),
            cell_line=str(contexts.iloc[0]["cell_line"]) if single else None,
            timepoint=_safe_value(contexts.iloc[0]["timepoint"]) if single else None,
        ),
    )
    return _record_run(db, settings, response)
