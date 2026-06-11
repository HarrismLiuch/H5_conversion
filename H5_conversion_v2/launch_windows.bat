@echo off
REM Double-clickable launcher for the H5 conversion GUI on Windows.
REM - First run: installs `uv` and creates the .venv.
REM - Subsequent runs: just opens the GUI.

setlocal
cd /d "%~dp0"

REM 1. Make sure `uv` is on PATH.
where uv >nul 2>nul
if errorlevel 1 (
    echo Installing uv (one-time)...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)

REM 2. Create / update the venv and install deps.
echo Syncing dependencies (this may take a minute on first run)...
uv sync
if errorlevel 1 (
    echo.
    echo uv sync failed. See the messages above.
    pause
    exit /b 1
)

REM 3. Run the GUI.
uv run python run.py
if errorlevel 1 (
    echo.
    echo The GUI exited with an error.
    pause
    exit /b 1
)
endlocal
