import numpy as np
import pytest
from sklearn.metrics import ndcg_score

from app.core.evaluation import evaluate_moa_predictions, ndcg_at_k, precision_at_k, recall_at_k


def test_precision_at_k():
    ranked = ["a", "b", "c", "d"]
    assert precision_at_k({"a", "c"}, ranked, 2) == pytest.approx(0.5)
    assert precision_at_k({"a", "c"}, ranked, 3) == pytest.approx(2 / 3)
    # Short rankings are penalized for missing positions.
    assert precision_at_k({"a"}, ["a"], 4) == pytest.approx(0.25)
    assert precision_at_k({"a"}, ["a", "a"], 2) == pytest.approx(0.5)


def test_recall_at_k():
    assert recall_at_k({"a", "c", "z"}, ["a", "b", "c"], 2) == pytest.approx(1 / 3)
    assert recall_at_k({"a", "c"}, ["a", "b", "c"], 3) == pytest.approx(1.0)
    with pytest.raises(ValueError, match="no relevant"):
        recall_at_k(set(), ["a"], 1)


@pytest.mark.parametrize("k", [0, -1, 1.5, True])
def test_invalid_k(k):
    with pytest.raises(ValueError, match="k must be"):
        precision_at_k({"a"}, ["a"], k)


def test_ndcg_matches_sklearn():
    relevance = np.array([3.0, 2.0, 0.0, 1.0, 2.0])
    for k in (1, 3, 5):
        expected = ndcg_score([relevance], [np.arange(len(relevance), 0, -1)], k=k)
        assert ndcg_at_k(relevance, k) == pytest.approx(expected)


def test_ndcg_edge_cases():
    assert ndcg_at_k([3, 2, 1], 3) == pytest.approx(1.0)
    assert ndcg_at_k([0, 0, 0], 2) == 0.0
    assert ndcg_at_k([1, 0], 10) == pytest.approx(1.0)
    with pytest.raises(ValueError, match="non-negative"):
        ndcg_at_k([1, -1], 2)
    with pytest.raises(ValueError, match="empty"):
        ndcg_at_k([], 2)
    with pytest.raises(ValueError, match="non-finite"):
        ndcg_at_k([1, np.nan], 2)


def test_evaluate_moa_predictions():
    metrics = evaluate_moa_predictions(["x", "x", "y", "y"], ["x", "y", "y", "__none__"])
    assert metrics["accuracy"] == pytest.approx(0.5)
    # Per class: x -> P=1, R=0.5; y -> P=0.5, R=0.5. Placeholder labels are not averaged.
    assert metrics["macro_precision"] == pytest.approx(0.75)
    assert metrics["macro_recall"] == pytest.approx(0.5)
    assert metrics["n_samples"] == 4 and metrics["n_classes"] == 2


def test_evaluate_moa_predictions_validation():
    with pytest.raises(ValueError, match="differ in length"):
        evaluate_moa_predictions(["x"], ["x", "y"])
    with pytest.raises(ValueError, match="At least one"):
        evaluate_moa_predictions([], [])
    with pytest.raises(ValueError, match="missing labels"):
        evaluate_moa_predictions(["x", None], ["x", "y"])
