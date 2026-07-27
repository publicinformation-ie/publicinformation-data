import json
import sys

import pytest

from steps.apply_overrides.process import apply_overrides, find_unresolved, count_via_override


# ── apply_overrides ──────────────────────────────────────────────────────

def test_apply_overrides_fills_a_null():
    records = [{"foigovie_slug": "an-garda-siochana", "public_body_id": None}]
    resolved = apply_overrides(records, {"an-garda-siochana": 1014})
    assert resolved[0]["public_body_id"] == 1014


def test_apply_overrides_replaces_an_existing_fuzzy_match():
    """A non-null override always wins, so a coincidental >=0.90 false
    positive can be corrected without lowering the threshold."""
    records = [{"foigovie_slug": "some-slug", "public_body_id": 9999}]
    resolved = apply_overrides(records, {"some-slug": 1014})
    assert resolved[0]["public_body_id"] == 1014


def test_apply_overrides_explicit_null_suppresses_existing_match():
    records = [{"foigovie_slug": "some-slug", "public_body_id": 9999}]
    resolved = apply_overrides(records, {"some-slug": None})
    assert resolved[0]["public_body_id"] is None


def test_apply_overrides_leaves_unlisted_slug_unchanged():
    records = [{"foigovie_slug": "unlisted", "public_body_id": 1234}]
    resolved = apply_overrides(records, {})
    assert resolved[0]["public_body_id"] == 1234


def test_apply_overrides_does_not_mutate_the_input_records():
    records = [{"foigovie_slug": "s", "public_body_id": None}]
    apply_overrides(records, {"s": 1})
    assert records[0]["public_body_id"] is None


# ── find_unresolved ──────────────────────────────────────────────────────

def test_find_unresolved_lists_null_slugs_absent_from_overrides():
    records = [
        {"foigovie_slug": "matched", "public_body_id": 1},
        {"foigovie_slug": "unmatched", "public_body_id": None},
    ]
    assert find_unresolved(records, {}) == ["unmatched"]


def test_find_unresolved_is_empty_when_all_resolve():
    assert find_unresolved([{"foigovie_slug": "matched", "public_body_id": 1}], {}) == []


def test_find_unresolved_excludes_a_slug_explicitly_nulled_in_overrides():
    """A slug present in override.json with an explicit null has been deliberately
    reviewed and marked as having no canonical counterpart -- that's resolved, not
    a failure, even though public_body_id is still None."""
    records = [{"foigovie_slug": "no-counterpart", "public_body_id": None}]
    assert find_unresolved(records, {"no-counterpart": None}) == []


def test_find_unresolved_still_flags_a_null_slug_missing_from_overrides():
    """A slug that was never reviewed at all (absent from override.json) must
    still fatal -- only an explicit null entry counts as reviewed."""
    records = [{"foigovie_slug": "never-reviewed", "public_body_id": None}]
    assert find_unresolved(records, {"some-other-slug": None}) == ["never-reviewed"]


# ── count_via_override ───────────────────────────────────────────────────

def test_count_via_override_counts_non_null_override_values_only():
    records = [{"foigovie_slug": "a"}, {"foigovie_slug": "b"}, {"foigovie_slug": "c"}]
    assert count_via_override(records, {"a": 123, "b": None}) == 1


# ── main (the behavioural difference from datagovie_pipeline) ────────────

def _write_input(tmp_path, records):
    from lib.file_utils import write_json
    input_path = tmp_path / "input.json"
    write_json(input_path, {"metadata": {}, "results": records})
    return input_path


def test_main_fatal_exits_when_any_record_is_unresolved(tmp_path, monkeypatch):
    input_path = _write_input(tmp_path, [
        {"foigovie_slug": "matched", "foigovie_name": "X", "public_body_id": 1},
        {"foigovie_slug": "unmatched", "foigovie_name": "Y", "public_body_id": None},
    ])
    monkeypatch.setattr(sys, "argv", [
        "process.py", "--input", str(input_path),
        "--output", str(tmp_path / "output.json"), "--force",
    ])
    from steps.apply_overrides import process as proc_mod
    with pytest.raises(SystemExit) as exc:
        proc_mod.main()
    assert exc.value.code != 0
    assert not (tmp_path / "output.json").exists()


def test_main_writes_output_when_every_record_resolves(tmp_path, monkeypatch):
    input_path = _write_input(tmp_path, [
        {"foigovie_slug": "matched", "foigovie_name": "X", "public_body_id": 1},
    ])
    output_path = tmp_path / "output.json"
    monkeypatch.setattr(sys, "argv", [
        "process.py", "--input", str(input_path), "--output", str(output_path), "--force",
    ])
    from steps.apply_overrides import process as proc_mod
    proc_mod.main()  # must not raise / sys.exit
    output = json.loads(output_path.read_text())
    assert len(output["results"]) == 1
    assert output["results"][0]["public_body_id"] == 1
