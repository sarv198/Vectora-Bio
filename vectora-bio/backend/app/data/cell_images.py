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

import ctypes
import io
import json
import logging
import os
import re
import sys
import threading
import time
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
# The website's per-stain ("Channels") tiles. Rendering a composite also keeps a grayscale tile
# of each stain at this size, so switching to the Channels view needs no new decoding.
TILE_SIZE = 360
BACKGROUND_PERCENTILE, HIGH_PERCENTILE = 10.0, 99.8

_WELL = re.compile(r"^([A-P])(\d{1,2})$")
_PLATE = re.compile(r"^[A-Za-z0-9-]{3,40}$")
_PREFIX = re.compile(r"<Prefix>([^<]+)</Prefix>")


def _malloc_trim() -> None:
    """Hand freed heap memory back to the OS (glibc only).

    Decoding a field allocates and frees tens of MB; without this, glibc keeps the freed pages
    and a long-running process's memory only ever ratchets up.
    """
    if not sys.platform.startswith("linux"):
        return
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except (OSError, AttributeError):
        pass


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


def scale_full(image: np.ndarray, low: float, high: float) -> np.ndarray:
    """One channel mapped to 0-1 over its display range, at full resolution.

    Works in place on a float32 copy, so a full-resolution field costs one extra array.
    """
    scaled = image.astype(np.float32)  # always a copy; the caller's array is untouched
    scaled -= low
    scaled /= high - low
    np.clip(scaled, 0.0, 1.0, out=scaled)
    return scaled


def downsample(scaled: np.ndarray, size: int) -> np.ndarray:
    if scaled.shape[0] == size:
        return scaled
    return np.asarray(Image.fromarray(scaled).resize((size, size), Image.Resampling.BOX), dtype=np.float32)


def scale_channel(image: np.ndarray, low: float, high: float, size: int) -> np.ndarray:
    """One channel mapped to 0-1 over its display range and downsampled to ``size``."""
    return downsample(scale_full(image, low, high), size)


def gray_tile(scaled: np.ndarray) -> np.ndarray:
    """8-bit grayscale of a scaled channel: exactly the pixels a grayscale render encodes."""
    return (np.clip(scaled, 0.0, 1.0) * 255).astype(np.uint8)


def add_channel(rgb: np.ndarray | None, scaled: np.ndarray, color: tuple[float, float, float]) -> np.ndarray:
    """Blend one scaled channel additively into the RGB image (created on first use)."""
    if rgb is None:
        rgb = np.zeros((*scaled.shape, 3), dtype=np.float32)
    for k, weight in enumerate(np.asarray(color, dtype=np.float32)):
        rgb[..., k] += scaled * weight
    return rgb


def png_bytes(pixels: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(pixels).save(buffer, format="PNG", compress_level=6)
    return buffer.getvalue()


def encode_png(rgb: np.ndarray | None) -> bytes:
    if rgb is None:
        raise InvalidQueryError("No channels selected.")
    np.clip(rgb, 0.0, 1.0, out=rgb)
    rgb *= 255
    return png_bytes(rgb.astype(np.uint8))


def encode_gray_tile(tile: np.ndarray) -> bytes:
    """PNG of a cached grayscale tile, identical to rendering that channel in grayscale."""
    return png_bytes(np.repeat(tile[..., None], 3, axis=2))


def render_png(
    images: dict[str, np.ndarray],
    limits: dict[str, tuple[float, float]],
    size: int,
    grayscale: bool = False,
) -> bytes:
    """Scale each channel to its display range, downsample, and blend additively into a PNG."""
    rgb: np.ndarray | None = None
    for channel, image in images.items():
        color = (1.0, 1.0, 1.0) if grayscale else CHANNEL_COLORS[channel]
        rgb = add_channel(rgb, scale_channel(image, *limits[channel], size), color)
    return encode_png(rgb)


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
        self._tiles: OrderedDict[tuple, np.ndarray] = OrderedDict()
        self._pool = ThreadPoolExecutor(max_workers=6, thread_name_prefix="cell-images")
        # Decoding and scaling a field takes ~15 MB per render; a page of comparisons asks
        # for many fields at once, so cap how many are processed together (downloads still
        # run in parallel). Keeps a 512 MB host from running out of memory.
        self._render_slots = threading.BoundedSemaphore(settings.cell_image_render_concurrency)
        self._disk_lock = threading.Lock()
        self._disk_bytes: int | None = None  # running total of cached TIFFs, scanned on first use

    @property
    def enabled(self) -> bool:
        return self._settings.cell_images_enabled

    # -- remote access -------------------------------------------------------------------
    def _fetch(self, url: str, attempts: int = 3) -> bytes:
        """GET from the public gallery, retrying transient failures (S3 5xx such as "Slow Down",
        timeouts, dropped connections) with a short backoff. Missing objects fail at once."""
        for attempt in range(1, attempts + 1):
            try:
                with urllib.request.urlopen(url, timeout=self._settings.cell_image_timeout_s) as response:  # noqa: S310
                    return response.read()
            except urllib.error.HTTPError as exc:
                if exc.code in (403, 404):
                    raise NotFoundError(f"Image not found in the Cell Painting Gallery ({exc.code}).") from exc
                if attempt == attempts or exc.code < 500:
                    raise ImagesUnavailableError(f"Cell Painting Gallery returned HTTP {exc.code}.") from exc
                logger.warning("Gallery returned HTTP %s for %s; retrying", exc.code, url)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                if attempt == attempts:
                    raise ImagesUnavailableError(
                        "Could not reach the Cell Painting Gallery to fetch images. Check the internet connection.",
                        details={"reason": str(getattr(exc, "reason", exc))},
                    ) from exc
                logger.warning("Gallery fetch failed for %s (%s); retrying", url, exc)
            time.sleep(0.5 * attempt)
        raise AssertionError("unreachable")

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
            self._touch(path)
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
        self._account(len(data))
        return path

    # -- disk cache ----------------------------------------------------------------------
    def _touch(self, path: Path) -> None:
        """Mark a cached file as recently used (its mtime orders eviction)."""
        if self._settings.cell_image_cache_mb:
            try:
                os.utime(path)
            except OSError:
                pass

    def _cached_files(self) -> list[tuple[float, int, Path]]:
        files = []
        for path in self._root.glob("*/*.tiff"):
            try:
                stat = path.stat()
            except OSError:
                continue
            files.append((stat.st_mtime, stat.st_size, path))
        return files

    def _account(self, added: int) -> None:
        """Keep the TIFF cache under CELL_IMAGE_CACHE_MB by removing the least recently used files."""
        cap = self._settings.cell_image_cache_mb * 2**20
        if cap <= 0:
            return
        with self._disk_lock:
            if self._disk_bytes is None:
                self._disk_bytes = sum(size for _, size, _ in self._cached_files())
            else:
                self._disk_bytes += added
            if self._disk_bytes <= cap:
                return
            files = sorted(self._cached_files())
            total = sum(size for _, size, _ in files)
            for _, size, path in files:
                if total <= cap * 0.8:  # trim to 80% so this does not run on every download
                    break
                try:
                    path.unlink()
                    total -= size
                except OSError:
                    pass
            self._disk_bytes = total

    def read(self, plate: str, well: str, field: int, channel: str) -> np.ndarray:
        path = self.channel_path(plate, well, field, channel)
        try:
            try:
                handle = Image.open(path)
            except FileNotFoundError:  # evicted from the disk cache in the meantime: fetch again
                handle = Image.open(self.channel_path(plate, well, field, channel))
            with handle as image:
                return np.asarray(image, dtype=np.float32)
        except OSError as exc:
            path.unlink(missing_ok=True)  # corrupt download; refetch next time
            raise ImagesUnavailableError(f"Could not decode {path.name}; it will be refetched.") from exc

    # -- rendering -----------------------------------------------------------------------
    def limits(
        self, plate: str, well: str, field: int, channel: str, image: np.ndarray | None = None
    ) -> tuple[float, float]:
        """Contrast limits of one channel (cached); ``image`` avoids decoding the file again."""
        key = (plate, well, field, channel)
        with self._lock:
            if key in self._limits:
                return self._limits[key]
        value = contrast_limits(image if image is not None else self.read(plate, well, field, channel))
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
            tile = None
            if grayscale and size == TILE_SIZE:
                tile = self._tiles.get((plate, well, field, channels[0], reference))
        if tile is not None:  # Channels view after the composite: no download or decoding
            png = encode_gray_tile(tile)
            self._remember(key, png)
            return png

        # Fetch everything needed in parallel (first view of a well downloads its channels).
        jobs = [(plate, well, field, c) for c in channels]
        if reference != well:
            jobs += [(plate, reference, field, c) for c in channels]
        list(self._pool.map(lambda job: self.channel_path(*job), jobs))

        with self._render_slots:
            # One channel at a time, so only one full-resolution field is held per render.
            rgb: np.ndarray | None = None
            for c in channels:
                reference_limits = self.limits(plate, reference, field, c)
                image = self.read(plate, well, field, c)
                low, high = display_range(self.limits(plate, well, field, c, image), reference_limits)
                color = (1.0, 1.0, 1.0) if grayscale else CHANNEL_COLORS[c]
                full = scale_full(image, low, high)
                del image
                scaled = downsample(full, size)
                rgb = add_channel(rgb, scaled, color)
                if not grayscale:
                    self._keep_tile((plate, well, field, c, reference), gray_tile(downsample(full, TILE_SIZE)))
                del full, scaled
            png = encode_png(rgb)
            del rgb
        _malloc_trim()
        self._remember(key, png)
        return png

    def _remember(self, key: tuple, png: bytes) -> None:
        with self._lock:
            self._rendered[key] = png
            self._rendered.move_to_end(key)
            while len(self._rendered) > self._settings.cell_image_render_cache:
                self._rendered.popitem(last=False)

    def _keep_tile(self, key: tuple, tile: np.ndarray) -> None:
        with self._lock:
            self._tiles[key] = tile
            self._tiles.move_to_end(key)
            while len(self._tiles) > self._settings.cell_image_tile_cache:
                self._tiles.popitem(last=False)


@lru_cache
def get_cell_image_source() -> CellImageSource:
    return CellImageSource(get_settings())
