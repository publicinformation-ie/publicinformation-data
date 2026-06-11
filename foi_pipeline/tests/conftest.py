import sys
import time
from pathlib import Path
import shutil
import tempfile

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.file_utils import IncrementalWriter


@pytest.fixture(autouse=True)
def zero_rate_limit(monkeypatch):
    monkeypatch.setattr("lib.http_utils.DEFAULT_RATE_LIMIT_DELAY", 0)


@pytest.fixture(autouse=True)
def clean_shared_cache(tmp_path):
    """Clean up shared cache directory before each test to ensure test isolation.

    Since transform_disclosure_files now points its cache at verify_disclosure_files/cache,
    which is outside the tmp_path isolation, we need to clean it before each test.
    """
    cache_dir = tmp_path.parent / "verify_disclosure_files" / "cache"
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    yield
    # Optional: clean up after test as well
    if cache_dir.exists():
        shutil.rmtree(cache_dir)


@pytest.fixture
def make_writer(tmp_path):
    def _make(step_name, key_field="public_body_id", force=True, override_path=None):
        return IncrementalWriter(tmp_path / "output.json", step_name, key_field=key_field,
                                 force=force, override_path=override_path)
    return _make
