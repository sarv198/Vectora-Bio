"""Load processed tables and signature files."""

import json
import math
from pathlib import Path

import pandas as pd

from app.config import settings


def _table_path(name: str, suffix: str) -> Path:
    return settings.processed_dir / f"{name}.{suffix}"


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return str(value).strip().lower() in {"", "nan", "none"}


def load_table(name: str) -> pd.DataFrame:
    """Load a processed table from parquet, then CSV. Missing files yield an empty frame."""
    parquet_path = _table_path(name, "parquet")
    if parquet_path.is_file():
        return pd.read_parquet(parquet_path)
    csv_path = _table_path(name, "csv")
    if csv_path.is_file():
        return pd.read_csv(csv_path)
    return pd.DataFrame()


def load_records(name: str) -> list[dict]:
    frame = load_table(name)
    if frame.empty:
        return []
    records = frame.to_dict(orient="records")
    cleaned: list[dict] = []
    for record in records:
        cleaned.append({key: None if _is_missing(value) else value for key, value in record.items()})
    return cleaned


def load_signature(signature_id: str) -> dict[str, float]:
    """Load data/processed/signatures/<signature_id>.json.

    Raises FileNotFoundError when the file is absent.
    """
    path = settings.processed_dir / "signatures" / f"{signature_id}.json"
    if not path.is_file():
        raise FileNotFoundError(signature_id)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("values"), dict):
        payload = payload["values"]
    if not isinstance(payload, dict):
        raise ValueError(f"Signature '{signature_id}' must be an object of gene values.")
    return {str(gene): float(value) for gene, value in payload.items()}
