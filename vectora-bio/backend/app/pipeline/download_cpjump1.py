"""Download the JUMP pilot (CPJUMP1) files a build config selects; nothing else.

    python -m app.pipeline.download_cpjump1 --config config/phase1_cpjump1_u2os.toml --dry-run
    python -m app.pipeline.download_cpjump1 --config config/phase1_cpjump1_u2os.toml

Fetches the experiment metadata and JUMP-Target-1 perturbation metadata (GitHub), then only
the selected plates' per-plate profile files from the public Cell Painting Gallery bucket.
Existing files with the expected size are skipped.
"""

import argparse
import sys
import urllib.request
from pathlib import Path

from app.preprocessing import sources
from app.preprocessing.config import BuildConfig, load_config

USER_AGENT = "vectora-bio-downloader"
_CHUNK = 1 << 20


def _remote_size(url: str) -> int | None:
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        length = response.headers.get("Content-Length")
    return int(length) if length else None


def _download(url: str, destination: Path) -> str:
    size = _remote_size(url)
    if destination.is_file() and size is not None and destination.stat().st_size == size:
        return "exists"
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=300) as response, partial.open("wb") as handle:
        while chunk := response.read(_CHUNK):
            handle.write(chunk)
    if size is not None and partial.stat().st_size != size:
        partial.unlink()
        raise OSError(f"Incomplete download of {url}")
    partial.replace(destination)
    return "downloaded"


def metadata_downloads(config: BuildConfig) -> list[tuple[str, Path]]:
    source = config.source
    files = [(sources.EXPERIMENT_METADATA_URL, source.metadata_file(source.experiment_metadata))]
    for name in (source.compound_metadata, source.crispr_metadata, source.orf_metadata):
        files.append((f"{sources.EXTERNAL_METADATA_URL}/{name}", source.metadata_file(name)))
    return files


def plate_downloads(config: BuildConfig) -> list[tuple[str, Path]]:
    plates = sources.select_plates(sources.read_experiment_metadata(config), config)
    return [
        (sources.plate_url(config.source.batch, plate, config.source.profile_suffix), config.source.plate_file(plate))
        for plate in plates["plate"]
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", required=True, help="Build config (TOML).")
    parser.add_argument("--dry-run", action="store_true", help="List the plate files and total size only.")
    args = parser.parse_args(argv)
    config = load_config(args.config)

    try:
        for url, path in metadata_downloads(config):
            print(f"[{_download(url, path)}] {path}")
        plates = plate_downloads(config)
    except (OSError, sources.SourceError) as exc:
        print(f"Download failed: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        total = 0
        for url, _path in plates:
            size = _remote_size(url) or 0
            total += size
            print(f"{size / 1e6:8.1f} MB  {url}")
        print(f"{len(plates)} plate file(s), {total / 1e6:.1f} MB -> {config.source.raw_path}")
        return 0

    for index, (url, path) in enumerate(plates, start=1):
        try:
            status = _download(url, path)
        except OSError as exc:
            print(f"Download failed for {url}: {exc}", file=sys.stderr)
            return 1
        print(f"[{index}/{len(plates)}] [{status}] {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
