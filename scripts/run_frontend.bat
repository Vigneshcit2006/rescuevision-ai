@echo off
REM Double-click this file to start BOTH the backend and the frontend:
REM   - Backend launches in its own separate cmd window (http://localhost:8000)
REM   - Frontend runs in THIS window (http://localhost:5173)
REM Close a window (or Ctrl+C inside it) to stop that process.
REM
REM (Internal: pass --nostart-backend to run frontend only, e.g. when
REM  called from run_backend.bat or start_all.bat, to avoid the two
REM  scripts endlessly launching each other.)

cd /d "%~dp0"

if "%~1"=="--nostart-backend" goto :frontend_only

echo Starting backend in a new window...
start "RescueVision AI - Backend" cmd /k "%~dp0run_backend.bat" --nostart-frontend

:frontend_only
echo Starting frontend in this window...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_frontend.ps1"

echo.
echo Frontend process exited. Press any key to close this window.
echo (The backend window, if still open, needs to be closed separately.)
pause >nul
