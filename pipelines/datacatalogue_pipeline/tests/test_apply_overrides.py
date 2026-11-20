import json
import sys

from steps.apply_overrides.process import apply_overrides, drop_unresolved, count_via_override


# ── apply_overrides ──────────────────────────────────────────────────────

def test_apply_overrides_fills_a_null():
    records = [{"datacatalogue_slug": "an-garda-siochana", "public_body_id": None}]
    overrides = {"an-garda-siochana": 1234}
    resolved = apply_overrides(records, overrides)
    assert resolved[0]["public_body_id"] == 1234


def test_apply_overrides_replaces_an_existing_fuzzy_match():
    records = [{"datacatalogue_slug": "some-slug", "public_body_id": 9999}]
    overrides = {"some-slug": 1234}
    resolved = apply_overrides(records, overrides)
    assert resolved[0]["public_body_id"] == 1234


def test_apply_overrides_explicit_null_suppresses_existing_match():
    records = [{"datacatalogue_slug": "some-slug", "public_body_id": 9999}]
    overrides = {"some-slug": None}
    resolved = apply_overrides(records, overrides)
    assert resolved[0]["public_body_id"] is None


def test_apply_overrides_leaves_unlisted_slug_unchanged():
    records = [{"datacatalogue_slug": "unlisted", "public_body_id": None}]
    resolved = apply_overrides(records, {})
    assert resolved[0]["public_body_id"] is None


# ── drop_unresolved ──────────────────────────────────────────────────────

def test_drop_unresolved_removes_null_records_and_lists_their_slugs():
    records = [
        {"datacatalogue_slug": "matched", "public_body_id": 1},
        {"datacatalogue_slug": "unmatched", "public_body_id": None},
    ]
    resolved, dropped = drop_unresolved(records)
    assert resolved == [{"datacatalogue_slug": "matched", "public_body_id": 1}]
    assert dropped == ["unmatched"]


def test_drop_unresolved_is_not_fatal_when_records_remain(tmp_path, monkeypatch):
    from lib.file_utils import write_json

    input_path = tmp_path / "input.json"
    write_json(input_path, {"metadata": {}, "results": [
        {"datacatalogue_slug": "matched", "datacatalogue_name": "X", "public_body_id": 1},
        {"datacatalogue_slug": "unmatched", "datacatalogue_name": "Y", "public_body_id": None},
    ]})
    output_path = tmp_path / "output.json"
    monkeypatch.setattr(sys, "argv", [
        "process.py", "--input", str(input_path), "--output", str(output_path), "--force",
    ])
    from steps.apply_overrides import process as proc_mod
    proc_mod.main()  # must not raise / sys.exit

    output = json.loads(output_path.read_text())
    assert len(output["results"]) == 1
    assert output["results"][0]["datacatalogue_slug"] == "matched"


# ── count_via_override ───────────────────────────────────────────────────

def test_count_via_override_counts_non_null_override_values():
    records = [{"datacatalogue_slug": "a"}, {"datacatalogue_slug": "b"}]
    overrides = {"a": 123, "b": None}
    assert count_via_override(records, overrides) == 1


# ── summary line ─────────────────────────────────────────────────────────

def test_main_prints_matched_override_and_dropped_summary(tmp_path, monkeypatch, capsys):
    from lib.file_utils import write_json
    from steps.apply_overrides import process as proc_mod

    input_path = tmp_path / "input.json"
    write_json(input_path, {"metadata": {}, "results": [
        {"datacatalogue_slug": "auto", "public_body_id": 1},
        {"datacatalogue_slug": "fixed", "public_body_id": None},
        {"datacatalogue_slug": "suppressed", "public_body_id": 3},
        {"datacatalogue_slug": "unmatched", "public_body_id": None},
    ]})
    override_path = tmp_path / "override.json"
    write_json(override_path, {"fixed": 2, "suppressed": None})
    monkeypatch.setattr(proc_mod, "__file__", str(tmp_path / "process.py"))
    output_path = tmp_path / "output.json"
    monkeypatch.setattr(sys, "argv", [
        "process.py", "--input", str(input_path), "--output", str(output_path), "--force"])
    proc_mod.main()

    assert "Matched 2/4 (1 via override), dropped 2 unmatched" in capsys.readouterr().out
    slugs = [r["datacatalogue_slug"] for r in json.loads(output_path.read_text())["results"]]
    assert slugs == ["auto", "fixed"]
