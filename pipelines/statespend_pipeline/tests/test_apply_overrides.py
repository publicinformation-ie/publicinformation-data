import json
import sys

import pytest

from steps.apply_overrides.process import (
    apply_overrides, verify_override_ids, drop_unresolved, count_via_override,
)


# ── apply_overrides ──────────────────────────────────────────────────────

def test_apply_overrides_str_key_matches_int_record_id():
    # Key-type convention: JSON keys are strings, statespend_id is an int.
    records = [{"statespend_id": 4, "public_body_id": None}]
    overrides = {"4": 1010}
    resolved = apply_overrides(records, overrides)
    assert resolved[0]["public_body_id"] == 1010


def test_apply_overrides_fills_a_null():
    records = [{"statespend_id": 2, "public_body_id": None}]
    resolved = apply_overrides(records, {"2": 1038})
    assert resolved[0]["public_body_id"] == 1038


def test_apply_overrides_replaces_an_existing_fuzzy_match():
    records = [{"statespend_id": 93, "public_body_id": 1544}]
    resolved = apply_overrides(records, {"93": 1571})
    assert resolved[0]["public_body_id"] == 1571


def test_apply_overrides_explicit_null_suppresses_existing_match():
    records = [{"statespend_id": 93, "public_body_id": 1544}]
    resolved = apply_overrides(records, {"93": None})
    assert resolved[0]["public_body_id"] is None


def test_apply_overrides_leaves_unlisted_record_unchanged():
    records = [{"statespend_id": 52, "public_body_id": 1234}]
    resolved = apply_overrides(records, {})
    assert resolved[0]["public_body_id"] == 1234


# ── verify_override_ids ──────────────────────────────────────────────────

def test_verify_override_ids_accepts_known_and_null():
    verify_override_ids({"2": 1038, "93": None}, {1038, 1544})


def test_verify_override_ids_fatal_on_unknown_id():
    with pytest.raises(SystemExit):
        verify_override_ids({"2": 999999}, {1038})


# ── drop_unresolved ──────────────────────────────────────────────────────

def test_drop_unresolved_separates_and_logs_reasons():
    records = [
        {"statespend_id": 52, "statespend_name": "Matched", "public_body_id": 1},
        {"statespend_id": 86, "statespend_name": "NTMA Admin", "public_body_id": None},
        {"statespend_id": 300, "statespend_name": "Never Matched", "public_body_id": None},
    ]
    overrides = {"86": None}
    resolved, dropped = drop_unresolved(records, overrides)
    assert [r["statespend_id"] for r in resolved] == [52]
    reasons = {d["statespend_id"]: d["reason"] for d in dropped}
    assert set(reasons) == {86, 300}
    assert "explicit null override" in reasons[86]
    assert "no override" in reasons[300]
    for d in dropped:
        assert d["statespend_name"]


# ── count_via_override ───────────────────────────────────────────────────

def test_count_via_override_counts_non_null_values_only():
    records = [{"statespend_id": 2}, {"statespend_id": 93}]
    overrides = {"2": 1038, "93": None}
    assert count_via_override(records, overrides) == 1


# ── main() end-to-end on a temp dir ──────────────────────────────────────

def test_main_writes_output_and_dropped_log(tmp_path, monkeypatch):
    from lib.file_utils import write_json

    input_path = tmp_path / "input.json"
    write_json(input_path, {"metadata": {}, "results": [
        {"statespend_id": 52, "statespend_name": "X", "public_body_id": 1},
        {"statespend_id": 86, "statespend_name": "NTMA Administration Account",
         "public_body_id": None},
    ]})
    output_path = tmp_path / "output.json"
    monkeypatch.setattr(sys, "argv", [
        "process.py", "--input", str(input_path), "--output", str(output_path), "--force",
    ])
    from steps.apply_overrides import process as proc_mod
    proc_mod.main()  # must not raise / sys.exit (partial resolution is expected)

    output = json.loads(output_path.read_text())
    assert len(output["results"]) == 1
    assert output["results"][0]["statespend_id"] == 52

    errors = json.loads((tmp_path / "errors.json").read_text())
    assert [e["statespend_id"] for e in errors["errors"]] == [86]
    assert "explicit null override" in errors["errors"][0]["reason"]
