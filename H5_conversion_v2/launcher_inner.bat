@echo off
REM Inner launcher: the real work. Most users should run
REM launch_windows.vbs, which spawns this file under cmd /k via the
REM Windows Script Host so the window stays open reliably.
REM
REM This file can also be run directly from a CMD window if you want
REM the output in a console you control.
REM
REM Every line of output is also appended to launcher.log so you can
REM read what happened even if the window does close.

setlocal EnableExtensions EnableDelayedExpansion
set "LOGFILE=%~dp0launcher.log"
echo. > "%LOGFILE%"
echo =============================================================== >> "%LOGFILE%"
echo Inner launcher started at %DATE% %TIME% >> "%LOGFILE%"
echo =============================================================== >> "%LOGFILE%"

echo === H5 Conversion launcher ===
echo Log: %LOGFILE%
echo.

if not defined MPLCONFIGDIR set "MPLCONFIGDIR=%TEMP%\h5conv-matplotlib"
if not exist "%MPLCONFIGDIR%" mkdir "%MPLCONFIGDIR%" >> "%LOGFILE%" 2>&1
echo Matplotlib cache: %MPLCONFIGDIR% >> "%LOGFILE%"

REM ---------------------------------------------------------------
REM 1. Locate `uv`. We check the most common install paths first;
REM    if none of those have it, we install it ourselves with a
REM    direct download from GitHub releases (no PowerShell, no
REM    group-policy surprises).
REM ---------------------------------------------------------------

REM 1a. Search the standard install locations and the user's PATH.
set "UV_EXE="
if defined H5CONV_UV_EXE (
    if exist "%H5CONV_UV_EXE%" (
        set "UV_EXE=%H5CONV_UV_EXE%"
        echo Using H5CONV_UV_EXE: %H5CONV_UV_EXE% >> "%LOGFILE%"
    ) else (
        echo H5CONV_UV_EXE is set but does not exist: %H5CONV_UV_EXE% >> "%LOGFILE%"
    )
)
for %%P in (
    "%USERPROFILE%\.local\bin\uv.exe"
    "%LOCALAPPDATA%\uv\uv.exe"
    "C:\Program Files\uv\uv.exe"
    "C:\Program Files (x86)\uv\uv.exe"
    "C:\ProgramData\chocolatey\bin\uv.exe"
    "C:\tools\uv\uv.exe"
) do (
    if not defined UV_EXE (
        if exist "%%~P" set "UV_EXE=%%~P"
    )
)

REM 1b. If we still have nothing, ask the OS to find it. `where` walks
REM     the current PATH; if it's there but in an unusual dir, we'll
REM     pick it up. If `where` returns nothing, it sets UV_EXE to "".
if not defined UV_EXE (
    for /f "delims=" %%W in ('where uv 2^>nul') do (
        if not defined UV_EXE set "UV_EXE=%%W"
    )
)

REM 1c. If we still have nothing, install uv ourselves by downloading
REM     the standalone binary from GitHub. This bypasses the PowerShell
REM     installer entirely (which is blocked on many managed machines).
if not defined UV_EXE (
    echo uv was not found anywhere on the system. Installing it now...
    echo uv was not found anywhere on the system. Installing it now. >> "%LOGFILE%"

    REM Pick the right arch-specific download URL.
    if /I "%PROCESSOR_ARCHITECTURE%"=="AMD64" (
        set "UV_URL=https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip"
        set "UV_ARCH=msvc"
    ) else if /I "%PROCESSOR_ARCHITECTURE%"=="ARM64" (
        set "UV_URL=https://github.com/astral-sh/uv/releases/latest/download/uv-aarch64-pc-windows-msvc.zip"
        set "UV_ARCH=msvc"
    ) else (
        echo Unsupported architecture: %PROCESSOR_ARCHITECTURE% >> "%LOGFILE%"
        set "UV_URL="
        set "UV_ARCH=unknown"
    )

    if defined UV_URL (
        set "UV_DIR=%USERPROFILE%\.local\bin"
        if not exist "!UV_DIR!" mkdir "!UV_DIR!" >> "%LOGFILE%" 2>&1
        set "UV_ZIP=%TEMP%\uv_install.zip"
        echo Downloading uv from !UV_URL! ... >> "%LOGFILE%"
        REM Try curl first (Windows 10+ ships it); fall back to PowerShell
        REM Invoke-WebRequest for older / stripped-down images.
        curl --version >nul 2>&1
        if not errorlevel 1 (
            curl -fsSL -o "!UV_ZIP!" "!UV_URL!" >> "%LOGFILE%" 2>&1
        ) else (
            echo curl not found, using PowerShell Invoke-WebRequest... >> "%LOGFILE%"
            powershell -NoProfile -Command "Invoke-WebRequest -UseBasicParsing -Uri '!UV_URL!' -OutFile '!UV_ZIP!'" >> "%LOGFILE%" 2>&1
        )
        if errorlevel 1 (
            echo Download failed. See %LOGFILE% for details. >> "%LOGFILE%"
        ) else (
            REM Unzip with PowerShell (no execution policy needed for
            REM Expand-Archive, which is a built-in cmdlet).
            echo Extracting uv... >> "%LOGFILE%"
            powershell -NoProfile -Command "Expand-Archive -Force -Path '!UV_ZIP!' -DestinationPath '!UV_DIR!'" >> "%LOGFILE%" 2>&1
            del "!UV_ZIP!" >nul 2>&1
            if exist "!UV_DIR!\uv.exe" set "UV_EXE=!UV_DIR!\uv.exe"
        )
    )
)

if not defined UV_EXE (
    echo.
    echo ===============================================================
    echo   ERROR: uv could not be found or installed.
    echo ===============================================================
    echo.
    echo I searched the standard install paths and the current PATH,
    echo then tried to download uv from GitHub releases. Both failed.
    echo.
    echo See the full log for details: %LOGFILE%
    echo.
    echo --- Last 40 lines of the log: ---
    powershell -NoProfile -Command "Get-Content '%LOGFILE%' -Tail 40"
    echo.
    echo Press any key to close this window...
    pause >nul
    exit /b 1
)

echo Found uv at: %UV_EXE%
echo Found uv at: %UV_EXE% >> "%LOGFILE%"
"%UV_EXE%" --version >> "%LOGFILE%" 2>&1
for %%I in ("%UV_EXE%") do set "PATH=%%~dpI;%PATH%"

REM ---------------------------------------------------------------
REM 2. Sync the venv.
REM ---------------------------------------------------------------
echo.
echo Syncing dependencies (first run may take a minute)...
echo Syncing dependencies... >> "%LOGFILE%"
"%UV_EXE%" sync >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo.
    echo ===============================================================
    echo   uv sync failed (error code %errorlevel%).
    echo ===============================================================
    echo.
    echo See the full output in: %LOGFILE%
    echo.
    echo --- Last 30 lines of the log: ---
    powershell -NoProfile -Command "Get-Content '%LOGFILE%' -Tail 30"
    echo.
    echo Press any key to close this window...
    pause >nul
    exit /b 1
)
echo uv sync completed.
echo uv sync completed. >> "%LOGFILE%"

REM ---------------------------------------------------------------
REM 3. Run the GUI.
REM ---------------------------------------------------------------
echo.
echo ===============================================================
echo   Starting the GUI. Close the GUI window to return here.
echo ===============================================================
echo.
echo Starting the GUI... >> "%LOGFILE%"
"%UV_EXE%" run python run.py >> "%LOGFILE%" 2>&1
set "RC=%errorlevel%"
echo.
if %RC% NEQ 0 (
    echo ===============================================================
    echo   The GUI exited with code %RC%.
    echo ===============================================================
    echo.
    echo See the full output in: %LOGFILE%
    echo.
    echo --- Last 30 lines of the log: ---
    powershell -NoProfile -Command "Get-Content '%LOGFILE%' -Tail 30"
) else (
    echo The GUI closed normally. You can re-run this launcher any time.
)
echo.
echo Press any key to close this window...
pause >nul
exit /b %RC%
