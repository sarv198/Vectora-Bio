"""Assemble the Docker build folder for the CellScope API image (deployed on Render).

Usage, from vectora-bio/ (see docs/deployment.md, step 2):
    python scripts/stage_api.py
    docker build -t <dockerhub-user>/cellscope-api:latest deploy/api/build
    docker push <dockerhub-user>/cellscope-api:latest

The output folder (deploy/api/build/) is gitignored. It contains:
    Dockerfile              from deploy/api/
    backend/                app code, config and requirements (no venv, tests, caches)
    data/processed/         the processed profiles and well tables the API reads

Nothing secret is copied: .env stays local and the database URL is set on the host.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
TEMPLATE = PROJECT / "deploy" / "api"
BUILD = TEMPLATE / "build"

BACKEND_ITEMS = ["app", "config", "requirements.txt", "pyproject.toml"]
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".env*")
REQUIRED_DATA = [
    "profiles/compound_profiles.parquet",
    "profiles/genetic_profiles.parquet",
    "profiles/control_profiles.parquet",
]


def folder_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def main() -> int:
    processed = PROJECT / "data" / "processed"
    missing = [name for name in REQUIRED_DATA if not (processed / name).is_file()]
    if missing:
        print("Missing processed data, build it first (see README):", *missing, sep="\n  ")
        return 1

    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True)

    shutil.copy2(TEMPLATE / "Dockerfile", BUILD / "Dockerfile")

    backend = BUILD / "backend"
    backend.mkdir()
    for item in BACKEND_ITEMS:
        source = PROJECT / "backend" / item
        if source.is_dir():
            shutil.copytree(source, backend / item, ignore=IGNORE)
        elif source.is_file():
            shutil.copy2(source, backend / item)

    shutil.copytree(processed, BUILD / "data" / "processed", ignore=shutil.ignore_patterns(".gitkeep"))

    leaked = [p for p in BUILD.rglob(".env*")]
    if leaked:
        print("Refusing to continue: found environment files in the build:", *leaked, sep="\n  ")
        shutil.rmtree(BUILD)
        return 1

    mb = folder_size(BUILD) / 1e6
    print(f"Staged {BUILD} ({mb:.1f} MB)")
    folder = BUILD.relative_to(PROJECT).as_posix()
    print("Build and push with:")
    print(f"  docker build -t <dockerhub-user>/cellscope-api:latest {folder}")
    print("  docker push <dockerhub-user>/cellscope-api:latest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
