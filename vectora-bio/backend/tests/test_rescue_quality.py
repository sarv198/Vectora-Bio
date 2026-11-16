import numpy as np
import pandas as pd
import pytest

from app.core.features import describe_feature, group_contributions
from app.core.phenotype_quality import (
    density_scores,
    empirical_percentile,
    generic_response_direction,
    generic_response_scores,
    pseudo_replicate_consensus,
    strength_null,
)
from app.core.reversal import calculate_reversal_score, reversal_contributions


def test_describe_feature():
    info = describe_feature("Nuclei_Texture_Contrast_DNA_3_01_256")
    assert (info.compartment, info.measurement, info.channels) == ("Nucleus", "texture", ("DNA",))
    assert info.label == "Nucleus texture: Contrast [DNA]"
    assert describe_feature("Cells_Correlation_RWC_DNA_AGP").channels == ("DNA", "AGP")
    assert describe_feature("Cells_Granularity_6_HighZBF").channels == ("Brightfield",)
    assert describe_feature("feat_001").compartment == "feat"


def test_reversal_contributions_sum_to_score():
    rng = np.random.default_rng(0)
    names = [
        "Cells_AreaShape_Area",
        "Nuclei_Intensity_Mean_DNA",
        "Cells_Correlation_RWC_DNA_AGP",
        "Cells_Texture_X_Mito",
    ]
    signature = pd.Series(rng.normal(size=4), index=names)
    compound = pd.Series(rng.normal(size=4), index=list(reversed(names)))
    contributions = reversal_contributions(compound, signature)
    assert contributions.sum() == pytest.approx(calculate_reversal_score(compound, signature))
    opposite = reversal_contributions(-signature, signature)
    assert (opposite >= 0).all() and opposite.sum() == pytest.approx(1.0)
    by_channel = group_contributions(contributions, "channel")
    assert by_channel.sum() == pytest.approx(contributions.sum())  # two-channel features split evenly
    assert set(group_contributions(contributions, "measurement").index) == {
        "size/shape",
        "intensity",
        "channel correlation",
        "texture",
    }
    with pytest.raises(ValueError):
        reversal_contributions(compound.drop(names[0]), signature)
    with pytest.raises(ValueError):
        group_contributions(contributions, "plate")


def test_response_strength_against_control_noise():
    rng = np.random.default_rng(1)
    features = ["f1", "f2", "f3"]
    controls = pd.DataFrame(rng.normal(0, 1, (40, 3)), columns=features).assign(
        Metadata_Plate=np.repeat(["p1", "p2", "p3", "p4"], 10)
    )
    pseudo = pseudo_replicate_consensus(controls, features, n_replicates=4, n_samples=500)
    assert pseudo.shape == (500, 3)
    null = strength_null(pseudo)
    assert np.all(np.diff(null) >= 0)
    # Medians of 4 wells are less noisy than single wells: a 1-SD single-well profile is not unusual,
    # a large consistent effect is far outside the null.
    weak, strong = empirical_percentile([np.sqrt(3) * 0.3, 10.0], null)
    assert weak < 0.95 and strong == 1.0
    with pytest.raises(ValueError):
        pseudo_replicate_consensus(controls, features, n_replicates=0)


def test_density_and_generic_response():
    profiles = pd.DataFrame(
        {
            "Cells_Neighbors_FirstClosestDistance_5": [3.0, 0.0, -1.0],
            "Cells_Neighbors_PercentTouching_Adjacent": [-3.0, 0.0, 1.0],
            "Cells_AreaShape_Area": [1.0, 2.0, 0.5],
        },
        index=["sparse", "neutral", "dense"],
    )
    scores = density_scores(profiles)
    assert scores["sparse"] == pytest.approx(3.0) and scores["dense"] == pytest.approx(-1.0)
    assert density_scores(profiles[["Cells_AreaShape_Area"]]) is None

    shared = np.array([1.0, 1.0, 0.0])
    population = pd.DataFrame([shared + d for d in ([0, 0, 0.1], [0, 0.1, 0], [0.1, 0, 0])] + [[0.0, -1.0, 1.0]])
    direction = generic_response_direction(population)
    generic = generic_response_scores(population, direction)
    assert generic.iloc[:3].min() > generic.iloc[3]
    assert np.linalg.norm(direction) == pytest.approx(1.0)
