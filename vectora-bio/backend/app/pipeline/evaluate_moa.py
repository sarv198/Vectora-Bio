"""Run the leave-one-out MoA benchmark on imported data and store the metrics.

python -m app.pipeline.evaluate_moa --cell-line U2OS --timepoint 48 --n-neighbors 20 --k 10
"""

import argparse
import json
import sys

from app.data.profile_store import get_profile_store
from app.db.session import get_session_factory, init_db
from app.errors import VectoraError
from app.services.evaluation_service import run_moa_benchmark


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cell-line")
    parser.add_argument("--timepoint", type=float)
    parser.add_argument("--n-neighbors", type=int, default=20)
    parser.add_argument("--k", type=int, default=10)
    args = parser.parse_args(argv)
    try:
        init_db()
        with get_session_factory()() as db:
            results = run_moa_benchmark(
                get_profile_store(),
                db,
                cell_line=args.cell_line,
                timepoint=args.timepoint,
                n_neighbors=args.n_neighbors,
                k=args.k,
            )
    except VectoraError as exc:
        print(f"Evaluation failed: {exc.message}", file=sys.stderr)
        print(json.dumps(exc.details, indent=2, default=str), file=sys.stderr)
        return 1
    print(json.dumps([result.model_dump(mode="json") for result in results], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
