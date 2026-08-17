"""
Thin entry point so `python evaluation/run_evaluation.py` works from the repo
root. All real logic lives in evaluation/scripts/run_evaluation.py so that it
can also be run directly (`python evaluation/scripts/run_evaluation.py`).
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from run_evaluation import main  # noqa: E402

if __name__ == "__main__":
    main()
