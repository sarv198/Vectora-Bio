import math

import pytest
from pydantic import ValidationError

from app.schemas.common import DatasetSplit, PredictionType, ProfileType
from app.schemas.compound import Compound
from app.schemas.evaluation import Evaluation
from app.schemas.genetic import GeneticPerturbation
from app.schemas.prediction import Prediction, RescueSearchRequest
from app.schemas.profile import Profile

COMPOUND = {
    "compound_id": "CMPD_1",
    "compound_name": "compound 1",
    "cell_line": "CELL_A",
    "timepoint": 48,
    "replicate_count": 4,
}


def test_compound_valid_and_blank_annotations_become_none():
    compound = Compound(**COMPOUND, moa="  ", known_target="")
    assert compound.moa is None and compound.known_target is None


@pytest.mark.parametrize(
    "override", [{"timepoint": 0}, {"replicate_count": -1}, {"compound_id": ""}, {"cell_line": "   "}]
)
def test_compound_invalid(override):
    with pytest.raises(ValidationError):
        Compound(**{**COMPOUND, **override})


def test_genetic_perturbation_type_is_validated():
    base = {"perturbation_id": "p", "gene_id": "1", "gene_symbol": "G", "cell_line": "C", "timepoint": 96}
    assert GeneticPerturbation(**base, perturbation_type="crispr").perturbation_type == "crispr"
    with pytest.raises(ValidationError):
        GeneticPerturbation(**base, perturbation_type="shrna")


def test_profile_rejects_non_finite_and_empty_features():
    base = {
        "profile_id": "p1",
        "perturbation_id": "x",
        "profile_type": ProfileType.CONTROL,
        "cell_line": "C",
        "timepoint": 48,
    }
    assert Profile(**base, feature_values={"a": 1.0}).profile_type == "control"
    with pytest.raises(ValidationError, match="not finite"):
        Profile(**base, feature_values={"a": math.nan})
    with pytest.raises(ValidationError):
        Profile(**base, feature_values={})


def test_prediction_validation():
    base = {"query_id": "q", "candidate_id": "c", "prediction_type": PredictionType.MOA_INFERENCE}
    assert Prediction(**base, score=0.5, rank=1).supporting_evidence == []
    with pytest.raises(ValidationError):
        Prediction(**base, score=0.5, rank=0)
    with pytest.raises(ValidationError, match="finite"):
        Prediction(**base, score=math.inf, rank=1)


def test_evaluation_validation():
    base = {"metric_name": "m", "evaluation_method": "e", "dataset_split": DatasetSplit.TEST, "sample_count": 3}
    assert Evaluation(**base, metric_value=0.2).dataset_split == "test"
    with pytest.raises(ValidationError):
        Evaluation(**base, metric_value=math.nan)
    with pytest.raises(ValidationError):
        Evaluation(**{**base, "dataset_split": "holdout"}, metric_value=0.2)


def test_rescue_request_requires_exactly_one_signature_source():
    assert RescueSearchRequest(perturbation_id="p").signature is None
    assert RescueSearchRequest(signature={"a": 1.0}).perturbation_id is None
    with pytest.raises(ValidationError, match="exactly one"):
        RescueSearchRequest()
    with pytest.raises(ValidationError, match="exactly one"):
        RescueSearchRequest(perturbation_id="p", signature={"a": 1.0})
