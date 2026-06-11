@echo off
REM Double-clickable launcher for the H5 conversion GUI on Windows.
REM - Finds an existing `uv` install (no need to re-run the installer each time).
REM - Runs `uv sync` to create/update the .venv.
REM - Opens the GUI. The window always stays open at the end so you can
REM   read the result, even on success.

setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

REM ---------------------------------------------------------------
REM 1. Locate `uv`. The installer drops the binary at
REM    %USERPROFILE%\.local\bin\uv.exe but the system PATH update
REM    from the installer often does not take effect for the
REM    current CMD session, so we check the common install paths
REM    first and add it to PATH ourselves.
REM ---------------------------------------------------------------
set "UV_EXE="
for %%P in ("%USERPROFILE%\.local\bin\uv.exe", "%LOCALAPPDATA%\uv\uv.exe", "uv.exe") do (
    if not defined UV_EXE if exist "%%~P" set "UV_EXE=%%~P"
)
if not defined UV_EXE (
    echo.
    echo uv was not found on this system. Installing it now (one-time)...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    if exist "%USERPROFILE%\.local\bin\uv.exe" set "UV_EXE=%USERPROFILE%\.local\bin\uv.exe"
)
if not defined UV_EXE (
    echo.
    echo ERROR: uv is still not installed. Please open PowerShell and run:
    echo     irm https://astral.sh/uv/install.ps1 ^| iex
    echo Then double-click launch_windows.bat again.
    echo.
    pause
    exit /b 1
)
REM Make sure the directory holding uv is on PATH for the rest of this script.
for %%I in ("%UV_EXE%") do set "PATH=%%~dpI;%PATH%"

REM ---------------------------------------------------------------
REM 2. Sync the venv.
REM ---------------------------------------------------------------
echo.
echo Syncing dependencies (first run may take a minute)...
"%UV_EXE%" sync
if errorlevel 1 (
    echo.
    echo uv sync failed with error %errorlevel%.
    echo Check the messages above. Common causes:
    echo   - No internet connection
    echo   - Antivirus blocking the package download
    echo   - The .venv directory is locked by another process
    echo.
    pause
    exit /b 1
)

REM ---------------------------------------------------------------
REM 3. Run the GUI.
REM ---------------------------------------------------------------
echo.
echo ===============================================================
echo   Starting the GUI. Close the GUI window to return here.
echo ===============================================================
echo.
"%UV_EXE%" run python run.py
set "RC=%errorlevel%"
echo.
if %RC% NEQ 0 (
    echo The GUI exited with code %RC%. See the messages above.
) else (
    echo The GUI closed normally. You can re-run this launcher any time.
)
echo.
echo Press any key to close this window...
pause >nul
exit /b %RC%
