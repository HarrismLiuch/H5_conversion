# H5 Conversion GUI (v2)

A cross-platform GUI for converting DECTRIS EIGER `.h5` detector files into
`.npy`, `.tiff`, and `.tif` outputs. Works on macOS and Windows by
double-clicking a single launcher file — no system Python required.

## What it does

For every `*master*.h5` in the input folder:

1. Loads the `entry/data/data_000001` dataset (single frame or 3-D stack).
2. **Optionally multiplies by a flatfield** (a 512×512 `.npy` / `.tif` you
   supply). This is the only whole-image correction; there is no
   hardcoded crosshair division any more.
3. **Optionally fixes the two known dead pixels** (164, 87) and (192, 85)
   by replacing each with the mean of its 4-neighborhood. The list is
   editable in the GUI.
4. Writes three outputs side by side (any subset is selectable):
   - `.npy` — raw `float32` array
   - `.tiff` — raw `float32` TIFF archive
   - `.tif` — 8-bit, percentile-clipped, colormapped display image
5. Auto-detects 3-D stacks and saves one output set per frame.

## Running

### macOS / Linux
Double-click **`launch_mac.command`**. macOS auto-runs `.command` files in
Terminal, so no "Open With" prompt will appear.

If you would rather run it from a terminal:
```bash
cd /Users/chuhang/Documents/GitHub/H5_conversion/H5_conversion_v2
./launch_mac.command          # or: ./launch_mac.sh
```

The first run will:
1. Install [`uv`](https://docs.astral.sh/uv/) (the Python package manager) into `~/.local/bin` if it is not already on `PATH`.
2. Create a local `.venv` and install every dependency.
3. Open the GUI.

> If the Terminal window disappears immediately on double-click, macOS
> Gatekeeper may have quarantined the file. From a terminal run:
> `xattr -dr com.apple.quarantine /Users/chuhang/Documents/GitHub/H5_conversion/H5_conversion_v2`

### Windows
Double-click `launch_windows.bat`.

First run will:
1. Install `uv` into `%USERPROFILE%\.local\bin` if it is not on `PATH`.
2. Create the `.venv` and install dependencies.
3. Open the GUI.

> Closing the terminal window will quit the GUI. The `.bat` keeps the window
> open on error so the message stays visible.

## Manual run (for development)

```bash
uv sync
uv run python run.py
```

## Project layout

```
H5_conversion_v2/
├── launch_mac.sh            # macOS / Linux double-click launcher
├── launch_windows.bat       # Windows double-click launcher
├── run.py                   # entry point
├── pyproject.toml
├── src/h5conv/
│   ├── __init__.py
│   ├── core.py              # Qt-free conversion engine
│   └── gui.py               # PySide6 window
└── .venv/                   # created on first run
```

## Dependencies

- PySide6 (LGPL Qt for Python)
- numpy, h5py, hdf5plugin (DECTRIS bit-shuffle / LZ4 filters)
- tifffile, matplotlib (image I/O + colormap)
