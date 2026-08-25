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
sys.path.insert(0, str(_HERE.parent))          # pipelines/statespend_pipeline/, for steps.* imports
sys.path.insert(0, str(_REPO_ROOT / "src"))     # src/lib/ takes precedence over pipeline lib/

import pytest
from lib.file_utils import IncrementalWriter


@pytest.fixture(autouse=True)
def zero_rate_limit(monkeypatch):
    monkeypatch.setattr("lib.http_utils.DEFAULT_RATE_LIMIT_DELAY", 0)


@pytest.fixture
def make_writer(tmp_path):
    def _make(step_name, key_field="statespend_id", force=True, override_path=None):
        return IncrementalWriter(tmp_path / "output.json", step_name, key_field=key_field,
                                 force=force, override_path=override_path)
    return _make
