@echo off
REM Outer launcher: spawns the inner launcher under a persistent console
REM (cmd /k) so the window stays open even if the user's "Close on exit"
REM console setting is on. The outer (this) process then exits immediately
REM so it does not block the user's view.
REM
REM Most users should double-click THIS file, not the inner one.

setlocal EnableExtensions
echo Launching the GUI in a persistent console window...
start "H5 Conversion" cmd /k "call \"%~dp0launcher_inner.bat\""
exit /b 0
