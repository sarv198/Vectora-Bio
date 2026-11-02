"""Helpers shared by the pipeline commands."""

import json
import os
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

NUMERIC_CONSTANTS = {"timepoint", "replicate_count"}


def load_column_map(path: str | Path | None) -> dict[str, str]:
    """Read a JSON object mapping source column names to canonical names."""
    if path is None:
        return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in payload.items()
    ):
        raise ValueError(f"{path} must be a JSON object of source column -> canonical column.")
    return {key: value for key, value in payload.items() if not key.startswith("_")}


def parse_assignments(values: Sequence[str] | None) -> dict[str, object]:
    """Parse ``["cell_line=U2OS", "timepoint=48"]`` into a dict (numeric for known numeric columns)."""
    constants: dict[str, object] = {}
    for item in values or []:
        if "=" not in item:
            raise ValueError(f"Expected COLUMN=VALUE, got {item!r}.")
        key, value = (part.strip() for part in item.split("=", 1))
        if not key:
            raise ValueError(f"Missing column name in {item!r}.")
        constants[key] = float(value) if key in NUMERIC_CONSTANTS else value
    return constants


def apply_column_map(frame: pd.DataFrame, column_map: dict[str, str]) -> pd.DataFrame:
    present = {source: target for source, target in column_map.items() if source in frame.columns}
    targets = list(present.values())
    duplicates = sorted({target for target in targets if targets.count(target) > 1})
    if duplicates:
        raise ValueError(f"Several source columns map to the same target: {duplicates}.")
    clashes = sorted(set(targets) & (set(frame.columns) - set(present)))
    if clashes:
        raise ValueError(f"Mapped column(s) already exist in the input: {clashes}.")
    return frame.rename(columns=present)


def apply_constants(frame: pd.DataFrame, constants: dict[str, object]) -> pd.DataFrame:
    clashes = sorted(column for column in constants if column in frame.columns)
    if clashes:
        raise ValueError(f"Column(s) {clashes} already exist in the input; remove them from --set.")
    return frame.assign(**constants)


def write_parquet_atomic(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_parquet(temporary, index=False)
    os.replace(temporary, path)
