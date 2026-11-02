import json

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import select

from app.db.models import CompoundRecord, GeneticPerturbationRecord, ProfileDatasetRecord
from app.db.session import get_session_factory
from app.errors import FeatureMismatchError, ProfileValidationError
from app.pipeline import import_profiles as import_profiles_cli
from app.pipeline.common import load_column_map, parse_assignments
from app.pipeline.import_metadata import MetadataImportError, import_metadata
from app.pipeline.import_profiles import import_profiles, prepare_profiles
from app.schemas.common import ProfileType
from tests import synthetic


def jump_like(frame: pd.DataFrame) -> pd.DataFrame:
    """Drop canonical metadata and use JUMP-style column names instead."""
    return (
        frame.rename(columns={"perturbation_id": "Metadata_JCP2022"})
        .drop(columns=["profile_id", "profile_type", "cell_line", "timepoint"])
        .assign(Metadata_Plate="P1")
    )


def test_parse_assignments_and_column_map(tmp_path):
    assert parse_assignments(["cell_line=U2OS", "timepoint=48"]) == {"cell_line": "U2OS", "timepoint": 48.0}
    with pytest.raises(ValueError):
        parse_assignments(["oops"])
    path = tmp_path / "map.json"
    path.write_text(json.dumps({"_comment": "ignored", "A": "perturbation_id"}))
    assert load_column_map(path) == {"A": "perturbation_id"}
    path.write_text("[1, 2]")
    with pytest.raises(ValueError):
        load_column_map(path)


def test_prepare_profiles_from_jump_like_columns():
    frame = prepare_profiles(
        jump_like(synthetic.compound_profiles()),
        ProfileType.COMPOUND,
        column_map={"Metadata_JCP2022": "perturbation_id"},
        constants={"cell_line": "CELL_A", "timepoint": 48.0},
        profile_id_columns=["Metadata_Plate", "Metadata_Well", "perturbation_id"],
    )
    assert {"profile_id", "perturbation_id", "profile_type", "cell_line", "timepoint"} <= set(frame.columns)
    assert frame["profile_type"].unique().tolist() == ["compound"]
    assert frame["profile_id"].iloc[0] == "P1:W00:CMPD_A1"


def test_prepare_profiles_requires_profile_id():
    with pytest.raises(ValueError, match="profile_id"):
        prepare_profiles(jump_like(synthetic.compound_profiles()), ProfileType.COMPOUND)


def test_import_profiles_writes_and_registers(settings, tmp_path):
    source = tmp_path / "compounds.csv"
    synthetic.compound_profiles().to_csv(source, index=False)

    dry = import_profiles(source, ProfileType.COMPOUND, dry_run=True)
    assert dry.dry_run and not settings.compound_profiles_path.exists()

    summary = import_profiles(source, ProfileType.COMPOUND)
    assert summary.registered
    written = pd.read_parquet(settings.compound_profiles_path)
    assert len(written) == summary.n_profiles == 21
    assert written["feat_000"].dtype == np.float32
    assert summary.contexts == [{"cell_line": "CELL_A", "timepoint": 48.0, "n_profiles": 21, "n_perturbations": 7}]
    with get_session_factory()() as db:
        record = db.scalar(select(ProfileDatasetRecord))
        assert record.profile_type == "compound" and record.n_features == synthetic.N_FEATURES


def test_import_profiles_rejects_invalid_data(settings, tmp_path):
    frame = synthetic.compound_profiles()
    frame.loc[0, "feat_000"] = np.nan
    source = tmp_path / "bad.parquet"
    frame.to_parquet(source)
    with pytest.raises(ProfileValidationError, match="missing feature"):
        import_profiles(source, ProfileType.COMPOUND)
    summary = import_profiles(source, ProfileType.COMPOUND, missing="drop-features", register=False)
    assert summary.dropped_features == ["feat_000"]
    summary = import_profiles(source, ProfileType.COMPOUND, missing="drop-rows", register=False)
    assert summary.dropped_rows == 1


def test_import_profiles_checks_feature_compatibility(settings, tmp_path):
    compounds = tmp_path / "c.parquet"
    synthetic.compound_profiles().to_parquet(compounds)
    import_profiles(compounds, ProfileType.COMPOUND, register=False)

    genetic = tmp_path / "g.parquet"
    synthetic.genetic_profiles().assign(extra_feature=1.0).to_parquet(genetic)
    with pytest.raises(FeatureMismatchError):
        import_profiles(genetic, ProfileType.GENETIC, register=False)

    summary = import_profiles(genetic, ProfileType.GENETIC, feature_list=synthetic.FEATURES, register=False)
    assert summary.n_features == synthetic.N_FEATURES


def test_import_profiles_cli(settings, tmp_path, capsys):
    source = tmp_path / "c.parquet"
    jump_like(synthetic.compound_profiles()).to_parquet(source)
    column_map = tmp_path / "map.json"
    column_map.write_text(json.dumps({"Metadata_JCP2022": "perturbation_id"}))
    argv = ["--input", str(source), "--profile-type", "compound", "--column-map", str(column_map)]
    argv += ["--set", "cell_line=CELL_A", "--set", "timepoint=48", "--no-register"]
    assert import_profiles_cli.main(argv + ["--profile-id-columns", "Metadata_Plate", "Metadata_Well"]) == 1
    assert "duplicate" in capsys.readouterr().err.lower()
    ids = ["--profile-id-columns", "Metadata_Plate", "Metadata_Well", "perturbation_id"]
    assert import_profiles_cli.main(argv + ids) == 0
    assert json.loads(capsys.readouterr().out)["n_profiles"] == 21


def test_import_metadata_compounds_counts_replicates(settings, tmp_path):
    profiles = tmp_path / "c.parquet"
    synthetic.compound_profiles().to_parquet(profiles)
    import_profiles(profiles, ProfileType.COMPOUND, register=False)

    source = tmp_path / "compounds.csv"
    metadata = synthetic.COMPOUND_METADATA.copy()
    metadata.loc[len(metadata)] = ["CMPD_NO_PROFILE", "", None, None, "CELL_A", 48.0]
    metadata.to_csv(source, index=False)

    with pytest.raises(MetadataImportError, match="failed validation"):
        import_metadata(source, "compounds")
    summary = import_metadata(source, "compounds", name_fallback_to_id=True)
    assert summary["n_upserted"] == 8
    # Re-importing upserts instead of duplicating.
    import_metadata(source, "compounds", name_fallback_to_id=True)
    with get_session_factory()() as db:
        records = {r.compound_id: r for r in db.scalars(select(CompoundRecord))}
    assert len(records) == 8
    assert records["CMPD_A1"].replicate_count == 3
    assert records["CMPD_NO_PROFILE"].replicate_count == 0
    assert records["CMPD_NO_PROFILE"].compound_name == "CMPD_NO_PROFILE"
    assert records["CMPD_A3"].moa == "class_x|class_z"


def test_import_metadata_compounds_requires_replicates_or_profiles(settings, tmp_path):
    source = tmp_path / "compounds.csv"
    synthetic.COMPOUND_METADATA.to_csv(source, index=False)
    with pytest.raises(MetadataImportError, match="replicate_count"):
        import_metadata(source, "compounds")


def test_import_metadata_genetic(settings, tmp_path):
    source = tmp_path / "genetic.csv"
    synthetic.GENETIC_METADATA.assign(perturbation_type=lambda f: f.perturbation_type.str.upper()).to_csv(
        source, index=False
    )
    assert import_metadata(source, "genetic")["n_upserted"] == 4
    with get_session_factory()() as db:
        record = db.scalar(
            select(GeneticPerturbationRecord).where(GeneticPerturbationRecord.perturbation_id == "ORF_G2")
        )
    assert record.gene_id == "1002" and record.perturbation_type == "orf"


def test_import_metadata_missing_columns(settings, tmp_path):
    source = tmp_path / "genetic.csv"
    synthetic.GENETIC_METADATA.drop(columns=["gene_symbol"]).to_csv(source, index=False)
    with pytest.raises(MetadataImportError, match="gene_symbol"):
        import_metadata(source, "genetic")
