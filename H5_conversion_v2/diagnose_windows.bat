@echo off
REM Diagnostic tool: prints everything the launcher needs to know.
REM - Always writes a copy to diagnose.log so you can read it later.
REM - Always waits for a keypress before closing.
REM Run from a CMD window:  diagnose_windows.bat

setlocal EnableExtensions
set "LOGFILE=%~dp0diagnose.log"
(
echo ===============================================================
echo   H5 Conversion - Windows diagnostic
echo   Captured at %DATE% %TIME%
echo ===============================================================
echo.
echo [PATH directories]
echo %PATH%
echo.
echo [Looking for uv.exe]
echo H5CONV_UV_EXE=%H5CONV_UV_EXE%
if defined H5CONV_UV_EXE (
    if exist "%H5CONV_UV_EXE%" (
        echo FOUND override: %H5CONV_UV_EXE%
        "%H5CONV_UV_EXE%" --version
    ) else (
        echo Override path does not exist: %H5CONV_UV_EXE%
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
    if exist "%%~P" (
        echo FOUND: %%~P
        "%%~P" --version
    ) else (
        echo NOT FOUND: %%~P
    )
)
echo.
echo [where uv (system PATH)]
where uv
echo.
echo [Python availability]
where python
where py
echo.
echo [Project venv]
if exist ".venv\Scripts\python.exe" (
    echo .venv exists: .venv\Scripts\python.exe
) else (
    echo .venv is missing - run launch_windows.vbs to create it.
)
echo.
echo [Project lockfile]
if exist "uv.lock" (
    echo uv.lock is present
) else (
    echo uv.lock is missing
)
echo.
echo [Matplotlib cache]
if defined MPLCONFIGDIR (
    echo MPLCONFIGDIR=%MPLCONFIGDIR%
) else (
    echo Launcher default: %TEMP%\h5conv-matplotlib
)
echo.
echo [H5 data files in current directory]
dir /b *.h5 2>nul
echo.
echo ===============================================================
echo   End of diagnostic
echo ===============================================================
) > "%LOGFILE%" 2>&1
type "%LOGFILE%"
echo.
echo A copy of this output was saved to: %LOGFILE%
echo.
echo Press any key to close this window...
pause >nul
