#!/usr/bin/env python3
import sys
from pathlib import Path

# Find repo root (location-independent — works before and after directory move)
_HERE = Path(__file__).parent
_REPO_ROOT = _HERE
_prev = None
while not (_REPO_ROOT / ".git").exists():
    if _prev == _REPO_ROOT:
        raise RuntimeError(f"Could not find .git root starting from {_HERE}")
    _prev = _REPO_ROOT
    _REPO_ROOT = _REPO_ROOT.parent

sys.path.insert(0, str(_REPO_ROOT / "src"))

from lib.pipeline_runner import main

if __name__ == "__main__":
    main()
