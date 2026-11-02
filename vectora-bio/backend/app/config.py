"""Runtime settings loaded from the environment and cellscope/.env."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
_SQLITE_PATH = (BACKEND_ROOT / "cellscope.db").as_posix()


def _resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Cellscope"
    database_url: str = f"sqlite:///{_SQLITE_PATH}"
    data_raw_dir: Path = PROJECT_ROOT / "data" / "raw"
    data_processed_dir: Path = PROJECT_ROOT / "data" / "processed"

    @property
    def raw_dir(self) -> Path:
        return _resolve_path(self.data_raw_dir)

    @property
    def processed_dir(self) -> Path:
        return _resolve_path(self.data_processed_dir)


settings = Settings()
