import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).parent
_PIPELINE_ROOT = _TESTS_DIR.parent
sys.path.insert(0, str(_PIPELINE_ROOT / "steps" / "find_meeting_minutes_pages_search" / "eval"))
sys.path.insert(0, str(_PIPELINE_ROOT / "experiments" / "2026-09-15-minutes-page-discovery" / "approaches"))


def test_grab_skips_cached(tmp_path, monkeypatch):
    import capture_fixtures as cap
    dest = tmp_path / "1.html"
    dest.write_text("cached", encoding="utf-8")
    monkeypatch.setattr(cap, "fetch", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not fetch")))
    assert cap._grab("https://example.com/", dest) is None
    assert dest.read_text(encoding="utf-8") == "cached"


def test_fixture_key_slugs_districts():
    from capture_fixtures import fixture_key
    assert fixture_key(1511, None) == "1511"
    assert fixture_key(1511, "Laytown-Bettystown") == "1511__laytown-bettystown"
    assert fixture_key(1511, "Ashbourne") == "1511__ashbourne"
