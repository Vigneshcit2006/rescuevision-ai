@echo off
REM Double-click this file to start BOTH the backend (http://localhost:8000)
REM and the frontend (http://localhost:5173) in their own separate cmd
REM windows. Close either window to stop that process.

cd /d "%~dp0"

echo Starting backend in a new window...
start "RescueVision AI - Backend" cmd /k "%~dp0run_backend.bat"

echo Starting frontend in a new window...
start "RescueVision AI - Frontend" cmd /k "%~dp0run_frontend.bat"

echo.
echo Both windows have been launched.
echo   Backend:  http://localhost:8000  (docs at /docs, health at /api/health)
echo   Frontend: http://localhost:5173
echo.
echo This window can be closed - it does not need to stay open.
pause >nul
