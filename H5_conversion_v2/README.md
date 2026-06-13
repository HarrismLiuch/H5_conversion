# H5 Conversion GUI (v2)

A cross-platform GUI for converting DECTRIS EIGER `.h5` detector files into
`.npy`, `.tiff`, and `.tif` outputs. Works on macOS and Windows by
double-clicking a single launcher file — no system Python required.

## What it does

For every `*master*.h5` in the input folder:

1. Loads the `entry/data/data_000001` dataset (single frame or 3-D stack).
   The Advanced panel can override both the filename keyword and dataset key;
   if the key is missing, the converter falls back to the first dataset under
   `entry/data`.
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
6. Overwrites existing outputs by default, or skips already-existing selected
   outputs when **Overwrite existing outputs** is unchecked.

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
Double-click **`launch_windows.vbs`**.

Why a `.vbs` and not a `.bat`? On managed Windows machines, double-clicking
a `.bat` file uses the *calling Explorer's* console properties. If "Close
on exit" is enabled (it often is, on corporate / school machines), the
console window disappears the moment the script ends — even if it ends
on a `pause`. A `.vbs` file runs through the Windows Script Host, which
spawns a *new* `cmd.exe` process that runs the launcher. That new
process has its own console properties and is not affected by the
"Close on exit" setting, so the window reliably stays visible.

The VBS launcher calls [launcher_inner.bat](launcher_inner.bat),
which does the actual work (locate `uv`, run `uv sync`, launch the GUI).

First run will:
1. Install `uv` into `%USERPROFILE%\.local\bin` if it is not on `PATH`.
2. Create the `.venv` and install dependencies.
3. Open the GUI.

> If double-clicking the `.vbs` does nothing, your antivirus or group
> policy may block VBScript. In that case, open a CMD window manually
> and run `launcher_inner.bat` directly — see "If the window
> disappears" below.

**Log files**: every run of the launcher appends its full output to
`launcher.log` in the project folder, and the diagnostic saves to
`diagnose.log`. So even if the console window does close, you can open
these files in Notepad to see exactly what happened.

**If you see `uv candidate not found`** (or any "uv not found" error):
The launcher searches the standard install paths and the current `PATH`
for `uv.exe`, and if it can't find one, downloads the standalone
binary directly from the [uv GitHub releases](https://github.com/astral-sh/uv/releases)
page (no PowerShell installer, no group-policy surprises). If the
download itself fails (corporate firewall blocking GitHub, no internet,
no `curl` and no PowerShell), the launcher prints a clear error and
pauses — and the full log is in `launcher.log`.

Two manual fallbacks if even the direct download doesn't work:

1. **Install `uv` manually from a PowerShell prompt**:
   ```powershell
   irm https://astral.sh/uv/install.ps1 | iex
   ```
   The installer drops `uv.exe` at `%USERPROFILE%\.local\bin\uv.exe`,
   which the launcher checks first.
2. **Tell the launcher where uv is** by setting an environment variable
   `H5CONV_UV_EXE` to the full path (e.g. `C:\tools\uv\uv.exe`) via
   *System Properties → Environment Variables*. Re-open the CMD window
   and re-run `launch_windows.vbs`.

**If the window disappears with no output** (the original problem):
Open a CMD window manually and run the launcher there. The window
stays attached to your console, so all error messages stay visible:

```cmd
cd C:\path\to\H5_conversion_v2
launcher_inner.bat
```

**Diagnostic tool**: `diagnose_windows.bat` prints where `uv` is on
disk, what `where uv` returns from `PATH`, whether the `.venv` is
built, and what `.h5` files are in the current directory. Output is
saved to `diagnose.log` and the window pauses at the end.

## Manual run (for development)

```bash
uv sync
uv run python run.py
```

## Project layout

```
H5_conversion_v2/
├── launch_mac.sh            # macOS / Linux double-click launcher
├── launch_mac.command       # macOS preferred double-click target
├── launch_windows.vbs       # Windows preferred double-click target
├── launcher_inner.bat       # Windows inner launcher (the real work)
├── diagnose_windows.bat     # Windows diagnostic tool
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
