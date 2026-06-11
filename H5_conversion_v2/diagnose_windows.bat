@echo off
REM Diagnostic tool: prints everything the launcher needs to know.
REM Run from a CMD window:  diagnose_windows.bat

setlocal EnableExtensions
echo ===============================================================
echo   H5 Conversion — Windows diagnostic
echo ===============================================================
echo.
echo [PATH directories]
echo %PATH%
echo.
echo [Looking for uv.exe]
for %%P in ("%USERPROFILE%\.local\bin\uv.exe", "%LOCALAPPDATA%\uv\uv.exe") do (
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
    echo .venv is missing — run launch_windows.bat to create it.
)
echo.
echo [Project lockfile]
if exist "uv.lock" (
    echo uv.lock is present
) else (
    echo uv.lock is missing
)
echo.
echo ===============================================================
echo   End of diagnostic
echo ===============================================================
pause
