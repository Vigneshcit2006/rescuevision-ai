@echo off
REM Double-click this file to install deps (if needed) and start the
REM RescueVision AI frontend dev server on http://localhost:5173
REM Keeps the cmd window open so you can see logs / any errors.

cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_frontend.ps1"

echo.
echo Frontend process exited. Press any key to close this window.
pause >nul
