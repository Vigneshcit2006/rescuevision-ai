#!/usr/bin/env bash
# Run the RescueVision AI backend locally (Linux/macOS/Git Bash).
# Usage: bash scripts/run_backend.sh
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backend_dir="$repo_root/backend"
cd "$backend_dir"

if [ -d ".venv" ]; then
    echo "Activating existing virtual environment..."
    # shellcheck disable=SC1091
    source .venv/bin/activate
else
    echo "No .venv found - using the system/active Python interpreter."
fi

echo "Installing dependencies..."
python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt
[ -f requirements-dev.txt ] && pip install -r requirements-dev.txt

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    echo "No backend/.env found - copying backend/.env.example (local-safe defaults)."
    cp .env.example .env
fi

echo "Starting uvicorn on http://0.0.0.0:8000 (docs at /docs, health at /api/health)..."
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
