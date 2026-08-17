# Run the RescueVision AI backend test suite (Windows / PowerShell).
# Usage: powershell -ExecutionPolicy Bypass -File scripts/run_tests.ps1

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
Set-Location $backendDir

$venvPath = Join-Path $backendDir ".venv"
if (Test-Path $venvPath) {
    Write-Host "Activating existing virtual environment..."
    & (Join-Path $venvPath "Scripts\Activate.ps1")
}

Write-Host "Installing dependencies (requirements.txt + requirements-dev.txt)..."
python -m pip install --upgrade pip | Out-Null
pip install -r requirements.txt
pip install -r requirements-dev.txt

Write-Host "Running pytest..."
python -m pytest tests/ -v
