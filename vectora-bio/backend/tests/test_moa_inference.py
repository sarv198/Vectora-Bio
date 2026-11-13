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


import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from app.core.moa_inference import (  # noqa: E402
    annotated_neighbor_count,
    fit_moa_confidence,
    leave_one_out_moa_calls,
)


def test_annotated_neighbor_count():
    neighbours = [("q", 1.0), ("a", 0.5), ("b", -0.1), ("c", 0.3), ("d", 0.2)]
    assert annotated_neighbor_count("q", neighbours, {"q": "x", "a": "x", "b": "y", "c": "z"}) == 2


@pytest.fixture
def clustered_profiles():
    rng = np.random.default_rng(0)
    rows, labels = {}, {}
    for cluster, direction in enumerate(np.eye(4)[:3]):
        for member in range(4):
            name = f"c{cluster}_{member}"
            rows[name] = direction + rng.normal(0, 0.05, 4)
            labels[name] = f"moa_{cluster}"
    rows["unlabelled"] = rng.normal(0, 1, 4)
    return pd.DataFrame(rows).T, labels


def test_leave_one_out_calls_hide_each_compound(clustered_profiles):
    profiles, labels = clustered_profiles
    calls = leave_one_out_moa_calls(profiles, labels, n_neighbors=3, top_k=2)
    assert set(calls["compound_id"]) == set(labels)  # unannotated compounds are not evaluated
    top1 = calls[calls["rank"] == 1]
    assert top1["correct"].all()  # tight clusters: every hidden label is recovered
    # A compound's own label never votes: if no other compound carries it, it cannot be recovered.
    lonely = {**labels, "c0_0": None, "c0_2": None, "c0_3": None}
    calls = leave_one_out_moa_calls(profiles, lonely, n_neighbors=3, top_k=1)
    assert not calls.loc[calls["compound_id"] == "c0_1", "correct"].any()
    with pytest.raises(ValueError):
        leave_one_out_moa_calls(profiles, labels, n_neighbors=0)


def test_fit_moa_confidence_is_monotone():
    calls = pd.DataFrame(
        {
            "compound_id": [f"c{i}" for i in range(8)],
            "moa": ["m"] * 8,
            "rank": [1] * 8,
            "score": [0.1, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9],
            "n_supporting": [1] * 8,
            "correct": [False, False, True, False, True, True, False, True],
        }
    )
    calibration = fit_moa_confidence(calls)
    predicted = calibration.predict([0.0, 0.25, 0.5, 0.75, 1.0])
    assert np.all(np.diff(predicted) >= 0) and predicted.min() >= 0 and predicted.max() <= 1
    assert calibration.n_compounds == 8 and calibration.top1_accuracy == pytest.approx(0.5)
    assert fit_moa_confidence(calls.assign(correct=True)) is None  # one outcome: nothing to calibrate
