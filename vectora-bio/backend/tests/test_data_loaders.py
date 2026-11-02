import numpy as np
import pandas as pd
import pytest

from app.data.loaders import (
    AmbiguousContextError,
    available_contexts,
    build_consensus_profiles,
    check_feature_compatibility,
    feature_hash,
    filter_profiles,
    identify_feature_columns,
    read_table,
    validate_profile_table,
)
from app.errors import ProfileValidationError
from tests import synthetic


@pytest.fixture
def table():
    return synthetic.compound_profiles()


def codes(report):
    return {issue.code for issue in report.issues}


def test_read_table_formats(tmp_path, table):
    parquet, csv, tsv = tmp_path / "t.parquet", tmp_path / "t.csv.gz", tmp_path / "t.tsv"
    table.to_parquet(parquet, index=False)
    table.to_csv(csv, index=False)
    table.to_csv(tsv, index=False, sep="\t")
    for path in (parquet, csv, tsv):
        loaded = read_table(path)
        assert list(loaded.columns) == list(table.columns)
        assert len(loaded) == len(table)


def test_read_table_errors(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_table(tmp_path / "missing.parquet")
    other = tmp_path / "t.xlsx"
    other.write_text("x")
    with pytest.raises(ValueError, match="Unsupported"):
        read_table(other)


def test_feature_columns_exclude_metadata(table):
    features = identify_feature_columns(table)
    assert features == synthetic.FEATURES
    assert "Metadata_Well" not in features


def test_valid_table_passes(table):
    report = validate_profile_table(table, expected_profile_type="compound")
    assert report.is_valid, report.issues
    assert report.n_features == synthetic.N_FEATURES


def test_missing_metadata_columns(table):
    report = validate_profile_table(table.drop(columns=["cell_line", "timepoint"]))
    assert "missing_metadata_columns" in codes(report)
    with pytest.raises(ProfileValidationError) as excinfo:
        report.raise_if_invalid()
    assert excinfo.value.details["issues"][0]["examples"] == ["cell_line", "timepoint"]


def test_missing_metadata_values_and_bad_timepoints(table):
    table.loc[0, "cell_line"] = None
    table.loc[1, "timepoint"] = -4
    report = validate_profile_table(table)
    assert {"missing_metadata_values", "invalid_timepoint"} <= codes(report)


def test_duplicate_profile_ids(table):
    table.loc[1, "profile_id"] = table.loc[0, "profile_id"]
    assert "duplicate_profile_ids" in codes(validate_profile_table(table))


def test_missing_and_infinite_feature_values(table):
    table.loc[0, "feat_001"] = np.nan
    table.loc[2, "feat_003"] = np.inf
    report = validate_profile_table(table)
    assert {"missing_feature_values", "non_finite_feature_values"} <= codes(report)


def test_non_numeric_features(table):
    table["plate_note"] = "x"
    report = validate_profile_table(table)
    assert "non_numeric_features" in codes(report)


def test_zero_norm_and_constant_features(table):
    table["feat_constant"] = 1.0
    table.loc[0, synthetic.FEATURES + ["feat_constant"]] = 0.0
    report = validate_profile_table(table)
    assert "zero_norm_profiles" in codes(report)
    assert any(issue.code == "constant_features" for issue in report.warnings) is False
    table.loc[0, "feat_constant"] = 1.0
    table.loc[0, "feat_000"] = 1.0
    report = validate_profile_table(table)
    assert [issue.code for issue in report.warnings] == ["constant_features"]
    assert report.is_valid


def test_unexpected_and_unknown_profile_types(table):
    table.loc[0, "profile_type"] = "genetic"
    table.loc[1, "profile_type"] = "mystery"
    report = validate_profile_table(table, expected_profile_type="compound")
    assert {"unexpected_profile_type", "unknown_profile_type"} <= codes(report)


def test_empty_table():
    assert "empty_table" in codes(validate_profile_table(pd.DataFrame()))


def test_feature_compatibility(table):
    other = table.drop(columns=["feat_000"]).assign(extra=1.0)
    report = check_feature_compatibility({"a": table, "b": other})
    assert not report.compatible
    assert report.missing_by_dataset == {"a": ["extra"], "b": ["feat_000"]}
    assert report.n_shared_features == synthetic.N_FEATURES - 1
    shuffled = table[list(reversed(table.columns))]
    assert check_feature_compatibility({"a": table, "b": shuffled}).compatible
    assert feature_hash(["b", "a"]) == feature_hash(["a", "b"])
    with pytest.raises(ValueError):
        check_feature_compatibility({"a": table})


def test_filter_profiles(table):
    other = synthetic.compound_profiles(cell_line="CELL_B", timepoint=24)
    both = pd.concat([table, other], ignore_index=True)
    assert len(filter_profiles(both, cell_line="cell_b")) == len(other)
    assert len(filter_profiles(both, timepoint=48)) == len(table)
    assert filter_profiles(both, cell_line="CELL_A", timepoint=24).empty
    assert len(filter_profiles(both)) == len(both)
    assert {c["cell_line"] for c in available_contexts(both)} == {"CELL_A", "CELL_B"}


def test_consensus_profiles_median(table):
    consensus = build_consensus_profiles(table)
    assert len(consensus) == len(synthetic.COMPOUND_CENTERS)
    expected = table[table.perturbation_id == "CMPD_A1"][synthetic.FEATURES].median()
    np.testing.assert_allclose(consensus.features.loc["CMPD_A1"], expected)
    assert consensus.context.loc["CMPD_A1", "replicate_count"] == 3
    mean = build_consensus_profiles(table, method="mean")
    np.testing.assert_allclose(
        mean.features.loc["CMPD_A1"], table[table.perturbation_id == "CMPD_A1"][synthetic.FEATURES].mean()
    )


def test_consensus_rejects_mixed_contexts(table):
    mixed = pd.concat([table, synthetic.compound_profiles(timepoint=24)], ignore_index=True)
    with pytest.raises(AmbiguousContextError):
        build_consensus_profiles(mixed)
    assert len(build_consensus_profiles(table.iloc[0:0])) == 0
