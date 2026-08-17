# Run the RescueVision AI backend locally (Windows / PowerShell).
# Usage: powershell -ExecutionPolicy Bypass -File scripts/run_backend.ps1

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
Set-Location $backendDir

$venvPath = Join-Path $backendDir ".venv"
if (Test-Path $venvPath) {
    Write-Host "Activating existing virtual environment..."
    & (Join-Path $venvPath "Scripts\Activate.ps1")
} else {
    Write-Host "No .venv found - using the system/active Python interpreter."
}

Write-Host "Installing dependencies..."
python -m pip install --upgrade pip | Out-Null
pip install -r requirements.txt
if (Test-Path "requirements-dev.txt") {
    pip install -r requirements-dev.txt
}

if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Write-Host "No backend/.env found - copying backend/.env.example (local-safe defaults)."
    Copy-Item ".env.example" ".env"
}

Write-Host "Starting uvicorn on http://0.0.0.0:8000 (docs at /docs, health at /api/health)..."
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
