"""Pure-Python conversion engine.

Reads DECTRIS EIGER `.h5` files (single frame or 3-D stack), optionally
multiplies by a flatfield, fixes two known dead pixels, optionally clips to a
percentile window, and writes `.npy` (raw float32), `.tiff` (raw float32), and
`.tif` (percentile-clipped 8-bit display) outputs.

The module is intentionally Qt-free. Progress and cancellation go through two
small Protocols so the GUI layer can hook in without polluting the engine.
"""

from __future__ import annotations

import glob
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Protocol

import h5py
import hdf5plugin  # noqa: F401  -- registers EIGER bit-shuffle/LZ4 filters
import numpy as np
import tifffile

# ---------------------------------------------------------------------------
# Defaults that match the detector used in the original notebooks
# ---------------------------------------------------------------------------

DETECTOR_SHAPE = (512, 512)

# Hardcoded dead-pixel positions from the existing notebooks
# (row, col) pairs. Each is replaced by the mean of its 4-neighborhood.
DEFAULT_DEAD_PIXELS: tuple[tuple[int, int], ...] = ((164, 87), (192, 85))

# DECTRIS EIGER writes the master file's first frame under this key.
DEFAULT_DATASET_KEY = "entry/data/data_000001"


# ---------------------------------------------------------------------------
# Callbacks (Qt-free protocols so the GUI can implement them)
# ---------------------------------------------------------------------------


class ProgressCallback(Protocol):
    """Receives per-frame updates: (frame_index, total_frames, message)."""

    def __call__(self, frame_index: int, total_frames: int, message: str) -> None: ...


class CancelCheck(Protocol):
    """Return True to request that the conversion stops at the next frame."""

    def __call__(self) -> bool: ...


# ---------------------------------------------------------------------------
# Configuration object (lives in core so it's also usable from a CLI later)
# ---------------------------------------------------------------------------


@dataclass
class ConvertConfig:
    input_dir: Path
    output_dir: Path
    flatfield: np.ndarray | None = None
    dead_pixels: tuple[tuple[int, int], ...] = DEFAULT_DEAD_PIXELS
    fix_dead_pixels: bool = True
    save_npy: bool = True
    save_tiff: bool = True  # raw float32 archive
    save_tif: bool = True   # percentile-clipped 8-bit display
    cmap: str = "gray"
    min_percentile: float = 1.0
    max_percentile: float = 99.0
    dataset_key: str = DEFAULT_DATASET_KEY
    file_keyword: str = "master"  # only convert files whose name contains this


@dataclass
class ConvertStats:
    files_total: int = 0
    files_done: int = 0
    frames_done: int = 0
    cancelled: bool = False
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def discover_h5_files(input_dir: Path, keyword: str) -> list[Path]:
    """Return `.h5` files in `input_dir` whose stem contains `keyword`."""
    return sorted(p for p in input_dir.glob("*.h5") if keyword in p.stem)


def load_flatfield(path: Path) -> np.ndarray:
    """Load a flatfield array from `.npy` or `.tif/.tiff`.

    Always returned as float32.
    """
    suffix = path.suffix.lower()
    if suffix == ".npy":
        arr = np.load(path)
    elif suffix in (".tif", ".tiff"):
        arr = tifffile.imread(path)
    else:  # pragma: no cover - guarded by the GUI's file dialog filter
        raise ValueError(f"Unsupported flatfield format: {suffix}")
    arr = np.asarray(arr, dtype=np.float32)
    if arr.shape != DETECTOR_SHAPE:
        raise ValueError(
            f"Flatfield must be {DETECTOR_SHAPE}, got {arr.shape} (from {path})"
        )
    return arr


def _read_frame(f: h5py.File, key: str) -> np.ndarray:
    """Read one frame. The EIGER layout is usually (1, 512, 512); squeeze to 2-D."""
    if key not in f:
        # Fall back to the first dataset under entry/data
        try:
            entries = sorted(f["entry/data"].keys())
            if not entries:
                raise KeyError(key)
            key = f"entry/data/{entries[0]}"
        except KeyError as exc:
            raise KeyError(f"No dataset matching {key!r} and none under entry/data") from exc
    raw = np.asarray(f[key])
    if raw.ndim == 3 and raw.shape[0] == 1:
        raw = raw[0]
    if raw.ndim != 2 or raw.shape != DETECTOR_SHAPE:
        raise ValueError(
            f"Unexpected frame shape {raw.shape}; expected {DETECTOR_SHAPE}"
        )
    return raw


def _fix_dead_pixels(frame: np.ndarray, positions: Iterable[tuple[int, int]]) -> None:
    """In-place 4-neighbor replacement for known dead pixels."""
    h, w = frame.shape
    for r, c in positions:
        if not (0 <= r < h and 0 <= c < w):
            continue
        frame[r, c] = (
            frame[r - 1, c] + frame[r + 1, c] + frame[r, c - 1] + frame[r, c + 1]
        ) / 4.0


def _apply_flatfield(frame: np.ndarray, flatfield: np.ndarray | None) -> np.ndarray:
    """Multiply by flatfield (user-chosen convention from the v3 Quadro notebooks)."""
    if flatfield is None:
        return frame
    out = frame.astype(np.float32, copy=False) * flatfield
    return out.astype(np.float32)


def _percentile_clip(
    frame: np.ndarray, lo: float, hi: float
) -> np.ndarray:
    """Clip to [percentile(lo), percentile(hi)] and rescale to 8-bit."""
    lo_v = float(np.percentile(frame, lo))
    hi_v = float(np.percentile(frame, hi))
    if hi_v <= lo_v:
        hi_v = lo_v + 1.0
    clipped = np.clip(frame, lo_v, hi_v)
    scaled = (clipped - lo_v) * (255.0 / (hi_v - lo_v))
    return scaled.astype(np.uint8)


# ---------------------------------------------------------------------------
# Colormap handling: PySide6 GUI has no Qt for headless testing, but
# matplotlib is a hard dep and provides everything we need for 8-bit .tif.
# ---------------------------------------------------------------------------


def _apply_cmap(frame_u8: np.ndarray, cmap: str) -> np.ndarray:
    """Map a (H, W) uint8 array through a matplotlib colormap → (H, W, 4) uint8."""
    import matplotlib.cm as cm
    import matplotlib.pyplot as plt

    cmap_obj = cm.get_cmap(cmap) if cmap in plt.colormaps() else cm.get_cmap("gray")
    rgba = cmap_obj(frame_u8 / 255.0)
    # Drop alpha for TIFF compatibility
    return (rgba[..., :3] * 255.0).astype(np.uint8)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def convert_directory(
    config: ConvertConfig,
    progress: ProgressCallback | None = None,
    is_cancelled: CancelCheck | None = None,
) -> ConvertStats:
    """Convert every master `.h5` file in `config.input_dir`.

    A file is treated as a 3-D stack when its first dataset has shape
    (N, 512, 512); in that case all N frames are saved (matches the
    `H5_conversion_Quadro_insitu_v3` workflow).
    """
    config.output_dir.mkdir(parents=True, exist_ok=True)

    files = discover_h5_files(config.input_dir, config.file_keyword)
    stats = ConvertStats(files_total=len(files))

    if not files:
        return stats

    # Sanity-check the flatfield shape up front so we fail fast.
    if config.flatfield is not None and config.flatfield.shape != DETECTOR_SHAPE:
        raise ValueError(
            f"Flatfield shape {config.flatfield.shape} != {DETECTOR_SHAPE}"
        )

    # Pre-scan: open each file once to learn its frame count, so the UI can
    # show a real percentage instead of an indeterminate "marquee" bar.
    file_frame_counts: list[int] = []
    for h5_path in files:
        try:
            with h5py.File(h5_path, "r") as f:
                try:
                    raw = np.asarray(f[config.dataset_key])
                except KeyError:
                    raw = np.asarray(
                        f[f"entry/data/{sorted(f['entry/data'].keys())[0]}"]
                    )
                if raw.ndim == 2:
                    file_frame_counts.append(1)
                elif raw.ndim == 3 and raw.shape[1:] == DETECTOR_SHAPE:
                    file_frame_counts.append(raw.shape[0])
                else:
                    raise ValueError(
                        f"Unexpected dataset shape {raw.shape} in {h5_path.name}"
                    )
        except Exception as exc:  # noqa: BLE001
            stats.errors.append(f"{h5_path.name}: {exc}")
            file_frame_counts.append(0)

    total_frames = sum(file_frame_counts)
    completed_frames = 0

    for file_idx, h5_path in enumerate(files):
        if is_cancelled and is_cancelled():
            stats.cancelled = True
            break

        if file_frame_counts[file_idx] == 0:
            # Pre-scan failed for this file; skip.
            continue

        try:
            with h5py.File(h5_path, "r") as f:
                try:
                    raw = np.asarray(f[config.dataset_key])
                except KeyError:
                    raw = np.asarray(f[f"entry/data/{sorted(f['entry/data'].keys())[0]}"])

                if raw.ndim == 2:
                    frames = [raw]
                else:
                    frames = [raw[i] for i in range(raw.shape[0])]

                total = len(frames)
                stem = h5_path.stem  # e.g. '30cm_001_master'

                for frame_idx, frame in enumerate(frames):
                    if is_cancelled and is_cancelled():
                        stats.cancelled = True
                        break

                    processed = _apply_flatfield(frame, config.flatfield)
                    if config.fix_dead_pixels:
                        _fix_dead_pixels(processed, config.dead_pixels)

                    if total == 1:
                        out_stem = stem
                        msg = f"{h5_path.name}"
                    else:
                        out_stem = f"{stem}_{frame_idx:04d}"
                        msg = f"{h5_path.name}  frame {frame_idx + 1}/{total}"

                    if config.save_npy:
                        np.save(config.output_dir / f"{out_stem}.npy", processed)
                    if config.save_tiff:
                        tifffile.imwrite(
                            config.output_dir / f"{out_stem}.tiff", processed
                        )
                    if config.save_tif:
                        u8 = _percentile_clip(
                            processed, config.min_percentile, config.max_percentile
                        )
                        rgb = _apply_cmap(u8, config.cmap)
                        tifffile.imwrite(
                            config.output_dir / f"{out_stem}.tif", rgb
                        )

                    stats.frames_done += 1
                    completed_frames += 1
                    if progress:
                        progress(completed_frames, total_frames, msg)
        except Exception as exc:  # noqa: BLE001 - report and continue
            stats.errors.append(f"{h5_path.name}: {exc}")
        else:
            stats.files_done += 1

    return stats
