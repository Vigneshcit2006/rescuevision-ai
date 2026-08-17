# Run the RescueVision AI frontend dev server locally (Windows / PowerShell).
# Usage: powershell -ExecutionPolicy Bypass -File scripts/run_frontend.ps1

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendDir = Join-Path $repoRoot "frontend"
Set-Location $frontendDir

if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Write-Host "No frontend/.env found - copying frontend/.env.example (local-safe defaults)."
    Copy-Item ".env.example" ".env"
}

Write-Host "Installing dependencies..."
if (Test-Path "package-lock.json") {
    npm ci
} else {
    npm install
}

Write-Host "Starting Vite dev server on http://localhost:5173 ..."
npm run dev
