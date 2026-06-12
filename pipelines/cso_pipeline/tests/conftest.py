import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).parent
_REPO_ROOT = _HERE
while not (_REPO_ROOT / ".git").exists():
    _REPO_ROOT = _REPO_ROOT.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_HERE.parent))  # pipelines/cso_pipeline/, for steps.* imports


@pytest.fixture(autouse=True)
def zero_rate_limit(monkeypatch):
    monkeypatch.setattr("lib.http_utils.DEFAULT_RATE_LIMIT_DELAY", 0)
