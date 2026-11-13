import numpy as np
import pandas as pd
import pytest

from app.core.similarity import (
    calculate_cosine_similarity,
    pairwise_cosine_similarity,
    rank_similar_compounds,
    score_percentile,
    similarity_background,
)


def test_cosine_identical_opposite_orthogonal():
    query = np.array([1.0, 0.0, 0.0])
    candidates = np.array([[2.0, 0.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 3.0, 0.0]])
    np.testing.assert_allclose(calculate_cosine_similarity(query, candidates), [1.0, -1.0, 0.0])


def test_cosine_is_scale_invariant_and_bounded():
    rng = np.random.default_rng(0)
    query = rng.normal(size=20)
    candidates = rng.normal(size=(5, 20))
    scores = calculate_cosine_similarity(query, candidates)
    np.testing.assert_allclose(scores, calculate_cosine_similarity(query * 7.5, candidates * 0.01))
    assert np.all(scores <= 1.0) and np.all(scores >= -1.0)


def test_single_candidate_vector_is_one_row():
    assert calculate_cosine_similarity([1.0, 1.0], [1.0, 1.0]).shape == (1,)


def test_dimension_mismatch_raises():
    with pytest.raises(ValueError, match="2 feature"):
        calculate_cosine_similarity([1.0, 2.0, 3.0], np.ones((4, 2)))


def test_query_must_be_one_dimensional():
    with pytest.raises(ValueError, match="1-dimensional"):
        calculate_cosine_similarity(np.ones((2, 2)), np.ones((2, 2)))


@pytest.mark.parametrize("bad", [np.nan, np.inf])
def test_missing_or_infinite_values_raise(bad):
    with pytest.raises(ValueError, match="non-finite"):
        calculate_cosine_similarity([1.0, bad], np.ones((2, 2)))
    with pytest.raises(ValueError, match="non-finite"):
        calculate_cosine_similarity([1.0, 1.0], [[1.0, 1.0], [bad, 1.0]])


def test_zero_norm_vectors_raise():
    with pytest.raises(ValueError, match="query_profile has 1 zero-norm"):
        calculate_cosine_similarity([0.0, 0.0], np.ones((2, 2)))
    candidates = pd.DataFrame([[1.0, 1.0], [0.0, 0.0]], index=["ok", "empty"], columns=["a", "b"])
    with pytest.raises(ValueError, match="empty"):
        calculate_cosine_similarity(pd.Series([1.0, 1.0], index=["a", "b"]), candidates)


def test_labelled_inputs_are_aligned_by_feature_name():
    query = pd.Series([1.0, 2.0, 3.0], index=["a", "b", "c"])
    candidates = pd.DataFrame([[3.0, 1.0, 2.0]], columns=["c", "a", "b"])
    np.testing.assert_allclose(calculate_cosine_similarity(query, candidates), [1.0])


def test_labelled_feature_mismatch_raises():
    query = pd.Series([1.0, 2.0], index=["a", "b"])
    with pytest.raises(ValueError, match="Feature sets differ"):
        calculate_cosine_similarity(query, pd.DataFrame([[1.0, 2.0]], columns=["a", "z"]))


@pytest.fixture
def profiles():
    return pd.DataFrame(
        [[1.0, 0.0, 0.0], [0.9, 0.1, 0.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0], [0.7, 0.7, 0.0]],
        index=["q", "near", "orth", "opposite", "mid"],
        columns=["f1", "f2", "f3"],
    )


def test_rank_similar_compounds_orders_and_excludes_query(profiles):
    results = rank_similar_compounds("q", profiles, top_k=10)
    assert [r.candidate_id for r in results] == ["near", "mid", "orth", "opposite"]
    assert [r.rank for r in results] == [1, 2, 3, 4]
    assert results[0].score == pytest.approx(0.9 / np.sqrt(0.82))


def test_rank_similar_compounds_top_k_and_metadata(profiles):
    metadata = pd.DataFrame({"compound_id": ["near", "mid"], "compound_name": ["N", None]})
    results = rank_similar_compounds("q", profiles, metadata, top_k=2)
    assert len(results) == 2
    assert results[0].metadata == {"compound_name": "N"}
    assert results[1].metadata == {}


def test_rank_similar_compounds_ties_are_deterministic():
    profiles = pd.DataFrame([[1.0, 0.0], [0.0, 1.0], [0.0, 2.0]], index=["q", "b", "a"], columns=["x", "y"])
    assert [r.candidate_id for r in rank_similar_compounds("q", profiles)] == ["a", "b"]


def test_rank_similar_compounds_errors(profiles):
    with pytest.raises(KeyError):
        rank_similar_compounds("missing", profiles)
    with pytest.raises(ValueError, match="one row per compound"):
        rank_similar_compounds("q", pd.concat([profiles, profiles.iloc[[0]]]))
    with pytest.raises(ValueError, match="top_k"):
        rank_similar_compounds("q", profiles, top_k=0)


def test_rank_similar_compounds_single_profile_returns_empty(profiles):
    assert rank_similar_compounds("q", profiles.iloc[[0]]) == []


def test_pairwise_cosine_similarity(profiles):
    matrix = pairwise_cosine_similarity(profiles)
    assert list(matrix.index) == list(profiles.index) == list(matrix.columns)
    np.testing.assert_allclose(np.diag(matrix), 1.0)
    np.testing.assert_allclose(matrix.to_numpy(), matrix.to_numpy().T)
    np.testing.assert_allclose(
        matrix.loc["q"].drop("q").to_numpy(),
        calculate_cosine_similarity(profiles.loc["q"], profiles.drop(index="q")),
    )
    with pytest.raises(ValueError, match="zero-norm"):
        pairwise_cosine_similarity(
            pd.concat([profiles, pd.DataFrame([[0.0, 0.0, 0.0]], index=["z"], columns=profiles.columns)])
        )


def test_similarity_background_full_and_sampled(profiles):
    full = similarity_background(profiles)
    upper = pairwise_cosine_similarity(profiles).to_numpy()[np.triu_indices(len(profiles), k=1)]
    np.testing.assert_allclose(full, np.sort(upper))
    sampled = similarity_background(profiles, max_pairs=4, seed=1)
    assert sampled.size == 4 and np.all(np.diff(sampled) >= 0)
    assert set(np.round(sampled, 10)) <= set(np.round(upper, 10))  # sampled pairs are real distinct pairs
    np.testing.assert_allclose(sampled, similarity_background(profiles, max_pairs=4, seed=1))
    with pytest.raises(ValueError, match="two profiles"):
        similarity_background(profiles.iloc[[0]])


def test_score_percentile():
    background = np.array([-0.5, 0.0, 0.2, 0.4, 0.9])
    np.testing.assert_allclose(score_percentile(np.array([-1.0, 0.2, 0.95]), background), [0.0, 60.0, 100.0])
    with pytest.raises(ValueError):
        score_percentile(0.1, np.array([]))


def test_cross_similarity_background(profiles):
    from app.core.similarity import cross_similarity_background

    other = profiles.iloc[:2][list(reversed(profiles.columns))]  # same features, different order
    background = cross_similarity_background(profiles, other)
    expected = np.sort((pairwise_cosine_similarity(profiles).iloc[:, :2]).to_numpy().ravel())
    np.testing.assert_allclose(background, expected)
    assert np.all(cross_similarity_background(profiles, other, absolute=True) >= 0)
    assert cross_similarity_background(profiles, other, max_pairs=3).size == 3
    with pytest.raises(ValueError, match="different features"):
        cross_similarity_background(profiles, other.rename(columns={"f1": "zz"}))
