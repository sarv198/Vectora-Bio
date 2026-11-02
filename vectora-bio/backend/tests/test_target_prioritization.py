import pandas as pd
import pytest

from app.core.target_prioritization import GeneMatch, match_compound_to_genes, prioritize_candidate_targets


@pytest.fixture
def genetic():
    return pd.DataFrame(
        [[1.0, 0.1, 0.0], [0.8, 0.0, 0.3], [-1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        index=["g1_a", "g1_b", "g2_orf", "g3"],
        columns=["f1", "f2", "f3"],
    )


@pytest.fixture
def info():
    return pd.DataFrame(
        {
            "perturbation_id": ["g1_a", "g1_b", "g2_orf", "g3"],
            "gene_id": ["1", "1", "2", "3"],
            "gene_symbol": ["G1", "G1", "G2", "G3"],
            "perturbation_type": ["crispr", "crispr", "orf", "crispr"],
        }
    )


QUERY = pd.Series([1.0, 0.0, 0.0], index=["f1", "f2", "f3"])


def test_absolute_similarity_surfaces_anticorrelated_perturbations(genetic, info):
    matches = match_compound_to_genes(QUERY, genetic, top_k=4, perturbation_info=info)
    assert matches[0].perturbation_id == "g2_orf"
    assert matches[0].similarity == pytest.approx(-1.0)
    assert matches[0].score == pytest.approx(1.0)
    assert matches[0].gene_symbol == "G2" and matches[0].perturbation_type == "orf"


def test_signed_similarity_ranks_anticorrelated_last(genetic):
    matches = match_compound_to_genes(QUERY, genetic, top_k=4, use_absolute_similarity=False)
    assert matches[-1].perturbation_id == "g2_orf"
    assert matches[0].perturbation_id == "g1_a"
    assert matches[0].gene_id is None


def test_match_top_k_and_empty(genetic):
    assert len(match_compound_to_genes(QUERY, genetic, top_k=2)) == 2
    assert match_compound_to_genes(QUERY, genetic.iloc[0:0]) == []


def test_prioritize_groups_by_gene_and_keeps_max(genetic, info):
    matches = match_compound_to_genes(QUERY, genetic, top_k=4, perturbation_info=info, use_absolute_similarity=False)
    candidates = prioritize_candidate_targets(matches, {"G1": {"annotated_target_of_query": True}})
    assert [c.gene_key for c in candidates] == ["1", "3", "2"]
    top = candidates[0]
    assert top.gene_symbol == "G1"
    assert top.n_supporting_perturbations == 2
    assert top.score == pytest.approx(max(m.score for m in matches if m.gene_id == "1"))
    assert top.annotations == {"annotated_target_of_query": True}
    assert [c.rank for c in candidates] == [1, 2, 3]


def test_annotations_do_not_change_order():
    matches = [
        GeneMatch("p1", 0.9, 0.9, 1, gene_id="a"),
        GeneMatch("p2", 0.5, 0.5, 2, gene_id="b"),
    ]
    candidates = prioritize_candidate_targets(matches, {"b": {"flag": True}})
    assert [c.gene_key for c in candidates] == ["a", "b"]
    assert candidates[1].annotations == {"flag": True}


def test_prioritize_falls_back_to_perturbation_id():
    candidates = prioritize_candidate_targets([GeneMatch("p1", 0.4, 0.4, 1)])
    assert candidates[0].gene_key == "p1" and candidates[0].gene_symbol is None
