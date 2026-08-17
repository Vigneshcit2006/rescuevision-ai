#!/usr/bin/env bash
# Run the RescueVision AI backend test suite (Linux/macOS/Git Bash).
# Usage: bash scripts/run_tests.sh
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root/backend"

if [ -d ".venv" ]; then
    echo "Activating existing virtual environment..."
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi

echo "Installing dependencies (requirements.txt + requirements-dev.txt)..."
python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt
pip install -r requirements-dev.txt

echo "Running pytest..."
python -m pytest tests/ -v
