"""Build processed profiles and metadata from downloaded raw plates (Phase 1).

python -m app.pipeline.build_profiles --config config/phase1_cpjump1_u2os.toml --dry-run
python -m app.pipeline.build_profiles --config config/phase1_cpjump1_u2os.toml --load-db
"""

import argparse
import json
import sys
from dataclasses import asdict

from app.errors import VectoraError
from app.preprocessing.build import build_dataset
from app.preprocessing.config import load_config
from app.preprocessing.sources import SourceError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", required=True, help="Build config (TOML).")
    parser.add_argument("--dry-run", action="store_true", help="Run every step but write nothing.")
    parser.add_argument("--load-db", action="store_true", help="Also upsert metadata and register datasets in the DB.")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    if args.load_db:
        config.output.load_database = True
    try:
        summary = build_dataset(config, dry_run=args.dry_run)
    except VectoraError as exc:
        print(f"Build failed: {exc.message}", file=sys.stderr)
        print(json.dumps(exc.details, indent=2, default=str), file=sys.stderr)
        return 1
    except (SourceError, FileNotFoundError, ValueError) as exc:
        print(f"Build failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(asdict(summary), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
