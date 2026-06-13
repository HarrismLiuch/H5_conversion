"""Smoke/regression tests for the H5 conversion engine.

Run with `uv run python smoke_test.py` or `.venv/bin/python smoke_test.py`
from the project root.
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

from h5conv.core import (
    DEFAULT_DEAD_PIXELS,
    ConvertConfig,
    convert_directory,
    parse_dead_pixels,
)


def make_synthetic_dataset(
    h5_path: Path,
    n_frames: int = 3,
    key: str = "entry/data/data_000001",
) -> None:
    rng = np.random.default_rng(seed=42)
    if n_frames == 1:
        data = rng.integers(0, 50000, size=(512, 512), dtype=np.uint32)
        data[164, 87] = 0
        data[254:258, :] = (data[254:258, :] * 0.9).astype(np.uint32)
    else:
        data = rng.integers(0, 50000, size=(n_frames, 512, 512), dtype=np.uint32)
        data[:, 164, 87] = 0
        data[:, 254:258, :] = (data[:, 254:258, :] * 0.9).astype(np.uint32)
    with h5py.File(h5_path, "w") as f:
        f.create_dataset(key, data=data)


def assert_raises_value_error(text: str) -> None:
    try:
        parse_dead_pixels(text)
    except ValueError:
        return
    raise AssertionError(f"Expected ValueError for {text!r}")


def test_dead_pixel_parser() -> None:
    assert parse_dead_pixels("") == DEFAULT_DEAD_PIXELS
    assert parse_dead_pixels("164,87; 192,85") == ((164, 87), (192, 85))
    assert parse_dead_pixels("164,87 192,85") == ((164, 87), (192, 85))
    assert parse_dead_pixels("164,87\n192,85") == ((164, 87), (192, 85))
    assert parse_dead_pixels("0,0; 999,999") == ((0, 0), (999, 999))
    assert_raises_value_error("164")
    assert_raises_value_error("164,87,broken")
    print("OK: dead-pixel parser accepts defaults and rejects malformed text.")


def test_stack_conversion(tmp: Path) -> None:
    in_dir = tmp / "stack_in"
    out_dir = tmp / "stack_out"
    in_dir.mkdir()

    make_synthetic_dataset(in_dir / "smoke_master.h5", n_frames=3)
    (in_dir / "noise_other.h5").write_bytes(b"x")

    flatfield = np.ones((512, 512), dtype=np.float32)
    flatfield[254:258, :] = 1.0 / 0.9
    flatfield[:, 254:258] = 1.0 / 0.9

    config = ConvertConfig(
        input_dir=in_dir,
        output_dir=out_dir,
        flatfield=flatfield,
        dead_pixels=((0, 0), (999, 999), *DEFAULT_DEAD_PIXELS),
        fix_dead_pixels=True,
        save_npy=True,
        save_tiff=True,
        save_tif=True,
        cmap="gray",
        min_percentile=1.0,
        max_percentile=99.0,
    )

    progress = []
    stats = convert_directory(
        config,
        progress=lambda i, n, msg: progress.append((i, n, msg)),
        is_cancelled=lambda: False,
    )

    assert stats.files_total == 1, stats
    assert stats.files_done == 1, stats
    assert stats.frames_done == 3, stats
    assert stats.frames_skipped == 0, stats
    assert stats.outputs_written == 9, stats
    assert stats.outputs_skipped == 0, stats
    assert not stats.cancelled, stats
    assert not stats.errors, stats

    expected = ["smoke_master_0000", "smoke_master_0001", "smoke_master_0002"]
    for stem in expected:
        for ext in (".npy", ".tiff", ".tif"):
            p = out_dir / f"{stem}{ext}"
            assert p.exists(), f"missing {p}"

    raw = np.load(out_dir / "smoke_master_0000.npy")
    assert raw.shape == (512, 512)
    assert raw.dtype == np.float32, raw.dtype
    assert raw[164, 87] > 0, "dead pixel was not fixed"

    display = tifffile.imread(out_dir / "smoke_master_0000.tif")
    assert display.shape == (512, 512, 3), display.shape
    assert display.dtype == np.uint8

    archive = tifffile.imread(out_dir / "smoke_master_0000.tiff")
    assert archive.dtype == np.float32, archive.dtype

    assert all(call[1] == 3 for call in progress), progress
    assert [call[0] for call in progress] == [1, 2, 3], progress
    print("OK: stack conversion writes float32/raw display outputs and progress.")


def test_single_frame_no_flatfield(tmp: Path) -> None:
    in_dir = tmp / "single_in"
    out_dir = tmp / "single_out"
    in_dir.mkdir()
    make_synthetic_dataset(in_dir / "single_master.h5", n_frames=1)

    progress = []
    stats = convert_directory(
        ConvertConfig(
            input_dir=in_dir,
            output_dir=out_dir,
            flatfield=None,
            save_npy=True,
            save_tiff=True,
            save_tif=False,
        ),
        progress=lambda i, n, msg: progress.append((i, n, msg)),
    )

    assert stats.files_total == 1, stats
    assert stats.files_done == 1, stats
    assert stats.frames_done == 1, stats
    assert stats.outputs_written == 2, stats
    assert progress == [(1, 1, "single_master.h5")], progress
    assert np.load(out_dir / "single_master.npy").dtype == np.float32
    assert tifffile.imread(out_dir / "single_master.tiff").dtype == np.float32
    print("OK: single-frame no-flatfield conversion stays float32.")


def test_dataset_key_and_keyword(tmp: Path) -> None:
    in_dir = tmp / "dataset_in"
    out_dir = tmp / "dataset_out"
    in_dir.mkdir()
    make_synthetic_dataset(
        in_dir / "custom_sample.h5",
        n_frames=1,
        key="entry/data/custom",
    )

    stats = convert_directory(
        ConvertConfig(
            input_dir=in_dir,
            output_dir=out_dir,
            dataset_key="entry/data/custom",
            file_keyword="sample",
            save_npy=True,
            save_tiff=False,
            save_tif=False,
        )
    )
    assert stats.files_total == 1, stats
    assert (out_dir / "custom_sample.npy").exists()

    fallback_out = tmp / "fallback_out"
    stats = convert_directory(
        ConvertConfig(
            input_dir=in_dir,
            output_dir=fallback_out,
            dataset_key="entry/data/missing",
            file_keyword="sample",
            save_npy=True,
            save_tiff=False,
            save_tif=False,
        )
    )
    assert stats.files_total == 1, stats
    assert stats.files_done == 1, stats
    assert (fallback_out / "custom_sample.npy").exists()
    print("OK: custom dataset key and fallback dataset resolution work.")


def test_skip_existing(tmp: Path) -> None:
    in_dir = tmp / "skip_in"
    out_dir = tmp / "skip_out"
    in_dir.mkdir()
    make_synthetic_dataset(in_dir / "skip_master.h5", n_frames=1)

    base_config = ConvertConfig(
        input_dir=in_dir,
        output_dir=out_dir,
        save_npy=True,
        save_tiff=False,
        save_tif=False,
    )
    first = convert_directory(base_config)
    assert first.frames_done == 1, first
    assert first.outputs_written == 1, first

    second = convert_directory(
        ConvertConfig(
            input_dir=in_dir,
            output_dir=out_dir,
            save_npy=True,
            save_tiff=False,
            save_tif=False,
            overwrite_existing=False,
        )
    )
    assert second.frames_done == 0, second
    assert second.frames_skipped == 1, second
    assert second.outputs_written == 0, second
    assert second.outputs_skipped == 1, second
    print("OK: overwrite_existing=False skips existing selected outputs.")


def test_cancellation_mid_stack(tmp: Path) -> None:
    in_dir = tmp / "cancel_in"
    out_dir = tmp / "cancel_out"
    in_dir.mkdir()
    make_synthetic_dataset(in_dir / "cancel_master.h5", n_frames=3)

    progress = []

    def is_cancelled() -> bool:
        return len(progress) >= 1

    stats = convert_directory(
        ConvertConfig(
            input_dir=in_dir,
            output_dir=out_dir,
            save_npy=True,
            save_tiff=False,
            save_tif=False,
        ),
        progress=lambda i, n, msg: progress.append((i, n, msg)),
        is_cancelled=is_cancelled,
    )
    assert stats.cancelled, stats
    assert stats.files_done == 0, stats
    assert stats.frames_done == 1, stats
    assert stats.outputs_written == 1, stats
    assert len(progress) == 1, progress
    print("OK: cancellation does not count partial files as complete.")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="h5conv_smoke_"))
    try:
        test_dead_pixel_parser()
        test_stack_conversion(tmp)
        test_single_frame_no_flatfield(tmp)
        test_dataset_key_and_keyword(tmp)
        test_skip_existing(tmp)
        test_cancellation_mid_stack(tmp)
        print("OK: all smoke/regression checks passed.")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
