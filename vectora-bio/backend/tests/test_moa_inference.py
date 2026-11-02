import pytest

from app.core.moa_inference import infer_mechanism, split_moa_labels
from app.core.similarity import SimilarCompound


def test_split_moa_labels():
    assert split_moa_labels("a | b|a|") == ["a", "b"]
    assert split_moa_labels(["x", " y "]) == ["x", "y"]
    assert split_moa_labels(None) == []
    assert split_moa_labels(float("nan")) == []


def test_weighted_vote_scores_are_normalized():
    neighbours = [("n1", 0.8), ("n2", 0.6), ("n3", 0.4)]
    annotations = {"n1": "x", "n2": "x|y", "n3": "y"}
    calls = infer_mechanism("q", neighbours, annotations, top_k=5)
    total = 0.8 + 0.6 + 0.4
    assert [c.moa for c in calls] == ["x", "y"]
    assert calls[0].score == pytest.approx(1.4 / total)
    assert calls[1].score == pytest.approx(1.0 / total)
    assert calls[0].supporting_compounds == (("n1", 0.8), ("n2", 0.6))
    assert [c.rank for c in calls] == [1, 2]


def test_ignores_self_nonpositive_and_unannotated_neighbours():
    neighbours = [
        SimilarCompound("q", 1.0, 1),
        SimilarCompound("neg", -0.9, 2),
        SimilarCompound("zero", 0.0, 3),
        SimilarCompound("unannotated", 0.7, 4),
        SimilarCompound("n1", 0.5, 5),
    ]
    annotations = {"q": "self_label", "neg": "neg_label", "zero": "zero_label", "n1": "x"}
    calls = infer_mechanism("q", neighbours, annotations)
    assert [c.moa for c in calls] == ["x"]
    assert calls[0].score == pytest.approx(1.0)


def test_no_qualifying_neighbours_returns_empty():
    assert infer_mechanism("q", [("a", 0.9)], {}) == []
    assert infer_mechanism("q", [], {"a": "x"}) == []


def test_top_k_limits_and_validates():
    neighbours = [("a", 0.9), ("b", 0.8), ("c", 0.7)]
    annotations = {"a": "x", "b": "y", "c": "z"}
    assert len(infer_mechanism("q", neighbours, annotations, top_k=2)) == 2
    with pytest.raises(ValueError):
        infer_mechanism("q", neighbours, annotations, top_k=0)
