@echo off
REM Double-click this file to start BOTH the backend and the frontend:
REM   - Frontend launches in its own separate cmd window (http://localhost:5173)
REM   - Backend runs in THIS window (http://localhost:8000)
REM Close a window (or Ctrl+C inside it) to stop that process.
REM
REM (Internal: pass --nostart-frontend to run backend only, e.g. when
REM  called from run_frontend.bat or start_all.bat, to avoid the two
REM  scripts endlessly launching each other.)

cd /d "%~dp0"

if "%~1"=="--nostart-frontend" goto :backend_only

echo Starting frontend in a new window...
start "RescueVision AI - Frontend" cmd /k "%~dp0run_frontend.bat" --nostart-backend

:backend_only
echo Starting backend in this window...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_backend.ps1"

echo.
echo Backend process exited. Press any key to close this window.
echo (The frontend window, if still open, needs to be closed separately.)
pause >nul
