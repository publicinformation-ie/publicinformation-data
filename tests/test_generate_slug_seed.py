"""Unit tests for scripts/generate_slug_seed.py.

Exercises the pure `build_seed()` transform and the local-file branch of
`fetch_bodies()` with no network access. The live-URL branch is exercised
manually (Task 1, Step 5) — this repo has no other place that talks to
publicinformation.ie's production API, so it is not mocked here.
"""

import json
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "src"))

import generate_slug_seed as gss  # noqa: E402


class TestBuildSeed:
    def test_maps_id_to_slug(self):
        bodies = [
            {"id": 1002, "slug": "ability-west", "name": "Ability West"},
            {"id": 1000, "slug": "abargrove-ltd", "name": "Abargrove Ltd"},
        ]
        seed = gss.build_seed(bodies)
        assert seed == {"1000": "abargrove-ltd", "1002": "ability-west"}

    def test_sorts_numerically_not_lexically(self):
        bodies = [
            {"id": 2, "slug": "b", "name": "B"},
            {"id": 10, "slug": "j", "name": "J"},
            {"id": 1, "slug": "a", "name": "A"},
        ]
        seed = gss.build_seed(bodies)
        assert list(seed.keys()) == ["1", "2", "10"]

    def test_raises_on_empty_slug(self):
        bodies = [{"id": 1, "slug": "", "name": "Nameless"}]
        with pytest.raises(ValueError, match="empty slug"):
            gss.build_seed(bodies)

    def test_raises_on_null_slug(self):
        bodies = [{"id": 1, "slug": None, "name": "Nameless"}]
        with pytest.raises(ValueError, match="empty slug"):
            gss.build_seed(bodies)


class TestFetchBodies:
    def test_reads_from_local_file(self, tmp_path):
        fixture = tmp_path / "bodies.json"
        fixture.write_text(json.dumps({"bodies": [{"id": 1, "slug": "a", "name": "A"}]}))
        bodies = gss.fetch_bodies(input_path=str(fixture))
        assert bodies == [{"id": 1, "slug": "a", "name": "A"}]
