import json
import sys

import pytest

from steps.apply_overrides.process import apply_overrides, find_unresolved


# ── apply_overrides ──────────────────────────────────────────────────────

def test_apply_overrides_fills_matching_slug():
    records = [{"wdw_slug": "publicjobs", "public_body_id": None}]
    overrides = {"publicjobs": 1651}
    resolved = apply_overrides(records, overrides)
    assert resolved[0]["public_body_id"] == 1651


def test_apply_overrides_leaves_already_matched_untouched():
    records = [{"wdw_slug": "central-statistics-office", "public_body_id": 1106}]
    overrides = {"central-statistics-office": 9999}
    resolved = apply_overrides(records, overrides)
    assert resolved[0]["public_body_id"] == 1106


def test_apply_overrides_leaves_unlisted_slug_null():
    records = [{"wdw_slug": "some-unmatched-body", "public_body_id": None}]
    resolved = apply_overrides(records, {})
    assert resolved[0]["public_body_id"] is None


# ── find_unresolved ──────────────────────────────────────────────────────

def test_find_unresolved_lists_null_slugs():
    records = [
        {"wdw_slug": "a", "public_body_id": 1},
        {"wdw_slug": "b", "public_body_id": None},
    ]
    assert find_unresolved(records) == ["b"]


def test_find_unresolved_empty_when_all_resolved():
    records = [{"wdw_slug": "a", "public_body_id": 1}]
    assert find_unresolved(records) == []


# ── main() — uses the real committed override.json ──────────────────────

def test_main_exits_nonzero_when_unresolved(tmp_path, monkeypatch):
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps({
        "metadata": {},
        "results": [{"wdw_name": "Totally Unknown Body",
                     "wdw_url": "https://www.gov.ie/en/x/who-does-what/",
                     "wdw_slug": "totally-unknown-body", "public_body_id": None}],
    }))
    output_path = tmp_path / "output.json"

    monkeypatch.setattr(sys, "argv", [
        "process.py", "--input", str(input_path), "--output", str(output_path), "--force",
    ])
    from steps.apply_overrides import process as proc_mod
    with pytest.raises(SystemExit) as exc:
        proc_mod.main()
    assert exc.value.code != 0
    assert not output_path.exists()


def test_main_applies_real_override_for_publicjobs(tmp_path, monkeypatch):
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps({
        "metadata": {},
        "results": [{"wdw_name": "publicjobs",
                     "wdw_url": "https://www.gov.ie/en/publicjobs/organisation-information/publicjobs-who-does-what/",
                     "wdw_slug": "publicjobs", "public_body_id": None}],
    }))
    output_path = tmp_path / "output.json"

    monkeypatch.setattr(sys, "argv", [
        "process.py", "--input", str(input_path), "--output", str(output_path), "--force",
    ])
    from steps.apply_overrides import process as proc_mod
    proc_mod.main()

    output = json.loads(output_path.read_text())
    assert output["results"][0]["public_body_id"] == 1651
