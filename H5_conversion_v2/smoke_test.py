"""Smoke test: build a synthetic H5 file, run convert_directory, verify outputs.

Run with `uv run python smoke_test.py` from the project root.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import h5py
import hdf5plugin  # noqa: F401  -- registers the EIGER-compatible filters
import numpy as np
import tifffile

from h5conv.core import ConvertConfig, convert_directory


def make_synthetic_dataset(h5_path: Path, n_frames: int = 3) -> None:
    rng = np.random.default_rng(seed=42)
    # Shape: (N, 512, 512) like the EIGER insitu stack format
    data = rng.integers(0, 50000, size=(n_frames, 512, 512), dtype=np.uint32)
    # Plant a dead pixel at the known location
    data[:, 164, 87] = 0
    # Plant a crosshair-like band that the flatfield should correct
    data[:, 254:258, :] = (data[:, 254:258, :] * 0.9).astype(np.uint32)
    with h5py.File(h5_path, "w") as f:
        f.create_dataset("entry/data/data_000001", data=data)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="h5conv_smoke_"))
    try:
        in_dir = tmp / "in"
        out_dir = tmp / "out"
        in_dir.mkdir()

        # Master file the GUI will pick up
        h5_path = in_dir / "smoke_master.h5"
        make_synthetic_dataset(h5_path, n_frames=3)

        # Noise file that should be ignored
        (in_dir / "noise_other.h5").write_bytes(b"x")

        # Fake flatfield: 1.0 everywhere except 1.11 on the crosshair band
        flatfield = np.ones((512, 512), dtype=np.float32)
        flatfield[254:258, :] = 1.0 / 0.9
        flatfield[:, 254:258] = 1.0 / 0.9
        flatfield_path = tmp / "flat.tif"
        tifffile.imwrite(flatfield_path, flatfield)

        # Run the conversion
        config = ConvertConfig(
            input_dir=in_dir,
            output_dir=out_dir,
            flatfield=flatfield,
            fix_dead_pixels=True,
            save_npy=True,
            save_tiff=True,
            save_tif=True,
            cmap="gray",
            min_percentile=1.0,
            max_percentile=99.0,
        )

        progress = []
        def prog(i, n, msg):
            progress.append((i, n, msg))
        stats = convert_directory(config, progress=prog, is_cancelled=lambda: False)

        # ----- assertions -----
        assert stats.files_total == 1, stats
        assert stats.files_done == 1, stats
        assert stats.frames_done == 3, stats
        assert not stats.cancelled, stats
        assert not stats.errors, stats

        expected = ["smoke_master_0000", "smoke_master_0001", "smoke_master_0002"]
        for stem in expected:
            for ext in (".npy", ".tiff", ".tif"):
                p = out_dir / f"{stem}{ext}"
                assert p.exists(), f"missing {p}"

        # Sanity: raw .npy was multiplied by the flatfield (crosshair band
        # should now have ~uniform stats with its neighbors).
        raw = np.load(out_dir / "smoke_master_0000.npy")
        assert raw.shape == (512, 512)
        assert raw[164, 87] > 0, "dead pixel was not fixed"

        # 8-bit .tif was percentile-clipped and colormapped → (512, 512, 3)
        display = tifffile.imread(out_dir / "smoke_master_0000.tif")
        assert display.shape == (512, 512, 3), display.shape
        assert display.dtype == np.uint8

        # Raw archive .tiff is float32
        archive = tifffile.imread(out_dir / "smoke_master_0000.tiff")
        assert archive.dtype == np.float32, archive.dtype

        print("OK: conversion produced the expected outputs.")
        print(f"frames_written={stats.frames_done} progress_calls={len(progress)}")
        print(f"sample progress: {progress[:2]}")

        # New contract: progress callback receives (completed, total, msg)
        # where `total` is the sum of all stack frames across all files, so
        # the GUI can drive a real percentage bar.
        assert all(call[1] == 3 for call in progress), (
            f"progress `total` should be 3 (sum of stack frames), got {progress}"
        )
        assert [call[0] for call in progress] == [1, 2, 3], progress
        print("OK: progress contract is (completed, total=3, message).")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
