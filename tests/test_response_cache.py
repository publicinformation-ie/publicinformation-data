import json
from datetime import datetime, timedelta, timezone

from lib.response_cache import ResponseCache


def test_key_is_stable_and_order_insensitive_for_dicts():
    a = ResponseCache.key("apify", {"b": 1, "a": 2}, "q")
    b = ResponseCache.key("apify", {"a": 2, "b": 1}, "q")
    assert a == b and len(a) == 32


def test_put_then_get_roundtrip(tmp_path):
    cache = ResponseCache(tmp_path / "c")
    k = ResponseCache.key("x")
    rec = cache.put(k, {"item": {"n": "Móna"}})
    assert rec["item"] == {"n": "Móna"} and "cached_at" in rec
    assert cache.get(k)["item"] == {"n": "Móna"}
    # stored as UTF-8, not escaped
    assert "Móna" in (tmp_path / "c" / f"{k}.json").read_text(encoding="utf-8")


def test_get_missing_returns_none(tmp_path):
    assert ResponseCache(tmp_path).get("nope") is None


def test_max_age_expires(tmp_path):
    cache = ResponseCache(tmp_path)
    k = ResponseCache.key("old")
    old = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    (tmp_path / f"{k}.json").write_text(json.dumps({"cached_at": old, "v": 1}))
    assert cache.get(k) is not None
    assert cache.get(k, max_age_days=30) is None
    assert cache.get(k, max_age_days=60) is not None


def test_corrupt_file_treated_as_miss(tmp_path):
    cache = ResponseCache(tmp_path)
    (tmp_path / "bad.json").write_text("{not json")
    assert cache.get("bad") is None
