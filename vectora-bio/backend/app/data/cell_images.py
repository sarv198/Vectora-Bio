"""On-demand Cell Painting microscopy fields from the public Cell Painting Gallery.

Only the channels of the one well and field (site) a user asks to view are fetched, and
each TIFF is cached under ``data/raw/images/`` so it is downloaded at most once. Display
ranges are taken from a reference well (normally a negative-control well on the same
plate), so a perturbation and its control are rendered on identical intensity scales and
brightness differences between them are real.

CPJUMP1 file layout (Opera Phenix): ``r{row}c{col}f{field}p01-ch{n}sk1fk1fl1.tiff`` with
ch1 Mito, ch2 AGP, ch3 RNA, ch4 ER, ch5 DNA, ch8 brightfield; 9 fields of 1080 x 1080 px
at 0.598 um/px per well.
"""

import io
import json
import logging
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

from app.config import Settings, get_settings
from app.errors import ImagesUnavailableError, InvalidQueryError, NotFoundError

logger = logging.getLogger(__name__)

CHANNEL_INDEX = {"Mito": 1, "AGP": 2, "RNA": 3, "ER": 4, "DNA": 5, "Brightfield": 8}
FLUORESCENT_CHANNELS = ("DNA", "ER", "RNA", "AGP", "Mito")
CHANNEL_COLORS: dict[str, tuple[float, float, float]] = {
    "DNA": (0.20, 0.45, 1.00),
    "ER": (0.10, 0.95, 0.25),
    "RNA": (1.00, 0.80, 0.05),
    "AGP": (1.00, 0.20, 0.85),
    "Mito": (1.00, 0.18, 0.08),
    "Brightfield": (1.00, 1.00, 1.00),
}
FIELDS = tuple(range(1, 10))
DEFAULT_FIELD = 5
IMAGE_SIZE_PX = 1080
PIXEL_SIZE_UM = 0.598
ALLOWED_SIZES = (270, 360, 540, 1080)
BACKGROUND_PERCENTILE, HIGH_PERCENTILE = 10.0, 99.8

_WELL = re.compile(r"^([A-P])(\d{1,2})$")
_PLATE = re.compile(r"^[A-Za-z0-9-]{3,40}$")
_PREFIX = re.compile(r"<Prefix>([^<]+)</Prefix>")


def parse_well(well: str) -> tuple[int, int]:
    """'B07' -> (2, 7). Raises InvalidQueryError for anything that is not a 384-well position."""
    match = _WELL.match(well.strip().upper())
    if not match or not 1 <= int(match.group(2)) <= 24:
        raise InvalidQueryError(f"Invalid well {well!r}; expected e.g. 'A01'.")
    return ord(match.group(1)) - ord("A") + 1, int(match.group(2))


def image_filename(well: str, field: int, channel: str) -> str:
    row, col = parse_well(well)
    return f"r{row:02d}c{col:02d}f{field:02d}p01-ch{CHANNEL_INDEX[channel]}sk1fk1fl1.tiff"


def contrast_limits(image: np.ndarray) -> tuple[float, float]:
    """(background, bright) intensity levels of one image."""
    low, high = np.percentile(image, [BACKGROUND_PERCENTILE, HIGH_PERCENTILE])
    return float(low), float(max(high, low + 1.0))


def display_range(own: tuple[float, float], reference: tuple[float, float]) -> tuple[float, float]:
    """Black point at the image's own background; intensity span taken from the reference.

    Background (medium fluorescence, illumination) differs from well to well, so each image
    is offset by its own background, while the gain above background is shared with the
    reference so that brighter staining stays visibly brighter.
    """
    span = reference[1] - reference[0]
    return own[0], own[0] + max(span, 1.0)


def render_png(
    images: dict[str, np.ndarray],
    limits: dict[str, tuple[float, float]],
    size: int,
    grayscale: bool = False,
) -> bytes:
    """Scale each channel to its display range, downsample, and blend additively into a PNG."""
    rgb: np.ndarray | None = None
    for channel, image in images.items():
        low, high = limits[channel]
        scaled = np.clip((image.astype(np.float32) - low) / (high - low), 0.0, 1.0)
        if scaled.shape[0] != size:
            scaled = np.asarray(Image.fromarray(scaled).resize((size, size), Image.Resampling.BOX), dtype=np.float32)
        color = (1.0, 1.0, 1.0) if grayscale else CHANNEL_COLORS[channel]
        layer = scaled[..., None] * np.asarray(color, dtype=np.float32)
        rgb = layer if rgb is None else rgb + layer
    if rgb is None:
        raise InvalidQueryError("No channels selected.")
    pixels = (np.clip(rgb, 0.0, 1.0) * 255).astype(np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(pixels).save(buffer, format="PNG", compress_level=6)
    return buffer.getvalue()


class CellImageSource:
    """Fetches, caches and renders single microscopy fields."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._root = settings.raw_dir / "images" / "cpjump1"
        self._lock = threading.Lock()
        self._file_locks: dict[Path, threading.Lock] = {}
        self._folders: dict[str, str] | None = None
        self._limits: dict[tuple[str, str, int, str], tuple[float, float]] = {}
        self._rendered: OrderedDict[tuple, bytes] = OrderedDict()
        self._pool = ThreadPoolExecutor(max_workers=6, thread_name_prefix="cell-images")

    @property
    def enabled(self) -> bool:
        return self._settings.cell_images_enabled

    # -- remote access -------------------------------------------------------------------
    def _fetch(self, url: str) -> bytes:
        try:
            with urllib.request.urlopen(url, timeout=self._settings.cell_image_timeout_s) as response:  # noqa: S310
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 404):
                raise NotFoundError(f"Image not found in the Cell Painting Gallery ({exc.code}).") from exc
            raise ImagesUnavailableError(f"Cell Painting Gallery returned HTTP {exc.code}.") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ImagesUnavailableError(
                "Could not reach the Cell Painting Gallery to fetch images. Check the internet connection.",
                details={"reason": str(getattr(exc, "reason", exc))},
            ) from exc

    def _folder_cache(self) -> dict[str, str]:
        if self._folders is None:
            path = self._root / "plates.json"
            self._folders = json.loads(path.read_text()) if path.is_file() else {}
        return self._folders

    def plate_folder(self, plate: str) -> str:
        """Image folder of a plate, e.g. 'BR00117010__2020-11-08T18_18_00-Measurement1' (cached)."""
        if not _PLATE.match(plate):
            raise InvalidQueryError(f"Invalid plate {plate!r}.")
        with self._lock:
            cached = self._folder_cache().get(plate)
        if cached:
            return cached
        query = urllib.parse.urlencode(
            {"list-type": "2", "prefix": f"{self._settings.cell_image_prefix}{plate}__", "delimiter": "/"}
        )
        listing = self._fetch(f"{self._settings.cell_image_bucket_url}/?{query}").decode("utf-8", "replace")
        folders = sorted(p.rstrip("/").rsplit("/", 1)[-1] for p in _PREFIX.findall(listing) if p.endswith("/"))
        folders = [f for f in folders if f.startswith(f"{plate}__")]
        if not folders:
            raise NotFoundError(f"No images for plate {plate} in the Cell Painting Gallery.")
        folder = folders[-1]  # latest measurement if a plate was re-imaged
        with self._lock:
            cache = self._folder_cache()
            cache[plate] = folder
            self._root.mkdir(parents=True, exist_ok=True)
            (self._root / "plates.json").write_text(json.dumps(cache, indent=1, sort_keys=True))
        return folder

    def channel_path(self, plate: str, well: str, field: int, channel: str) -> Path:
        """Local path of one channel TIFF, downloading it on first use."""
        name = image_filename(well, field, channel)
        path = self._root / plate / name
        if path.is_file():
            return path
        with self._lock:
            file_lock = self._file_locks.setdefault(path, threading.Lock())
        with file_lock:
            if path.is_file():
                return path
            folder = self.plate_folder(plate)
            url = f"{self._settings.cell_image_bucket_url}/{self._settings.cell_image_prefix}{folder}/Images/{name}"
            data = self._fetch(url)
            path.parent.mkdir(parents=True, exist_ok=True)
            partial = path.with_suffix(".part")
            partial.write_bytes(data)
            partial.replace(path)
            logger.info("Fetched %s (%.1f MB)", url, len(data) / 1e6)
        return path

    def read(self, plate: str, well: str, field: int, channel: str) -> np.ndarray:
        path = self.channel_path(plate, well, field, channel)
        try:
            with Image.open(path) as image:
                return np.asarray(image, dtype=np.float32)
        except OSError as exc:
            path.unlink(missing_ok=True)  # corrupt download; refetch next time
            raise ImagesUnavailableError(f"Could not decode {path.name}; it will be refetched.") from exc

    # -- rendering -----------------------------------------------------------------------
    def limits(self, plate: str, well: str, field: int, channel: str) -> tuple[float, float]:
        key = (plate, well, field, channel)
        with self._lock:
            if key in self._limits:
                return self._limits[key]
        value = contrast_limits(self.read(plate, well, field, channel))
        with self._lock:
            self._limits[key] = value
        return value

    def render(
        self,
        plate: str,
        well: str,
        field: int,
        channels: list[str],
        size: int = 540,
        reference_well: str | None = None,
        grayscale: bool = False,
    ) -> bytes:
        """PNG of one field. Display ranges come from ``reference_well`` (same plate and field)."""
        if not self.enabled:
            raise ImagesUnavailableError("Cell images are disabled (CELL_IMAGES_ENABLED=false).")
        well = well.strip().upper()
        reference = (reference_well or well).strip().upper()
        parse_well(well)
        parse_well(reference)
        if field not in FIELDS:
            raise InvalidQueryError(f"Field must be 1-9, got {field}.")
        if size not in ALLOWED_SIZES:
            raise InvalidQueryError(f"Size must be one of {ALLOWED_SIZES}.")
        unknown = [c for c in channels if c not in CHANNEL_INDEX]
        if unknown or not channels:
            raise InvalidQueryError(f"Unknown channel(s) {unknown}; choose from {list(CHANNEL_INDEX)}.")
        if grayscale and len(channels) != 1:
            raise InvalidQueryError("Grayscale rendering takes exactly one channel.")

        key = (plate, well, field, tuple(channels), size, reference, grayscale)
        with self._lock:
            if key in self._rendered:
                self._rendered.move_to_end(key)
                return self._rendered[key]

        # Fetch everything needed in parallel (first view of a well downloads its channels).
        jobs = [(plate, well, field, c) for c in channels]
        if reference != well:
            jobs += [(plate, reference, field, c) for c in channels]
        list(self._pool.map(lambda job: self.channel_path(*job), jobs))

        images = {c: self.read(plate, well, field, c) for c in channels}
        limits = {
            c: display_range(self.limits(plate, well, field, c), self.limits(plate, reference, field, c))
            for c in channels
        }
        png = render_png(images, limits, size, grayscale=grayscale)
        with self._lock:
            self._rendered[key] = png
            while len(self._rendered) > 96:
                self._rendered.popitem(last=False)
        return png


@lru_cache
def get_cell_image_source() -> CellImageSource:
    return CellImageSource(get_settings())
