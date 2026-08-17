@echo off
REM Double-click this file to install deps (if needed) and start the
REM RescueVision AI backend (FastAPI + OpenCV 5) on http://localhost:8000
REM Keeps the cmd window open so you can see logs / any errors.

cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_backend.ps1"

echo.
echo Backend process exited. Press any key to close this window.
pause >nul
