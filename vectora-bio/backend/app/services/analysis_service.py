"""Orchestrate preprocessing, data lookup, and analytical routines."""

from collections.abc import Mapping

from app.core.evaluation import run_evaluation
from app.core.moa_inference import infer_moa
from app.core.preprocessing import standardize_signature
from app.core.reversal import score_reversal
from app.core.similarity import rank_similar
from app.core.target_prioritization import prioritize_targets
from app.schemas.evaluation import EvaluationReport, MetricResult
from app.schemas.prediction import MechanismPrediction, ReversalScore, SimilarityHit, TargetScore
from app.services.data_loader import load_signature


def _prepare(values: Mapping[str, float]) -> dict[str, float]:
    signature = standardize_signature(values)
    if not signature:
        raise ValueError("Signature is empty after preprocessing.")
    return signature


def find_similar(
    values: Mapping[str, float],
    library: Mapping[str, Mapping[str, float]],
    limit: int = 20,
) -> list[SimilarityHit]:
    signature = _prepare(values)
    ranked = rank_similar(signature, library, limit=limit)
    return [SimilarityHit(compound_id=compound_id, score=score, method="similarity") for compound_id, score in ranked]


def rank_targets(values: Mapping[str, float], limit: int = 50) -> list[TargetScore]:
    signature = _prepare(values)
    ranked = prioritize_targets(signature, limit=limit)
    return [TargetScore(symbol=symbol, score=score) for symbol, score in ranked]


def infer_mechanisms(values: Mapping[str, float], limit: int = 10) -> list[MechanismPrediction]:
    signature = _prepare(values)
    ranked = infer_moa(signature, limit=limit)
    return [MechanismPrediction(label=label, score=score) for label, score in ranked]


def score_rescue(
    values: Mapping[str, float],
    reference_id: str,
    query_id: str | None = None,
) -> ReversalScore:
    query = _prepare(values)
    reference = standardize_signature(load_signature(reference_id))
    if not reference:
        raise ValueError(f"Reference signature '{reference_id}' is empty after preprocessing.")
    score = score_reversal(query, reference)
    return ReversalScore(
        query_id=query_id or "query",
        reference_id=reference_id,
        score=score,
        method="reversal",
    )


def evaluate(task: str) -> EvaluationReport:
    metrics = run_evaluation(task)
    return EvaluationReport(
        task=task,
        metrics=[MetricResult(name=name, value=value) for name, value in metrics],
    )
