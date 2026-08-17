@echo off
REM Double-click this file to run the RescueVision AI backend test suite.
REM Keeps the cmd window open so you can see the pytest results.

cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_tests.ps1"

echo.
echo Test run finished. Press any key to close this window.
pause >nul
