"""Ranking and classification metrics for model evaluation."""

from collections.abc import Hashable, Iterable, Sequence

import numpy as np
from numpy.typing import ArrayLike
from sklearn.metrics import accuracy_score, precision_recall_fscore_support


def _validate_k(k: int) -> None:
    if not isinstance(k, (int, np.integer)) or isinstance(k, bool) or k < 1:
        raise ValueError(f"k must be a positive integer, got {k!r}.")


def precision_at_k(relevant_items: Iterable[Hashable], ranked_items: Sequence[Hashable], k: int) -> float:
    """Fraction of the top ``k`` ranked items that are relevant.

    The denominator is always ``k``: a ranking shorter than ``k`` is penalized for the
    missing positions. Duplicate items in the ranking are counted once.
    """
    _validate_k(k)
    relevant = set(relevant_items)
    top = list(dict.fromkeys(ranked_items[:k]))
    return sum(item in relevant for item in top) / k


def recall_at_k(relevant_items: Iterable[Hashable], ranked_items: Sequence[Hashable], k: int) -> float:
    """Fraction of relevant items that appear in the top ``k`` ranked items.

    Raises:
        ValueError: if there are no relevant items (recall is undefined).
    """
    _validate_k(k)
    relevant = set(relevant_items)
    if not relevant:
        raise ValueError("recall_at_k is undefined when there are no relevant items.")
    top = set(ranked_items[:k])
    return len(relevant & top) / len(relevant)


def ndcg_at_k(relevance_scores: ArrayLike, k: int) -> float:
    """Normalized discounted cumulative gain of the top ``k`` positions.

    Args:
        relevance_scores: Non-negative graded relevance of each item, in ranked order.
        k: Cutoff.

    Uses linear gain, ``DCG = sum(rel_i / log2(i + 1))`` for positions i = 1..k, normalized
    by the DCG of the ideal (descending) ordering of the same scores. Returns 0.0 when
    every relevance is zero, matching ``sklearn.metrics.ndcg_score``.
    """
    _validate_k(k)
    scores = np.asarray(relevance_scores, dtype=np.float64)
    if scores.ndim != 1:
        raise ValueError(f"relevance_scores must be 1-dimensional, got shape {scores.shape}.")
    if scores.size == 0:
        raise ValueError("relevance_scores is empty.")
    if not np.all(np.isfinite(scores)):
        raise ValueError("relevance_scores contains missing or non-finite values.")
    if np.any(scores < 0):
        raise ValueError("relevance_scores must be non-negative.")

    discounts = 1.0 / np.log2(np.arange(2, scores.size + 2))
    dcg = float(np.sum(scores[:k] * discounts[:k]))
    ideal = np.sort(scores)[::-1]
    idcg = float(np.sum(ideal[:k] * discounts[:k]))
    return 0.0 if idcg == 0 else dcg / idcg


def evaluate_moa_predictions(y_true: Sequence[str], y_pred: Sequence[str]) -> dict[str, float]:
    """Single-label classification metrics for predicted mechanisms of action.

    Returns accuracy and precision, recall and F1 macro-averaged over the labels present
    in ``y_true`` (a true label that is never predicted counts as zero precision;
    predicted labels absent from ``y_true``, such as a "no prediction" placeholder,
    count as errors but are not averaged as classes), plus ``n_samples`` and
    ``n_classes`` (distinct labels in ``y_true``).
    """
    if len(y_true) != len(y_pred):
        raise ValueError(f"y_true and y_pred differ in length ({len(y_true)} vs {len(y_pred)}).")
    if len(y_true) == 0:
        raise ValueError("At least one prediction is required.")
    for name, values in (("y_true", y_true), ("y_pred", y_pred)):
        if any(value is None or (isinstance(value, float) and np.isnan(value)) for value in values):
            raise ValueError(f"{name} contains missing labels.")

    y_true_list = [str(value) for value in y_true]
    y_pred_list = [str(value) for value in y_pred]
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true_list, y_pred_list, labels=sorted(set(y_true_list)), average="macro", zero_division=0
    )
    return {
        "accuracy": float(accuracy_score(y_true_list, y_pred_list)),
        "macro_precision": float(precision),
        "macro_recall": float(recall),
        "macro_f1": float(f1),
        "n_samples": float(len(y_true_list)),
        "n_classes": float(len(set(y_true_list))),
    }
