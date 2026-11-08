"""Phase 1 preprocessing on a synthetic raw layout that mimics the JUMP pilot files.

Plate contents, ids and gene symbols are placeholders, not real measurements.
"""

import json

import numpy as np
import pandas as pd
import pytest

from app.data.profile_store import get_profile_store
from app.pipeline import build_profiles as build_cli
from app.pipeline import download_cpjump1
from app.preprocessing import sources
from app.preprocessing.aggregate import aggregate_replicates, mean_pairwise_cosine
from app.preprocessing.build import build_dataset
from app.preprocessing.config import BuildConfig, FeatureSelectionConfig, load_config
from app.preprocessing.feature_selection import (
    blocklisted,
    correlated_features,
    low_variance_features,
    missing_features,
    select_features,
)
from app.preprocessing.normalize import normalize_by_plate, normalize_plate

BATCH = "BATCH_1"
N_FEATURES = 8
FEATURES = [f"Cells_Feature_{i}" for i in range(N_FEATURES)] + ["Nuclei_Location_Center_X"]

# plate -> (modality, cell type, hours, anomaly)
PLATES = {
    "PC1": ("compound", "CELL_A", 48, "none"),
    "PC2": ("compound", "CELL_A", 48, "none"),
    "PC3": ("compound", "CELL_A", 24, "none"),
    "PG1": ("crispr", "CELL_A", 144, "none"),
    "PO1": ("orf", "CELL_A", 48, "dye"),
    "PX1": ("compound", "CELL_B", 48, "none"),
}
COMPOUNDS = {"CMP-1": ("drug one", "GENE1"), "CMP-2": ("drug two", "GENE2"), "CMP-3": ("drug three", "GENE1")}
CRISPR = {"SG-1": "GENE1", "SG-2": "GENE1", "SG-3": "GENE2"}
ORFS = {"ORF-1": "GENE1", "ORF-2": "GENE3"}


def _direction(index: int) -> np.ndarray:
    vector = np.zeros(N_FEATURES)
    vector[index % N_FEATURES] = 3.0
    return vector


def _plate(modality: str, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    baseline = rng.normal(100, 5, N_FEATURES)  # plate-specific raw offset that normalization must remove
    perturbations: dict[str, tuple[str | None, str | None, np.ndarray]] = {}
    if modality == "compound":
        for i, (cid, (name, gene)) in enumerate(COMPOUNDS.items()):
            perturbations[cid] = (name, gene, _direction(i))
        controls = [("DMSO", None)] * 8
    elif modality == "crispr":
        for i, (sid, gene) in enumerate(CRISPR.items()):
            perturbations[sid] = (None, gene, _direction(i))
        controls = [(f"SG-NEG-{i % 2}", None) for i in range(8)]
    else:
        for i, (oid, gene) in enumerate(ORFS.items()):
            perturbations[oid] = (None, gene, -_direction(i))
        controls = [(f"ORF-NEG-{i % 2}", None) for i in range(8)]

    well = 0
    for pid, (name, gene, effect) in perturbations.items():
        for _ in range(2):
            rows.append((pid, name, gene, "trt", None, baseline + effect * 5 + rng.normal(0, 1, N_FEATURES)))
            well += 1
    for pid, _ in controls:
        broad = None if pid == "DMSO" else pid
        name = "DMSO" if pid == "DMSO" else None
        rows.append((broad, name, None, "control", "negcon", baseline + rng.normal(0, 1, N_FEATURES)))
    rows.append((None, None, None, None, None, baseline))  # empty well

    frame = pd.DataFrame(
        {
            "Metadata_broad_sample": [r[0] for r in rows],
            "Metadata_pert_iname": [r[1] for r in rows],
            "Metadata_gene": [r[2] for r in rows],
            "Metadata_pert_type": [r[3] for r in rows],
            "Metadata_control_type": [r[4] for r in rows],
            "Metadata_Well": [f"W{i:02d}" for i in range(len(rows))],
        }
    )
    values = np.vstack([r[5] for r in rows])
    for i, feature in enumerate(FEATURES[:N_FEATURES]):
        frame[feature] = values[:, i]
    frame["Nuclei_Location_Center_X"] = rng.uniform(0, 1000, len(rows))
    if modality == "compound":
        frame["Metadata_InChIKey"] = frame["Metadata_broad_sample"].map(lambda b: f"KEY-{b}" if b else None)
    return frame


@pytest.fixture
def raw_dir(tmp_path):
    root = tmp_path / "raw"
    metadata = root / "metadata"
    metadata.mkdir(parents=True)
    rng = np.random.default_rng(0)
    rows = []
    for plate, (modality, cell, hours, anomaly) in PLATES.items():
        rows.append([BATCH, f"{modality}_map", plate, modality, cell, hours, 100, "absent", "Parental", anomaly])
        path = root / "profiles" / BATCH / plate / f"{plate}_augmented.csv.gz"
        path.parent.mkdir(parents=True)
        _plate(modality, rng).to_csv(path, index=False)
    pd.DataFrame(
        rows,
        columns=[
            "Batch",
            "Plate_Map_Name",
            "Assay_Plate_Barcode",
            "Perturbation",
            "Cell_type",
            "Time",
            "Density",
            "Antibiotics",
            "Cell_line",
            "Anomaly",
        ],
    ).to_csv(metadata / "experiment-metadata.tsv", sep="\t", index=False)
    pd.DataFrame(
        {
            "broad_sample": list(COMPOUNDS),
            "pert_iname": [v[0] for v in COMPOUNDS.values()],
            "target": [v[1] for v in COMPOUNDS.values()],
            "target_list": ["GENE1|GENE9", "GENE2", "GENE1"],
        }
    ).to_csv(metadata / "JUMP-Target-1_compound_metadata_targets.tsv", sep="\t", index=False)
    return root


def make_config(raw_dir, **overrides) -> BuildConfig:
    payload = {
        "source": {"name": "synthetic", "batch": BATCH, "raw_dir": str(raw_dir)},
        "selection": {"cell_type": "CELL_A", "timepoints": {"compound": 48, "crispr": 144, "orf": 48}},
        "feature_selection": {"correlation_threshold": None},
    }
    for section, values in overrides.items():
        payload.setdefault(section, {}).update(values)
    return BuildConfig.model_validate(payload)


# --- Units ---------------------------------------------------------------------------


def test_normalize_plate_mad_and_standardize():
    features = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0, 100.0], "b": [5.0, 5.0, 5.0, 5.0, 9.0]})
    reference = np.array([True, True, True, True, False])
    scaled, degenerate = normalize_plate(features, reference)
    assert degenerate == 1  # 'b' has zero spread in the reference wells
    assert scaled["b"].isna().all()
    np.testing.assert_allclose(np.median(scaled["a"][:4]), 0.0)
    scaled, _ = normalize_plate(features, reference, method="standardize")
    np.testing.assert_allclose(scaled["a"][:4].mean(), 0.0, atol=1e-12)
    with pytest.raises(ValueError, match="reference wells"):
        normalize_plate(features, np.array([True, True, False, False, False]))


def test_normalize_by_plate_removes_plate_offsets():
    wells = pd.DataFrame(
        {"Metadata_Plate": ["p1"] * 4 + ["p2"] * 4, "f": [1.0, 2.0, 3.0, 10.0, 101.0, 102.0, 103.0, 110.0]}
    )
    reference = pd.Series([True, True, True, False] * 2)
    normalized, report = normalize_by_plate(wells, ["f"], reference)
    np.testing.assert_allclose(normalized["f"][:4].to_numpy(), normalized["f"][4:].to_numpy())
    assert [r.n_reference_wells for r in report] == [3, 3]


def test_feature_selection_steps():
    rng = np.random.default_rng(0)
    base = rng.normal(size=300)
    frame = pd.DataFrame(
        {
            "Cells_A": base,
            "Cells_A_copy": base * 2 + 0.001 * rng.normal(size=300),
            "Cells_B": rng.normal(size=300),
            "Cells_const": np.ones(300),
            "Cells_rare": [0.0] * 299 + [1.0],
            "Cells_missing": [np.nan] + list(rng.normal(size=299)),
            "Nuclei_Location_X": rng.normal(size=300),
        }
    )
    assert blocklisted(list(frame.columns), [r"_Location_"]) == ["Nuclei_Location_X"]
    assert missing_features(frame) == ["Cells_missing"]
    assert set(low_variance_features(frame.drop(columns="Cells_missing"), 0.05, 0.01)) == {"Cells_const", "Cells_rare"}
    assert len(correlated_features(frame[["Cells_A", "Cells_A_copy", "Cells_B"]], 0.9)) == 1

    report = select_features(frame, FeatureSelectionConfig(blocklist_patterns=[r"_Location_"]))
    assert set(report.selected) in ({"Cells_A", "Cells_B"}, {"Cells_A_copy", "Cells_B"})
    assert report.summary()["removed_counts"] == {"blocklist": 1, "missing": 1, "low_variance": 2, "correlation": 1}
    with pytest.raises(ValueError, match="every feature"):
        select_features(frame[["Cells_const"]], FeatureSelectionConfig())


def test_aggregate_replicates_and_reproducibility():
    assert mean_pairwise_cosine(np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]])) == pytest.approx(1 / 3)
    assert np.isnan(mean_pairwise_cosine(np.array([[1.0, 2.0]])))
    wells = pd.DataFrame(
        {
            "Metadata_modality": ["compound"] * 3,
            "perturbation_id": ["a", "a", "b"],
            "cell_line": ["C"] * 3,
            "timepoint": [48.0] * 3,
            "Metadata_Plate": ["p1", "p2", "p1"],
            "Metadata_Well": ["A1", "A1", "A2"],
            "f1": [1.0, 3.0, 5.0],
            "f2": [0.0, 0.0, 1.0],
        }
    )
    consensus = aggregate_replicates(wells, ["f1", "f2"])
    row = consensus.set_index("perturbation_id").loc["a"]
    assert row["f1"] == 2.0 and row["Metadata_n_replicates"] == 2 and row["Metadata_n_plates"] == 2
    assert row["Metadata_replicate_cosine"] == pytest.approx(1.0)
    assert "Metadata_Well" not in consensus.columns
    assert list(aggregate_replicates(wells, ["f1"], min_replicates=2)["perturbation_id"]) == ["a"]


def test_select_plates(raw_dir):
    config = make_config(raw_dir)
    plates = sources.select_plates(sources.read_experiment_metadata(config), config)
    assert set(plates["plate"]) == {"PC1", "PC2", "PG1", "PO1"}
    excluded = make_config(raw_dir, selection={"exclude_anomalies": ["dye"]})
    with pytest.raises(sources.SourceError, match="orf"):
        sources.select_plates(sources.read_experiment_metadata(excluded), excluded)
    explicit = make_config(raw_dir, selection={"plates": ["PC1", "PG1"], "timepoints": {"compound": 48, "crispr": 144}})
    assert list(sources.select_plates(sources.read_experiment_metadata(explicit), explicit)["plate"]) == ["PC1", "PG1"]


def test_missing_raw_files_are_reported(raw_dir):
    (raw_dir / "profiles" / BATCH / "PG1" / "PG1_augmented.csv.gz").unlink()
    config = make_config(raw_dir)
    with pytest.raises(sources.SourceError, match="download_cpjump1"):
        build_dataset(config, dry_run=True)


def test_download_targets_only_selected_plates(raw_dir):
    config = make_config(raw_dir)
    urls = [url for url, _ in download_cpjump1.plate_downloads(config)]
    assert len(urls) == 4
    assert all(url.startswith(sources.PROFILES_BASE_URL) and url.endswith("_augmented.csv.gz") for url in urls)
    assert len(download_cpjump1.metadata_downloads(config)) == 4


def test_example_config_parses():
    from pathlib import Path

    config = load_config(Path(__file__).resolve().parents[1] / "config" / "phase1_cpjump1_u2os.toml")
    assert config.selection.timepoints == {"compound": 48, "orf": 48, "crispr": 144}


# --- End to end ----------------------------------------------------------------------


def test_build_dataset_end_to_end(settings, raw_dir):
    summary = build_dataset(make_config(raw_dir))
    assert summary.n_plates == 4
    assert summary.n_features_raw == N_FEATURES + 1
    assert summary.n_features_selected == N_FEATURES  # positional feature blocklisted
    assert any("anomaly 'dye'" in w for w in summary.warnings)

    compounds = pd.read_parquet(settings.compound_profiles_path)
    genetic = pd.read_parquet(settings.genetic_profiles_path)
    controls = pd.read_parquet(settings.control_profiles_path)
    feature_columns = [c for c in compounds.columns if c.startswith("Cells_")]
    assert feature_columns == [c for c in genetic.columns if c.startswith("Cells_")]
    assert feature_columns == [c for c in controls.columns if c.startswith("Cells_")]

    assert sorted(compounds["perturbation_id"]) == sorted(COMPOUNDS)
    assert set(compounds["Metadata_n_replicates"]) == {4}  # 2 wells x 2 plates
    assert sorted(genetic["perturbation_id"]) == sorted([*CRISPR, *ORFS])
    assert set(controls["perturbation_id"]) == {"DMSO", "SG-NEG-0", "SG-NEG-1", "ORF-NEG-0", "ORF-NEG-1"}
    assert (compounds["Metadata_replicate_cosine"] > 0.8).all()

    # Normalized to controls: each compound's signal sits on its own feature, controls near 0.
    a1 = compounds.set_index("perturbation_id").loc["CMP-1", feature_columns].to_numpy(float)
    assert np.argmax(a1) == 0 and a1[0] > 5
    assert np.linalg.norm(controls[feature_columns].to_numpy(float), axis=1).max() < np.linalg.norm(a1)

    metadata = pd.read_parquet(settings.processed_dir / "metadata" / "compound_metadata.parquet")
    row = metadata.set_index("compound_id").loc["CMP-1"]
    assert row["compound_name"] == "drug one" and row["known_target"] == "GENE1|GENE9" and row["moa"] is None
    genes = pd.read_parquet(settings.processed_dir / "metadata" / "genetic_metadata.parquet")
    assert set(genes["perturbation_type"]) == {"crispr", "orf"}
    assert (genes["gene_id"] == genes["gene_symbol"]).all()

    manifest = json.loads((settings.processed_dir / "build" / "manifest.json").read_text())
    assert {p["plate"]: p["n_reference_wells"] for p in manifest["plates"]} == {"PC1": 8, "PC2": 8, "PG1": 8, "PO1": 8}
    assert len(manifest["inputs"]) == 4
    assert (settings.processed_dir / "wells" / "compound_wells.parquet").is_file()


def test_build_with_annotations_and_database(settings, raw_dir, tmp_path, client):
    moa = tmp_path / "moa.txt"
    moa.write_text("!comment line\npert_iname\tmoa\nDRUG ONE\tclass a\ndrug two\tclass b|class c\n", encoding="utf-8")
    gene_ids = tmp_path / "genes.tsv"
    gene_ids.write_text("symbol\tgene_id\nGENE1\t101\nGENE2\t102\n", encoding="utf-8")
    config = make_config(
        raw_dir,
        annotations={"moa_file": str(moa), "gene_id_file": str(gene_ids)},
        output={"load_database": True},
    )
    summary = build_dataset(config)
    assert summary.database_loaded

    detail = client.get("/api/compounds/CMP-2").json()
    assert detail["moa"] == "class b|class c"
    assert client.get("/api/genes/101").json()["gene_symbol"] == "GENE1"
    assert client.get("/api/genes/GENE3").json()["gene_id"] == "GENE3"  # unmapped symbol falls back

    get_profile_store.cache_clear()
    similar = client.post("/api/similarity/compounds", json={"compound_id": "CMP-1"}).json()
    assert similar["predictions"][0]["candidate_id"] == "CMP-3"  # same synthetic direction
    rescue = client.post("/api/rescue/search", json={"perturbation_id": "ORF-1", "top_k": 3}).json()
    assert rescue["predictions"][0]["candidate_id"] in {"CMP-1", "CMP-3"}  # ORF-1 is the negative of that direction


def test_build_cli_dry_run_writes_nothing(settings, raw_dir, tmp_path, capsys):
    config_path = tmp_path / "build.toml"
    config_path.write_text(
        f"""
[source]
name = "synthetic"
batch = "{BATCH}"
raw_dir = "{raw_dir.as_posix()}"
[selection]
cell_type = "CELL_A"
[selection.timepoints]
compound = 48
crispr = 144
orf = 48
""",
        encoding="utf-8",
    )
    assert build_cli.main(["--config", str(config_path), "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["n_plates"] == 4
    assert not settings.compound_profiles_path.exists()
    config_path.write_text(config_path.read_text().replace('cell_type = "CELL_A"', 'cell_type = "NOPE"'))
    assert build_cli.main(["--config", str(config_path)]) == 1
    assert "No plates match" in capsys.readouterr().err
