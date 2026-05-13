import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.file_utils import IncrementalWriter


@pytest.fixture(autouse=True)
def zero_rate_limit(monkeypatch):
    monkeypatch.setattr("scripts.http_utils.DEFAULT_RATE_LIMIT_DELAY", 0)


@pytest.fixture
def make_writer(tmp_path):
    def _make(step_name, key_field="public_body_id", force=True, override_path=None):
        return IncrementalWriter(tmp_path / "output.json", step_name, key_field=key_field,
                                 force=force, override_path=override_path)
    return _make
