"""Test configuration: isolated SQLite database and data directory per test."""

from collections.abc import Iterator

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.data.profile_store import get_profile_store
from app.db.session import get_engine, get_session_factory
from app.pipeline.import_metadata import import_metadata
from app.pipeline.import_profiles import import_profiles
from app.schemas.common import ProfileType
from tests import synthetic


def _clear_caches() -> None:
    if get_engine.cache_info().currsize:
        get_engine().dispose()
    for cached in (get_settings, get_engine, get_session_factory, get_profile_store):
        cached.cache_clear()


@pytest.fixture
def settings(tmp_path, monkeypatch) -> Iterator[Settings]:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    monkeypatch.setenv("DATA_RAW_DIR", str(tmp_path / "raw"))
    monkeypatch.setenv("DATA_PROCESSED_DIR", str(tmp_path / "processed"))
    monkeypatch.setenv("ENVIRONMENT", "test")
    for name in ("COMPOUND_PROFILES_FILE", "GENETIC_PROFILES_FILE", "CONTROL_PROFILES_FILE"):
        monkeypatch.delenv(name, raising=False)
    _clear_caches()
    yield get_settings()
    _clear_caches()


@pytest.fixture
def client(settings) -> Iterator[TestClient]:
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


def _write(tmp_path, name: str, frame: pd.DataFrame) -> str:
    path = tmp_path / name
    frame.to_parquet(path, index=False)
    return str(path)


@pytest.fixture
def loaded_data(settings, tmp_path) -> Settings:
    """Import synthetic compound, genetic, and control profiles plus metadata."""
    import_profiles(_write(tmp_path, "c.parquet", synthetic.compound_profiles()), ProfileType.COMPOUND)
    import_profiles(_write(tmp_path, "g.parquet", synthetic.genetic_profiles()), ProfileType.GENETIC)
    controls = pd.concat(
        [
            synthetic.control_profiles(synthetic.COMPOUND_TIMEPOINT),
            synthetic.control_profiles(synthetic.GENETIC_TIMEPOINT, seed=3),
        ],
        ignore_index=True,
    )
    import_profiles(_write(tmp_path, "ctrl.parquet", controls), ProfileType.CONTROL)

    compounds_csv = tmp_path / "compounds.csv"
    synthetic.COMPOUND_METADATA.to_csv(compounds_csv, index=False)
    import_metadata(compounds_csv, "compounds")
    genetic_csv = tmp_path / "genetic.csv"
    synthetic.GENETIC_METADATA.to_csv(genetic_csv, index=False)
    import_metadata(genetic_csv, "genetic")
    return settings
