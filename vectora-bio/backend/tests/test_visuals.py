"""Phenotype maps, profile overviews/comparisons and on-demand cell image rendering."""

import io

import numpy as np
import pandas as pd
import pytest
from PIL import Image

from app.core.phenotype_map import map_similarity, phenotype_map
from app.data import cell_images
from app.data.cell_images import CellImageSource, display_range, image_filename, parse_well, render_png
from app.errors import ImagesUnavailableError, InvalidQueryError, NotFoundError

# --- phenotype map --------------------------------------------------------------------


def _profile() -> pd.Series:
    return pd.Series(
        {
            "Nuclei_Intensity_MeanIntensity_DNA": 3.0,
            "Nuclei_Texture_Contrast_DNA_3_01_256": -4.0,
            "Cells_Intensity_MeanIntensity_ER": 1.0,
            "Cells_AreaShape_Area": 2.0,
            "Cells_Correlation_Correlation_ER_Mito": 0.5,
            "Image_Count_Cells": 9.0,  # not a cell compartment: ignored
        }
    )


def test_phenotype_map_groups_by_compartment_and_channel():
    cells = {(c.compartment, c.channel): c for c in phenotype_map(_profile())}
    dna = cells[("Nucleus", "DNA")]
    assert dna.n_features == 2
    assert dna.rms == pytest.approx(np.sqrt((9 + 16) / 2))
    assert dna.top_feature == "Nuclei_Texture_Contrast_DNA_3_01_256"
    assert dna.top_value == -4.0
    assert cells[("Cell", "Shape")].n_features == 1
    # A two-channel feature counts towards both channels.
    assert cells[("Cell", "ER")].n_features == 2
    assert cells[("Cell", "Mito")].n_features == 1
    assert all(c.compartment != "Image" for c in cells.values())


def test_map_similarity_detects_opposition_per_cell():
    profile = _profile()
    cells = {(c["compartment"], c["channel"]): c["cosine"] for c in map_similarity(profile, -profile)}
    assert cells[("Nucleus", "DNA")] == pytest.approx(-1.0)
    assert all(value == pytest.approx(-1.0) for value in cells.values())


# --- image helpers --------------------------------------------------------------------


def test_parse_well_and_filename():
    assert parse_well("b07") == (2, 7)
    assert image_filename("P24", 9, "DNA") == "r16c24f09p01-ch5sk1fk1fl1.tiff"
    for bad in ("Q01", "A25", "A0", "../x", ""):
        with pytest.raises(InvalidQueryError):
            parse_well(bad)


def test_display_range_uses_own_background_and_reference_span():
    assert display_range((100.0, 900.0), (50.0, 2050.0)) == (100.0, 2100.0)


def test_render_png_blends_channels_at_requested_size():
    image = np.zeros((8, 8), dtype=np.float32)
    image[:4] = 1000.0
    png = render_png({"DNA": image}, {"DNA": (0.0, 1000.0)}, size=4)
    pixels = np.asarray(Image.open(io.BytesIO(png)))
    assert pixels.shape == (4, 4, 3)
    assert tuple(pixels[0, 0]) == tuple(int(c * 255) for c in cell_images.CHANNEL_COLORS["DNA"])
    assert pixels[3, 3].sum() == 0
    gray = np.asarray(Image.open(io.BytesIO(render_png({"DNA": image}, {"DNA": (0.0, 1000.0)}, 8, grayscale=True))))
    assert tuple(gray[0, 0]) == (255, 255, 255)


def _tiff(value: int) -> bytes:
    data = np.full((1080, 1080), value, dtype=np.uint16)
    data[:540] = value * 4
    buffer = io.BytesIO()
    Image.fromarray(data).save(buffer, format="TIFF")
    return buffer.getvalue()


def test_cell_image_source_fetches_once_and_caches(settings, monkeypatch):
    source = CellImageSource(settings)
    calls: list[str] = []

    def fake_fetch(url: str) -> bytes:
        calls.append(url)
        if "list-type" in url:
            return (
                b"<ListBucketResult><Prefix>x/</Prefix><CommonPrefixes>"
                b"<Prefix>p/PLATE1__2020-Measurement1/</Prefix></CommonPrefixes></ListBucketResult>"
            )
        return _tiff(500)

    monkeypatch.setattr(source, "_fetch", fake_fetch)
    png = source.render("PLATE1", "A01", 5, ["DNA", "ER"], size=270, reference_well="B02")
    assert Image.open(io.BytesIO(png)).size == (270, 270)
    tiffs = [u for u in calls if u.endswith(".tiff")]
    assert len(tiffs) == 4  # 2 channels x (well + reference)
    assert all("PLATE1__2020-Measurement1/Images/" in u for u in tiffs)
    assert (settings.raw_dir / "images" / "cpjump1" / "PLATE1" / "r01c01f05p01-ch5sk1fk1fl1.tiff").is_file()

    calls.clear()
    fresh = CellImageSource(settings)  # new process: disk cache and plates.json are reused
    monkeypatch.setattr(fresh, "_fetch", fake_fetch)
    fresh.render("PLATE1", "A01", 5, ["DNA"], size=270)
    assert calls == []


def test_cell_image_source_validates_and_reports_offline(settings, monkeypatch):
    source = CellImageSource(settings)
    with pytest.raises(InvalidQueryError):
        source.render("PLATE1", "A01", 5, ["Nope"])
    with pytest.raises(InvalidQueryError):
        source.render("PLATE1", "A01", 12, ["DNA"])
    with pytest.raises(InvalidQueryError):
        source.render("PLATE1", "A01", 5, ["DNA", "ER"], grayscale=True)

    def offline(url: str) -> bytes:
        raise ImagesUnavailableError("offline")

    monkeypatch.setattr(source, "_fetch", offline)
    with pytest.raises(ImagesUnavailableError):
        source.render("PLATE1", "A01", 5, ["DNA"])


# --- API ------------------------------------------------------------------------------


def test_profile_overview_endpoint(client, loaded_data):
    response = client.get("/api/profiles/genetic/GUIDE_G1_1")
    assert response.status_code == 200
    body = response.json()
    assert body["perturbation_id"] == "GUIDE_G1_1"
    assert body["n_features"] == 12
    assert body["response_norm"] > 0
    assert len(body["top_features"]) == 8
    # Synthetic data has no well-level files, so no images are offered (never faked).
    assert body["wells"] == []
    assert body["images"]["available"] is False
    assert body["images"]["message"]

    assert client.get("/api/profiles/compound/NOPE").status_code == 404
    assert client.get("/api/profiles/control/CTRL_24_0").status_code == 400


def test_profile_compare_endpoint(client, loaded_data):
    response = client.get(
        "/api/profiles/compare",
        params={"first_type": "compound", "first_id": "CMPD_A1", "second_type": "genetic", "second_id": "GUIDE_G1_1"},
    )
    assert response.status_code == 200
    assert response.json()["cosine"] > 0.8


def test_profile_endpoints_need_data(client):
    response = client.get("/api/profiles/compound/CMPD_A1")
    assert response.status_code == 503
    assert response.json()["error"] == "data_not_loaded"


def test_image_endpoint_rejects_unknown_plates(client, loaded_data):
    response = client.get("/api/images/NOT_A_PLATE/A01")
    assert response.status_code == 404
    assert isinstance(NotFoundError("x"), Exception)


def test_plates_need_well_files(client, loaded_data):
    response = client.get("/api/plates")
    assert response.status_code == 503
    assert response.json()["details"]["missing_datasets"] == ["well_profiles"]


def test_plate_layout_from_well_files(client, loaded_data, settings):
    wells_dir = settings.processed_dir / "wells"
    wells_dir.mkdir(parents=True, exist_ok=True)
    base = {"cell_line": "U2OS", "timepoint": 48.0, "Metadata_Plate": "P1", "f": 0.0}
    pd.DataFrame(
        [{**base, "Metadata_Well": "B02", "perturbation_id": "CMPD_A1", "Metadata_modality": "compound"}]
    ).to_parquet(wells_dir / "compound_wells.parquet")
    pd.DataFrame(
        [{**base, "Metadata_Well": "A01", "perturbation_id": "DMSO", "Metadata_modality": "compound"}]
    ).to_parquet(wells_dir / "control_wells.parquet")

    plates = client.get("/api/plates").json()
    assert plates == [
        {"plate": "P1", "modality": "compound", "cell_line": "U2OS", "timepoint": 48.0, "n_wells": 2, "n_controls": 1}
    ]
    layout = client.get("/api/plates/P1").json()
    assert [(w["well"], w["kind"], w["perturbation_id"]) for w in layout["wells"]] == [
        ("A01", "control", None),
        ("B02", "compound", "CMPD_A1"),
    ]
    assert client.get("/api/plates/P2").status_code == 404

    overview = client.get("/api/profiles/compound/CMPD_A1").json()
    assert overview["wells"] == [{"plate": "P1", "well": "B02", "control_well": "A01"}]
    assert overview["images"]["available"] is True
