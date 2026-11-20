import pytest

from steps.apply_overrides.process import apply_overrides


def rec(key, body_id=None, status="unmatched"):
    return {"source_key": key, "public_body_id": body_id, "match_status": status, "match_method": None}


def test_override_id_sets_body_and_status():
    out, unreviewed = apply_overrides([rec("a")], {"a": 5}, {5})
    assert out[0]["public_body_id"] == 5 and out[0]["match_status"] == "override"
    assert unreviewed == []


def test_null_override_is_reviewed_but_stays_unmatched():
    out, unreviewed = apply_overrides([rec("a")], {"a": None}, {5})
    assert out[0]["public_body_id"] is None and out[0]["match_status"] == "unmatched"
    assert unreviewed == []


def test_unmatched_without_override_is_reported_and_kept():
    out, unreviewed = apply_overrides([rec("a")], {}, {5})
    assert len(out) == 1 and unreviewed == ["a"]


def test_unknown_target_body_is_fatal():
    with pytest.raises(ValueError, match="unknown public_body_id"):
        apply_overrides([rec("a")], {"a": 999}, {5})


def test_stale_override_key_is_fatal():
    with pytest.raises(ValueError, match="not in the source"):
        apply_overrides([rec("a")], {"gone": 5}, {5})


def test_redundant_override_is_fatal():
    with pytest.raises(ValueError, match="redundant"):
        apply_overrides([rec("a", 5, "exact")], {"a": 5}, {5})
