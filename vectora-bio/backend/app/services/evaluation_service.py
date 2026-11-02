"""Stored evaluation results and the leave-one-out MoA benchmark that produces them."""

from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.evaluation import evaluate_moa_predictions, ndcg_at_k, precision_at_k, recall_at_k
from app.core.moa_inference import infer_mechanism, split_moa_labels
from app.core.vectors import check_nonzero_norm
from app.data.profile_store import ProfileStore
from app.db.models import EvaluationResultRecord
from app.errors import DataNotLoadedError
from app.schemas.common import DatasetSplit, ProfileType
from app.schemas.evaluation import Evaluation, EvaluationListResponse, EvaluationRecord
from app.services import metadata_service

NO_PREDICTION = "__no_prediction__"
_QUERY_CHUNK = 256


def list_results(db: Session, *, metric_name: str | None = None, limit: int = 200) -> EvaluationListResponse:
    statement = select(EvaluationResultRecord).order_by(EvaluationResultRecord.created_at.desc())
    if metric_name:
        statement = statement.where(EvaluationResultRecord.metric_name == metric_name)
    with metadata_service.database_errors():
        rows = db.scalars(statement.limit(limit)).all()
    results = [EvaluationRecord.model_validate(row) for row in rows]
    message = None
    if not results:
        message = (
            "No evaluation results have been recorded. Import compound profiles and MoA annotations, "
            "then run `python -m app.pipeline.evaluate_moa`."
        )
    return EvaluationListResponse(results=results, message=message)


def run_moa_benchmark(
    store: ProfileStore,
    db: Session,
    *,
    cell_line: str | None,
    timepoint: float | None,
    n_neighbors: int = 20,
    k: int = 10,
) -> list[Evaluation]:
    """Leave-one-out evaluation over annotated compounds in one context.

    For every compound with a MoA annotation:
      * top-1 MoA from ``infer_mechanism`` over its ``n_neighbors`` nearest compounds
        (self excluded) is compared with the annotation (single-label compounds only);
      * annotated compounds are ranked by similarity and those sharing any MoA label
        are relevant, giving precision@k, recall@k and nDCG@k (binary relevance).
    """
    consensus = store.consensus(ProfileType.COMPOUND, cell_line, timepoint)
    annotations = metadata_service.compound_annotations(db)
    moa_by_compound = {
        str(compound_id): labels
        for compound_id, value in (
            annotations[["compound_id", "moa"]].itertuples(index=False) if not annotations.empty else []
        )
        if (labels := split_moa_labels(value))
    }
    ids = [str(index) for index in consensus.features.index]
    annotated = [i for i, compound_id in enumerate(ids) if compound_id in moa_by_compound]
    if len(annotated) < 2:
        raise DataNotLoadedError(
            ["compound_moa_annotations"],
            message=f"Need at least two annotated compounds with profiles in this context; found {len(annotated)}.",
        )

    matrix = consensus.features.to_numpy(dtype=np.float64)
    norms = np.linalg.norm(matrix, axis=1)
    check_nonzero_norm(norms, "compound profiles", ids)
    unit = matrix / norms[:, None]
    moa_strings = {compound_id: "|".join(labels) for compound_id, labels in moa_by_compound.items()}

    y_true: list[str] = []
    y_pred: list[str] = []
    precisions: list[float] = []
    recalls: list[float] = []
    ndcgs: list[float] = []
    for start in range(0, len(annotated), _QUERY_CHUNK):
        chunk = annotated[start : start + _QUERY_CHUNK]
        similarities = unit[chunk] @ unit.T
        for row, query_index in zip(similarities, chunk, strict=True):
            query_id = ids[query_index]
            row = row.copy()
            row[query_index] = -np.inf
            order = np.argsort(-row, kind="stable")
            neighbours = [(ids[j], float(row[j])) for j in order[:n_neighbors]]

            true_labels = moa_by_compound[query_id]
            if len(true_labels) == 1:
                calls = infer_mechanism(query_id, neighbours, moa_strings, top_k=1)
                y_true.append(true_labels[0])
                y_pred.append(calls[0].moa if calls else NO_PREDICTION)

            ranked = _rank_annotated(row, annotated, query_index, ids)
            relevant = {c for c in ranked if set(moa_by_compound[c]) & set(true_labels)}
            if relevant:
                precisions.append(precision_at_k(relevant, ranked, k))
                recalls.append(recall_at_k(relevant, ranked, k))
                ndcgs.append(ndcg_at_k([1.0 if c in relevant else 0.0 for c in ranked], k))

    parameters: dict[str, Any] = {
        "cell_line": cell_line,
        "timepoint": timepoint,
        "n_neighbors": n_neighbors,
        "k": k,
        "n_compounds_in_context": len(ids),
        "n_annotated": len(annotated),
    }
    results: list[Evaluation] = []
    knn_method = f"leave_one_out_knn_moa (n_neighbors={n_neighbors})"
    if y_true:
        metrics = evaluate_moa_predictions(y_true, y_pred)
        for name in ("accuracy", "macro_precision", "macro_recall", "macro_f1"):
            results.append(
                Evaluation(
                    metric_name=f"moa_top1_{name}",
                    metric_value=metrics[name],
                    evaluation_method=knn_method,
                    dataset_split=DatasetSplit.ALL,
                    sample_count=len(y_true),
                )
            )
    retrieval_method = "leave_one_out_same_moa_retrieval"
    for name, values in ((f"precision_at_{k}", precisions), (f"recall_at_{k}", recalls), (f"ndcg_at_{k}", ndcgs)):
        if values:
            results.append(
                Evaluation(
                    metric_name=f"mean_{name}",
                    metric_value=float(np.mean(values)),
                    evaluation_method=retrieval_method,
                    dataset_split=DatasetSplit.ALL,
                    sample_count=len(values),
                )
            )

    with metadata_service.database_errors():
        db.add_all(
            EvaluationResultRecord(**result.model_dump(mode="json"), parameters=parameters) for result in results
        )
        db.commit()
    return results


def _rank_annotated(row: np.ndarray, annotated: list[int], query_index: int, ids: list[str]) -> list[str]:
    """Annotated compounds other than the query, most similar first."""
    candidates = [i for i in annotated if i != query_index]
    order = sorted(candidates, key=lambda i: (-row[i], ids[i]))
    return [ids[i] for i in order]
