import numpy as np
import pandas as pd
import pytest

from app.core.reversal import calculate_reversal_score, rank_reversal_candidates


def test_reversal_score_extremes():
    signature = np.array([1.0, -2.0, 0.5])
    assert calculate_reversal_score(-signature, signature) == pytest.approx(1.0)
    assert calculate_reversal_score(signature * 3, signature) == pytest.approx(-1.0)
    assert calculate_reversal_score([2.0, 1.0, 0.0], signature) == pytest.approx(0.0)


def test_reversal_score_aligns_labelled_series():
    signature = pd.Series([1.0, 0.0], index=["a", "b"])
    compound = pd.Series([0.0, -1.0], index=["b", "a"])
    assert calculate_reversal_score(compound, signature) == pytest.approx(1.0)


def test_rank_reversal_candidates_orders_by_score():
    signature = pd.Series([1.0, 0.0, 0.0], index=["a", "b", "c"])
    compounds = pd.DataFrame(
        [[-1.0, 0.0, 0.0], [1.0, 0.0, 0.0], [-0.5, 0.5, 0.0], [0.0, 1.0, 0.0]],
        index=["reverser", "mimic", "partial", "orthogonal"],
        columns=["a", "b", "c"],
    )
    ranked = rank_reversal_candidates(signature, compounds, top_k=3)
    assert [c.compound_id for c in ranked] == ["reverser", "partial", "orthogonal"]
    assert ranked[0].score == pytest.approx(1.0)
    assert [c.rank for c in ranked] == [1, 2, 3]


def test_reversal_validation():
    with pytest.raises(ValueError, match="zero-norm"):
        calculate_reversal_score([1.0, 1.0], [0.0, 0.0])
    with pytest.raises(ValueError, match="feature"):
        calculate_reversal_score([1.0, 1.0, 1.0], [1.0, 1.0])
    with pytest.raises(ValueError, match="non-finite"):
        calculate_reversal_score([np.nan, 1.0], [1.0, 1.0])
    assert rank_reversal_candidates([1.0], pd.DataFrame(columns=["a"], dtype=float)) == []
