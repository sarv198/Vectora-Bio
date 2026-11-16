"""Held-out benchmarks for similarity retrieval, MoA inference and target prioritization.

Every benchmark is cross-validated over compounds: in each fold the test compounds are removed
from the reference set entirely (their profiles and annotations), predictions for them are made
from the reference compounds only, and the hidden annotations are used only for scoring. Each
method is reported next to a baseline so the numbers can be read against chance.

Split strategies:
* ``random``: compounds assigned to folds at random.
* ``target_group``: compounds sharing a designed target (JUMP-Target pairs two compounds per
  target) always fall in the same fold, so a test compound never has its sibling in the
  reference set. This measures generalization to targets the reference set has not seen.
"""

import uuid
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.evaluation import (
    audit_folds,
    evaluate_moa_predictions,
    make_folds,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)
from app.core.moa_inference import infer_mechanism, split_moa_labels
from app.core.target_prioritization import GeneMatch, neighbor_target_support, rank_candidate_targets
from app.core.vectors import check_nonzero_norm
from app.data.profile_store import ProfileStore
from app.db.models import EvaluationResultRecord
from app.errors import DataNotLoadedError, InvalidQueryError
from app.schemas.common import DatasetSplit, ProfileType
from app.schemas.evaluation import (
    EvaluationListResponse,
    EvaluationRecord,
    EvaluationRunRequest,
    EvaluationRunResponse,
)
from app.services import metadata_service

NO_PREDICTION = "__no_prediction__"
DESIGNED_TARGET_COLUMN = "Metadata_gene"


def list_results(db: Session, *, metric_name: str | None = None, limit: int = 500) -> EvaluationListResponse:
    statement = select(EvaluationResultRecord).order_by(
        EvaluationResultRecord.created_at.desc(), EvaluationResultRecord.id
    )
    if metric_name:
        statement = statement.where(EvaluationResultRecord.metric_name == metric_name)
    with metadata_service.database_errors():
        rows = db.scalars(statement.limit(limit)).all()
    results = [EvaluationRecord.model_validate(row) for row in rows]
    message = None
    if not results:
        message = (
            "No evaluation results have been recorded. Run the benchmarks from this page or with "
            "`python -m app.pipeline.evaluate`."
        )
    return EvaluationListResponse(results=results, message=message)


@dataclass
class _Metric:
    task: str
    metric: str
    model: str
    method: str
    values: list[float] = field(default_factory=list)
    fold_means: list[float] = field(default_factory=list)


class _Collector:
    def __init__(self) -> None:
        self.metrics: dict[tuple[str, str, str], _Metric] = {}

    def add(self, task: str, metric: str, model: str, method: str, values: Sequence[float]) -> None:
        entry = self.metrics.setdefault((task, metric, model), _Metric(task, metric, model, method))
        entry.values.extend(float(v) for v in values)
        if len(values):
            entry.fold_means.append(float(np.mean(values)))


@dataclass
class _Data:
    ids: list[str]
    unit: np.ndarray
    moa: dict[str, list[str]]
    targets: dict[str, list[str]]
    designed_target: dict[str, str]
    genes: list[str] = field(default_factory=list)
    reagent_ids: list[str] = field(default_factory=list)
    reagent_info: pd.DataFrame | None = None
    reagent_unit: np.ndarray | None = None


def _unit_rows(frame: pd.DataFrame) -> np.ndarray:
    values = frame.to_numpy(np.float64)
    norms = np.linalg.norm(values, axis=1)
    check_nonzero_norm(norms, "profiles", list(frame.index))
    return values / norms[:, None]


def _load_data(store: ProfileStore, db: Session, request: EvaluationRunRequest) -> _Data:
    consensus = store.consensus(ProfileType.COMPOUND, request.cell_line, request.timepoint)
    info = metadata_service.compound_annotations(db)
    if info.empty:
        raise DataNotLoadedError([metadata_service.COMPOUND_METADATA])
    table = info.set_index("compound_id")
    ids = [str(i) for i in consensus.features.index]
    moa = {cid: labels for cid in ids if cid in table.index and (labels := split_moa_labels(table.at[cid, "moa"]))}
    targets = {
        cid: labels for cid in ids if cid in table.index and (labels := split_moa_labels(table.at[cid, "known_target"]))
    }
    designed = store.metadata_values(ProfileType.COMPOUND, DESIGNED_TARGET_COLUMN)
    designed_target = {
        cid: str(designed[cid]) if cid in designed.index else (targets[cid][0] if cid in targets else None)
        for cid in ids
    }
    data = _Data(
        ids=ids,
        unit=_unit_rows(consensus.features),
        moa=moa,
        targets=targets,
        designed_target={k: v for k, v in designed_target.items() if v},
    )

    try:
        cell_line = str(consensus.context["cell_line"].iloc[0])
        genetic = store.consensus(ProfileType.GENETIC, cell_line, None)
        reagent_info = metadata_service.perturbation_info(db)
        keep = genetic.features.index.intersection(reagent_info.index)
        if len(keep):
            features = genetic.features.loc[keep, consensus.features.columns]
            data.reagent_ids = [str(i) for i in keep]
            data.reagent_info = reagent_info.loc[keep]
            data.reagent_unit = _unit_rows(features)
            data.genes = sorted(set(data.reagent_info["gene_symbol"]))
    except (DataNotLoadedError, InvalidQueryError, KeyError):
        pass
    return data


def _random_ranking_metrics(
    n_items: int, relevant_positions: set[int], k: int, rng: np.random.Generator, n_permutations: int
) -> tuple[float, float, float, float]:
    """Mean precision@k, recall@k, nDCG@k and hit@k over random orderings of ``n_items``."""
    p = r = n = h = 0.0
    items = list(range(n_items))
    for _ in range(n_permutations):
        order = list(rng.permutation(items))
        p += precision_at_k(relevant_positions, order, k)
        r += recall_at_k(relevant_positions, order, k)
        n += ndcg_at_k([1.0 if i in relevant_positions else 0.0 for i in order], k)
        h += float(bool(relevant_positions & set(order[:k])))
    return p / n_permutations, r / n_permutations, n / n_permutations, h / n_permutations


def _similarity_task(data: _Data, folds, k: int, rng, n_permutations: int, out: _Collector) -> int:
    index = {cid: i for i, cid in enumerate(data.ids)}
    n_queries = 0
    for reference, test in folds:
        ref_idx = np.array([index[c] for c in reference])
        reference_moa = {c: data.moa[c] for c in reference if c in data.moa}
        method: dict[str, list[float]] = defaultdict(list)
        baseline: dict[str, list[float]] = defaultdict(list)
        for cid in test:
            truth = set(data.moa.get(cid, []))
            if not truth:
                continue
            similarity = data.unit[ref_idx] @ data.unit[index[cid]]
            order = np.lexsort((np.array(reference), -similarity))
            ranked = [reference[i] for i in order]
            relevant = {c for c in reference if set(reference_moa.get(c, [])) & truth}
            if not relevant:
                continue  # no reference compound shares the label: nothing retrievable
            n_queries += 1
            method["precision"].append(precision_at_k(relevant, ranked, k))
            method["recall"].append(recall_at_k(relevant, ranked, k))
            method["ndcg"].append(ndcg_at_k([1.0 if c in relevant else 0.0 for c in ranked], k))
            positions = {i for i, c in enumerate(reference) if c in relevant}
            p, r, n, _ = _random_ranking_metrics(len(reference), positions, k, rng, n_permutations)
            baseline["precision"].append(p)
            baseline["recall"].append(r)
            baseline["ndcg"].append(n)
        for metric in ("precision", "recall", "ndcg"):
            out.add("similarity", f"{metric}_at_{k}", "method", "Cosine nearest neighbours", method[metric])
            out.add("similarity", f"{metric}_at_{k}", "baseline", "Random ranking", baseline[metric])
    return n_queries


def _moa_task(data: _Data, folds, n_neighbors: int, out: _Collector) -> int:
    index = {cid: i for i, cid in enumerate(data.ids)}
    y_true: list[str] = []
    y_pred: list[str] = []
    y_base: list[str] = []
    n_queries = 0
    for reference, test in folds:
        ref_idx = np.array([index[c] for c in reference])
        reference_moa = {c: "|".join(data.moa[c]) for c in reference if c in data.moa}
        counts = Counter(label for c in reference for label in data.moa.get(c, []))
        common = [label for label, _ in counts.most_common(5)]
        method: dict[str, list[float]] = defaultdict(list)
        baseline: dict[str, list[float]] = defaultdict(list)
        for cid in test:
            truth = set(data.moa.get(cid, []))
            if not truth:
                continue
            n_queries += 1
            similarity = data.unit[ref_idx] @ data.unit[index[cid]]
            order = np.argsort(-similarity, kind="stable")[:n_neighbors]
            neighbours = [(reference[j], float(similarity[j])) for j in order]
            calls = infer_mechanism(cid, neighbours, reference_moa, top_k=5)
            labels = [c.moa for c in calls]
            recoverable = bool(truth & set(counts))
            method["top1_accuracy"].append(float(bool(labels) and labels[0] in truth))
            method["top5_accuracy"].append(float(bool(truth & set(labels))))
            baseline["top1_accuracy"].append(float(bool(common) and common[0] in truth))
            baseline["top5_accuracy"].append(float(bool(truth & set(common))))
            if recoverable:
                method["top1_accuracy_recoverable"].append(float(bool(labels) and labels[0] in truth))
                baseline["top1_accuracy_recoverable"].append(float(bool(common) and common[0] in truth))
            if len(truth) == 1:
                y_true.append(next(iter(truth)))
                y_pred.append(labels[0] if labels else NO_PREDICTION)
                y_base.append(common[0] if common else NO_PREDICTION)
        for metric in ("top1_accuracy", "top5_accuracy", "top1_accuracy_recoverable"):
            out.add("moa", metric, "method", f"Similarity-weighted vote (k={n_neighbors})", method[metric])
            out.add("moa", metric, "baseline", "Most frequent reference label", baseline[metric])
    if y_true:
        f1 = evaluate_moa_predictions(y_true, y_pred)["macro_f1"]
        f1_base = evaluate_moa_predictions(y_true, y_base)["macro_f1"]
        out.add("moa", "macro_f1", "method", f"Similarity-weighted vote (k={n_neighbors})", [f1] * len(y_true))
        out.add("moa", "macro_f1", "baseline", "Most frequent reference label", [f1_base] * len(y_true))
    return n_queries


def _target_task(
    data: _Data, folds, k: int, n_neighbors: int, neighbor_weight: float, rng, n_permutations: int, out: _Collector
) -> int:
    if data.reagent_unit is None or data.reagent_info is None or not data.genes:
        return 0
    index = {cid: i for i, cid in enumerate(data.ids)}
    info = data.reagent_info
    gene_ids = info["gene_id"].astype(str).tolist()
    symbols = info["gene_symbol"].astype(str).tolist()
    types = info["perturbation_type"].astype(str).tolist()
    gene_set = set(data.genes)
    similarity_all = data.unit @ data.reagent_unit.T  # compounds x reagents
    n_queries = 0
    for reference, test in folds:
        ref_idx = np.array([index[c] for c in reference])
        background = np.sort(np.abs(similarity_all[ref_idx]).ravel())
        reference_targets = {c: data.targets[c] for c in reference if c in data.targets}
        results: dict[str, dict[str, list[float]]] = {
            model: defaultdict(list) for model in ("combined", "phenotype_only", "baseline")
        }
        for cid in test:
            truth = set(data.targets.get(cid, [])) & gene_set
            if not truth:
                continue
            n_queries += 1
            row = similarity_all[index[cid]]
            percentiles = np.searchsorted(background, np.abs(row), side="right") / background.size
            matches = [
                GeneMatch(data.reagent_ids[j], float(row[j]), float(abs(row[j])), 1, gene_ids[j], symbols[j], types[j])
                for j in range(len(row))
            ]
            pct_map = dict(zip(data.reagent_ids, percentiles, strict=True))
            compound_similarity = data.unit[ref_idx] @ data.unit[index[cid]]
            order = np.argsort(-compound_similarity, kind="stable")[:n_neighbors]
            support = neighbor_target_support(
                cid, [(reference[j], float(compound_similarity[j])) for j in order], reference_targets
            )
            for model, weight in (("combined", neighbor_weight), ("phenotype_only", 0.0)):
                ranked = [
                    t.gene_symbol for t in rank_candidate_targets(matches, pct_map, support, neighbor_weight=weight)
                ]
                first = next((i for i, gene in enumerate(ranked, start=1) if gene in truth), None)
                results[model]["hit"].append(float(first is not None and first <= k))
                results[model]["precision"].append(precision_at_k(truth, ranked, k))
                results[model]["ndcg"].append(ndcg_at_k([1.0 if g in truth else 0.0 for g in ranked], k))
                results[model]["mrr"].append(1.0 / first if first else 0.0)
            positions = {i for i, g in enumerate(data.genes) if g in truth}
            p, _, n, h = _random_ranking_metrics(len(data.genes), positions, k, rng, n_permutations)
            results["baseline"]["hit"].append(h)
            results["baseline"]["precision"].append(p)
            results["baseline"]["ndcg"].append(n)
            results["baseline"]["mrr"].append(
                float(
                    np.mean(
                        [
                            1.0 / (1 + min(rng.permutation(len(data.genes))[list(positions)]))
                            for _ in range(n_permutations)
                        ]
                    )
                )
            )
        names = {
            "combined": f"Phenotype + similar-compound targets (w={neighbor_weight:g}, k={n_neighbors})",
            "phenotype_only": "Phenotypic match only",
            "baseline": "Random ranking",
        }
        for model, metrics in results.items():
            for metric, label in (
                ("hit", f"hit_at_{k}"),
                ("precision", f"precision_at_{k}"),
                ("ndcg", f"ndcg_at_{k}"),
                ("mrr", "mrr"),
            ):
                out.add("targets", label, model, names[model], metrics[metric])
    return n_queries


def run_benchmarks(store: ProfileStore, db: Session, request: EvaluationRunRequest) -> EvaluationRunResponse:
    """Run all held-out benchmarks for each split strategy, persist the metrics, and return them."""
    data = _load_data(store, db, request)
    if len(data.ids) < request.n_folds:
        raise InvalidQueryError(f"Need at least {request.n_folds} compounds; found {len(data.ids)}.")
    run_id = uuid.uuid4().hex[:12]
    rng = np.random.default_rng(request.seed)
    records: list[EvaluationResultRecord] = []
    audits: dict[str, Any] = {}
    notes: list[str] = []

    for strategy in request.split_strategies:
        groups = data.designed_target if strategy == "target_group" else None
        folds = make_folds(data.ids, request.n_folds, request.seed, groups)
        audit = audit_folds(folds, groups)
        # Annotations are rebuilt from the reference ids inside each task, so test labels never leak.
        audit["test_annotations_hidden"] = True
        out = _Collector()
        counts = {
            "similarity": _similarity_task(data, folds, request.k, rng, request.n_permutations, out),
            "moa": _moa_task(data, folds, request.n_neighbors, out),
            "targets": _target_task(
                data, folds, request.k, request.n_neighbors, request.neighbor_weight, rng, request.n_permutations, out
            ),
        }
        audit["queries"] = counts
        audits[strategy] = audit
        if counts["targets"] == 0:
            notes.append("Target benchmark skipped: no genetic profiles with gene metadata in this context.")
        for metric in out.metrics.values():
            if not metric.values:
                continue
            records.append(
                EvaluationResultRecord(
                    metric_name=f"{metric.task}.{metric.metric}",
                    metric_value=float(np.mean(metric.values)),
                    evaluation_method=metric.method,
                    dataset_split=DatasetSplit.TEST.value,
                    sample_count=len(metric.values),
                    parameters={
                        "run_id": run_id,
                        "task": metric.task,
                        "metric": metric.metric,
                        "model": metric.model,
                        "split_strategy": strategy,
                        "fold_std": float(np.std(metric.fold_means)) if len(metric.fold_means) > 1 else None,
                        "audit": audit,
                        **request.model_dump(mode="json", exclude={"split_strategies"}),
                    },
                )
            )

    with metadata_service.database_errors():
        db.add_all(records)
        db.commit()
        results = [EvaluationRecord.model_validate(record) for record in records]
    return EvaluationRunResponse(run_id=run_id, results=results, audit=audits, notes=notes)
