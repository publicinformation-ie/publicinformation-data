import sys
from pathlib import Path

_HERE = Path(__file__).parent
_REPO_ROOT = _HERE
_prev = None
while not (_REPO_ROOT / ".git").exists():
    if _prev == _REPO_ROOT:
        raise RuntimeError(f"Could not find .git root starting from {_HERE}")
    _prev = _REPO_ROOT
    _REPO_ROOT = _REPO_ROOT.parent
sys.path.insert(0, str(_HERE.parent))        # pipelines/actions_pipeline/, for steps.*
sys.path.insert(0, str(_REPO_ROOT / "src"))  # src/lib/
