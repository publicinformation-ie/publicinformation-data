import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def zero_rate_limit(monkeypatch):
    monkeypatch.setattr("scripts.http_utils.RATE_LIMIT_DELAY", 0)
