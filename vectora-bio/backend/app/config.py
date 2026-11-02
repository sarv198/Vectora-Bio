"""Runtime settings loaded from the environment and vectora-bio/.env."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"


def resolve_project_path(path: Path) -> Path:
    """Resolve relative paths from the vectora-bio/ directory."""
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Vectora Bio"
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "staging", "production"] = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://vectora:vectora@localhost:5432/vectora"
    database_connect_timeout_s: int = Field(default=5, ge=1)
    auto_create_tables: bool = True
    persist_analysis_runs: bool = True

    # Comma-separated list, e.g. "http://localhost:3000,http://127.0.0.1:3000".
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    data_raw_dir: Path = Path("data/raw")
    data_processed_dir: Path = Path("data/processed")

    # Processed profile files, relative to data_processed_dir unless absolute.
    compound_profiles_file: Path = Path("profiles/compound_profiles.parquet")
    genetic_profiles_file: Path = Path("profiles/genetic_profiles.parquet")
    control_profiles_file: Path = Path("profiles/control_profiles.parquet")

    # Consensus profiles aggregate replicate wells per perturbation.
    consensus_method: Literal["median", "mean"] = "median"
    max_top_k: int = Field(default=500, ge=1)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def raw_dir(self) -> Path:
        return resolve_project_path(self.data_raw_dir)

    @property
    def processed_dir(self) -> Path:
        return resolve_project_path(self.data_processed_dir)

    def _processed_file(self, path: Path) -> Path:
        return path if path.is_absolute() else (self.processed_dir / path).resolve()

    @property
    def compound_profiles_path(self) -> Path:
        return self._processed_file(self.compound_profiles_file)

    @property
    def genetic_profiles_path(self) -> Path:
        return self._processed_file(self.genetic_profiles_file)

    @property
    def control_profiles_path(self) -> Path:
        return self._processed_file(self.control_profiles_file)

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
