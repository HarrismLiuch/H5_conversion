@echo off
REM Inner launcher: the real work. Always run from launch_windows.bat,
REM which spawns this file under cmd /k so the window stays open.
REM
REM This file can also be run directly from a CMD window if you want to
REM see the output in a console that you control.
REM
REM Every line is appended to launcher.log so you can read what happened
REM even if the window does close.

setlocal EnableExtensions EnableDelayedExpansion
set "LOGFILE=%~dp0launcher.log"
echo. > "%LOGFILE%"

echo =============================================================== >> "%LOGFILE%"
echo Inner launcher started at %DATE% %TIME% >> "%LOGFILE%"
echo =============================================================== >> "%LOGFILE%"
echo.
echo === H5 Conversion launcher ===
echo Log: %LOGFILE%
echo.

REM ---------------------------------------------------------------
REM 1. Locate `uv`. Check the binary's actual filesystem path first,
REM    because the installer's PATH update often doesn't reach the
REM    current CMD session.
REM ---------------------------------------------------------------
set "UV_EXE="
for %%P in ("%USERPROFILE%\.local\bin\uv.exe", "%LOCALAPPDATA%\uv\uv.exe") do (
    if not defined UV_EXE if exist "%%~P" set "UV_EXE=%%~P"
)
if not defined UV_EXE (
    echo uv was not found on this system. Installing it now (one-time)...
    echo uv was not found on this system. Installing it now. >> "%LOGFILE%"
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex" >> "%LOGFILE%" 2>&1
    if exist "%USERPROFILE%\.local\bin\uv.exe" set "UV_EXE=%USERPROFILE%\.local\bin\uv.exe"
)
if not defined UV_EXE (
    echo.
    echo ERROR: uv is still not installed. Please open PowerShell and run:
    echo     irm https://astral.sh/uv/install.ps1 ^| iex
    echo Then double-click launch_windows.bat again.
    echo.
    echo --- Last 20 lines of the installer log: ---
    powershell -Command "Get-Content '%LOGFILE%' -Tail 20"
    echo.
    echo Installer output has been saved to: %LOGFILE%
    echo Press any key to close this window...
    pause >nul
    exit /b 1
)
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
    echo uv sync failed with error %errorlevel%.
    echo See the full output in: %LOGFILE%
    echo.
    echo --- Last 30 lines of the log: ---
    powershell -Command "Get-Content '%LOGFILE%' -Tail 30"
    echo.
    echo Press any key to close this window...
    pause >nul
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
echo Starting the GUI... >> "%LOGFILE%"
"%UV_EXE%" run python run.py >> "%LOGFILE%" 2>&1
set "RC=%errorlevel%"
echo.
if %RC% NEQ 0 (
    echo The GUI exited with code %RC%. See the full output in: %LOGFILE%
    echo.
    echo --- Last 30 lines of the log: ---
    powershell -Command "Get-Content '%LOGFILE%' -Tail 30"
) else (
    echo The GUI closed normally. You can re-run this launcher any time.
)
echo.
echo Press any key to close this window...
pause >nul
exit /b %RC%
