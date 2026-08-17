#!/usr/bin/env bash
# Run the RescueVision AI frontend dev server locally (Linux/macOS/Git Bash).
# Usage: bash scripts/run_frontend.sh
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root/frontend"

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    echo "No frontend/.env found - copying frontend/.env.example (local-safe defaults)."
    cp .env.example .env
fi

echo "Installing dependencies..."
if [ -f "package-lock.json" ]; then
    npm ci
else
    npm install
fi

echo "Starting Vite dev server on http://localhost:5173 ..."
npm run dev
