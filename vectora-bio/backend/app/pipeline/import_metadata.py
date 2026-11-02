"""Import compound or genetic perturbation metadata into the database.

Examples::

    python -m app.pipeline.import_metadata compounds --input ../data/raw/compounds_annotated.csv \\
        --column-map config/compound_metadata_map.example.json --set cell_line=U2OS --set timepoint=48

    python -m app.pipeline.import_metadata genetic --input ../data/raw/crispr.csv.gz \\
        --column-map config/genetic_metadata_map.example.json \\
        --set perturbation_type=crispr --set cell_line=U2OS --set timepoint=96

Rows are validated with the API schemas and upserted on their natural key
(``compound_id, cell_line, timepoint`` or ``perturbation_id, cell_line, timepoint``).
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ValidationError
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings, get_settings
from app.data.loaders import read_table
from app.db.models import CompoundRecord, GeneticPerturbationRecord
from app.db.session import get_engine, get_session_factory, init_db
from app.pipeline.common import apply_column_map, apply_constants, load_column_map, parse_assignments
from app.schemas.compound import Compound
from app.schemas.genetic import GeneticPerturbation

MetadataKind = Literal["compounds", "genetic"]
_MAX_REPORTED_ERRORS = 20
_CHUNK = 1000

_KINDS: dict[str, tuple[type[BaseModel], type, list[str]]] = {
    "compounds": (Compound, CompoundRecord, ["compound_id", "cell_line", "timepoint"]),
    "genetic": (GeneticPerturbation, GeneticPerturbationRecord, ["perturbation_id", "cell_line", "timepoint"]),
}


class MetadataImportError(ValueError):
    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or []


def _clean(value: object) -> object:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _replicate_counts(settings: Settings) -> pd.Series | None:
    path = settings.compound_profiles_path
    if not path.is_file():
        return None
    frame = pd.read_parquet(path, columns=["perturbation_id", "cell_line", "timepoint"])
    frame["timepoint"] = frame["timepoint"].astype(float)
    return frame.groupby(["perturbation_id", "cell_line", "timepoint"]).size()


def prepare_metadata(
    frame: pd.DataFrame,
    kind: MetadataKind,
    *,
    column_map: dict[str, str] | None = None,
    constants: dict[str, object] | None = None,
    name_fallback_to_id: bool = False,
    settings: Settings | None = None,
) -> list[dict]:
    """Rename, complete, and validate rows. Raises ``MetadataImportError`` listing invalid rows."""
    schema, _, key = _KINDS[kind]
    frame = apply_constants(apply_column_map(frame, column_map or {}), constants or {})

    if kind == "compounds":
        if name_fallback_to_id:
            names = frame["compound_name"] if "compound_name" in frame.columns else pd.Series(None, index=frame.index)
            blank = names.isna() | (names.astype(str).str.strip() == "")
            frame = frame.assign(compound_name=names.where(~blank, frame["compound_id"]))
        if "replicate_count" not in frame.columns:
            counts = _replicate_counts(settings or get_settings())
            if counts is None:
                raise MetadataImportError(
                    "No replicate_count column and no imported compound profiles to count replicates from. "
                    "Import compound profiles first or provide replicate_count."
                )
            index = pd.MultiIndex.from_arrays(
                [frame["compound_id"].astype(str), frame["cell_line"].astype(str), frame["timepoint"].astype(float)]
            )
            frame = frame.assign(replicate_count=counts.reindex(index).fillna(0).astype(int).to_numpy())
    elif "perturbation_type" in frame.columns:
        frame = frame.assign(perturbation_type=frame["perturbation_type"].astype(str).str.strip().str.lower())

    fields = list(schema.model_fields)
    missing = [name for name in fields if name not in frame.columns and schema.model_fields[name].is_required()]
    if missing:
        raise MetadataImportError(f"Missing required column(s) after mapping: {missing}.")

    rows: list[dict] = []
    errors: list[str] = []
    n_invalid = 0
    for position, record in enumerate(frame[[c for c in fields if c in frame.columns]].to_dict(orient="records")):
        try:
            rows.append(schema.model_validate({k: _clean(v) for k, v in record.items()}).model_dump(mode="json"))
        except ValidationError as exc:
            n_invalid += 1
            if len(errors) < _MAX_REPORTED_ERRORS:
                problems = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
                errors.append(f"row {position}: {problems}")
    if n_invalid:
        raise MetadataImportError(f"{n_invalid} row(s) failed validation.", errors)

    deduplicated = {tuple(row[k] for k in key): row for row in reversed(rows)}
    return list(reversed(deduplicated.values()))


def upsert_rows(kind: MetadataKind, rows: list[dict]) -> int:
    _, model, key = _KINDS[kind]
    dialect = get_engine().dialect.name
    insert = {"postgresql": postgresql.insert, "sqlite": sqlite.insert}.get(dialect)
    if insert is None:
        raise MetadataImportError(f"Upsert is not implemented for the '{dialect}' dialect.")
    init_db()
    with get_session_factory()() as db:
        for start in range(0, len(rows), _CHUNK):
            statement = insert(model).values(rows[start : start + _CHUNK])
            updates = {column: statement.excluded[column] for column in rows[0] if column not in key}
            db.execute(statement.on_conflict_do_update(index_elements=key, set_=updates))
        db.commit()
    return len(rows)


def import_metadata(
    input_path: str | Path,
    kind: MetadataKind,
    *,
    column_map: dict[str, str] | None = None,
    constants: dict[str, object] | None = None,
    name_fallback_to_id: bool = False,
    dry_run: bool = False,
) -> dict:
    frame = read_table(input_path)
    rows = prepare_metadata(
        frame, kind, column_map=column_map, constants=constants, name_fallback_to_id=name_fallback_to_id
    )
    summary = {
        "kind": kind,
        "source_path": str(Path(input_path).resolve()),
        "n_input_rows": len(frame),
        "n_records": len(rows),
        "dry_run": dry_run,
    }
    if not dry_run and rows:
        summary["n_upserted"] = upsert_rows(kind, rows)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("kind", choices=list(_KINDS))
    parser.add_argument("--input", required=True)
    parser.add_argument("--column-map", help="JSON object mapping source columns to canonical columns.")
    parser.add_argument("--set", action="append", metavar="COLUMN=VALUE", help="Constant column, e.g. cell_line=U2OS.")
    parser.add_argument(
        "--name-fallback-to-id", action="store_true", help="Use compound_id when compound_name is blank."
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = import_metadata(
            args.input,
            args.kind,
            column_map=load_column_map(args.column_map),
            constants=parse_assignments(args.set),
            name_fallback_to_id=args.name_fallback_to_id,
            dry_run=args.dry_run,
        )
    except MetadataImportError as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        for error in exc.errors:
            print(f"  {error}", file=sys.stderr)
        return 1
    except (FileNotFoundError, ValueError) as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        return 1
    except SQLAlchemyError as exc:
        print(f"Database error: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
