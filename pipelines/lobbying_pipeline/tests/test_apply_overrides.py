import json
import sys

from steps.apply_overrides.process import apply_overrides, drop_unresolved, count_via_override


# ── apply_overrides ──────────────────────────────────────────────────────

def test_apply_overrides_fills_a_null():
    records = [{"lobbyingie_id": 1571, "public_body_id": None}]
    overrides = {"1571": 1234}
    resolved = apply_overrides(records, overrides)
    assert resolved[0]["public_body_id"] == 1234


def test_apply_overrides_replaces_an_existing_fuzzy_match():
    records = [{"lobbyingie_id": 1571, "public_body_id": 9999}]
    overrides = {"1571": 1234}
    resolved = apply_overrides(records, overrides)
    assert resolved[0]["public_body_id"] == 1234


def test_apply_overrides_explicit_null_suppresses_existing_match():
    records = [{"lobbyingie_id": 1571, "public_body_id": 9999}]
    overrides = {"1571": None}
    resolved = apply_overrides(records, overrides)
    assert resolved[0]["public_body_id"] is None


def test_apply_overrides_leaves_unlisted_id_unchanged():
    records = [{"lobbyingie_id": 4242, "public_body_id": None}]
    resolved = apply_overrides(records, {})
    assert resolved[0]["public_body_id"] is None


# ── drop_unresolved ──────────────────────────────────────────────────────

def test_drop_unresolved_removes_null_records_and_lists_their_ids():
    records = [
        {"lobbyingie_id": 1600, "public_body_id": 1},
        {"lobbyingie_id": 9999, "public_body_id": None},
    ]
    resolved, dropped = drop_unresolved(records)
    assert resolved == [{"lobbyingie_id": 1600, "public_body_id": 1}]
    assert dropped == [9999]


def test_drop_unresolved_is_not_fatal_when_records_remain(tmp_path, monkeypatch):
    from lib.file_utils import write_json

    input_path = tmp_path / "input.json"
    write_json(input_path, {"metadata": {}, "results": [
        {"lobbyingie_id": 1600, "lobbyingie_name": "X", "public_body_id": 1},
        {"lobbyingie_id": 9999, "lobbyingie_name": "Y", "public_body_id": None},
    ]})
    output_path = tmp_path / "output.json"
    monkeypatch.setattr(sys, "argv", [
        "process.py", "--input", str(input_path), "--output", str(output_path), "--force",
    ])
    from steps.apply_overrides import process as proc_mod
    proc_mod.main()  # must not raise / sys.exit

    output = json.loads(output_path.read_text())
    assert len(output["results"]) == 1
    assert output["results"][0]["lobbyingie_id"] == 1600


# ── count_via_override ───────────────────────────────────────────────────

def test_count_via_override_counts_non_null_override_values():
    records = [{"lobbyingie_id": 1}, {"lobbyingie_id": 2}]
    overrides = {"1": 123, "2": None}
    assert count_via_override(records, overrides) == 1
