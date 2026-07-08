import sys
from pathlib import Path

_HERE = Path(__file__).parent
_REPO_ROOT = _HERE
while not (_REPO_ROOT / ".git").exists():
    _REPO_ROOT = _REPO_ROOT.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_HERE.parent))  # pipelines/wdw_pipeline/, for steps.* imports
