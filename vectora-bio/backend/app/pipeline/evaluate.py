"""Run the held-out benchmarks on imported data and store the metrics (Phase 6).

python -m app.pipeline.evaluate
python -m app.pipeline.evaluate --split target_group --folds 5 --seed 1
"""

import argparse
import json
import sys

from app.data.profile_store import get_profile_store
from app.db.session import get_session_factory, init_db
from app.errors import VectoraError
from app.schemas.evaluation import EvaluationRunRequest
from app.services.evaluation_service import run_benchmarks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cell-line")
    parser.add_argument("--timepoint", type=float)
    parser.add_argument("--split", choices=["random", "target_group", "both"], default="both")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--n-neighbors", type=int, default=10)
    parser.add_argument("--neighbor-weight", type=float, default=2.0)
    args = parser.parse_args(argv)
    request = EvaluationRunRequest(
        cell_line=args.cell_line,
        timepoint=args.timepoint,
        split_strategies=["random", "target_group"] if args.split == "both" else [args.split],
        n_folds=args.folds,
        seed=args.seed,
        k=args.k,
        n_neighbors=args.n_neighbors,
        neighbor_weight=args.neighbor_weight,
    )
    try:
        init_db()
        with get_session_factory()() as db:
            response = run_benchmarks(get_profile_store(), db, request)
    except VectoraError as exc:
        print(f"Evaluation failed: {exc.message}", file=sys.stderr)
        print(json.dumps(exc.details, indent=2, default=str), file=sys.stderr)
        return 1

    print(f"Run {response.run_id}")
    rows = sorted(
        response.results,
        key=lambda r: (r.parameters["split_strategy"], r.metric_name, r.parameters["model"] != "baseline"),
    )
    for record in rows:
        p = record.parameters
        std = f" ± {p['fold_std']:.3f}" if p.get("fold_std") is not None else ""
        label = f"[{p['split_strategy']:12s}] {record.metric_name:38s} {p['model']:14s}"
        print(f"  {label} {record.metric_value:.3f}{std}  (n={record.sample_count})")
    print(json.dumps({"audit": response.audit, "notes": response.notes}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
