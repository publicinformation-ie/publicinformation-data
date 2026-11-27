import json
from pathlib import Path

import pytest

from steps.extract_spc_items.extraction import (
    assign_decision_ids,
    load_decision_ids,
)

PIPELINE = Path(__file__).resolve().parents[1]
MEETING_ID = "meath/test/2026-01-01"
MEETING = {"meeting_id": MEETING_ID}
Q1 = "It was agreed to circulate the policy to the members."
Q2 = "It was agreed to defer the report to the next meeting."


def _d(quote, item="item-2-0"):
    return {"item_key": item, "item_number": item[5:].replace("-", "."),
            "decision_text": quote}


def _entry(n, quote, item="item-2-0", status="active", **extra):
    return {"id": f"{MEETING_ID}/d{n:02d}", "item_key": item, "quote": quote,
            "status": status, **extra}


def _ids(decisions):
    return [d["decision_id"] for d in decisions]


def test_a_meeting_with_no_registry_is_numbered_in_order():
    registry = {}
    out, errors = assign_decision_ids(
        MEETING, [_d(Q1), _d(Q2, "item-3-0")], registry)
    assert errors == []
    assert _ids(out) == [f"{MEETING_ID}/d01", f"{MEETING_ID}/d02"]
    assert [e["id"] for e in registry[MEETING_ID]] == _ids(out)
    assert all(e["status"] == "active" for e in registry[MEETING_ID])


def test_ids_survive_an_added_earlier_decision():
    registry = {MEETING_ID: [_entry(1, Q1), _entry(2, Q2, "item-3-0")]}
    new = "It was noted that a new item preceded the others."
    out, errors = assign_decision_ids(
        MEETING, [_d(new, "item-1-0"), _d(Q1), _d(Q2, "item-3-0")], registry)
    assert errors == []
    assert _ids(out) == [f"{MEETING_ID}/d03", f"{MEETING_ID}/d01",
                         f"{MEETING_ID}/d02"]


def test_whitespace_differences_still_match():
    registry = {MEETING_ID: [_entry(1, Q1)]}
    out, errors = assign_decision_ids(
        MEETING, [_d(Q1.replace(" to ", "  to\n"))], registry)
    assert errors == [] and _ids(out) == [f"{MEETING_ID}/d01"]


def test_the_next_number_counts_retired_numbers():
    registry = {MEETING_ID: [_entry(1, Q1), _entry(4, Q2, "item-3-0",
                                                  status="retired", reason="x")]}
    new = "It was resolved to note the update from the executive."
    out, errors = assign_decision_ids(MEETING, [_d(Q1), _d(new, "item-5-0")],
                                      registry)
    assert errors == []
    assert _ids(out) == [f"{MEETING_ID}/d01", f"{MEETING_ID}/d05"]


def test_a_retired_decision_is_suppressed_and_its_number_stays_reserved():
    registry = {MEETING_ID: [_entry(1, Q1, status="retired", reason="not ours")]}
    new = "It was agreed to note the update from the executive."
    out, errors = assign_decision_ids(MEETING, [_d(Q1), _d(new, "item-5-0")],
                                      registry)
    assert errors == []
    assert _ids(out) == [f"{MEETING_ID}/d02"]


def test_quote_boundary_drift_is_an_error_and_is_not_renumbered():
    registry = {MEETING_ID: [_entry(1, Q1)]}
    drifted = Q1 + " The matter was closed."
    out, errors = assign_decision_ids(MEETING, [_d(drifted)], registry)
    assert out == []
    assert [e["error_type"] for e in errors] == ["DecisionIdAmbiguous"]
    assert "d01" in errors[0]["error_message"]
    assert registry == {MEETING_ID: [_entry(1, Q1)]}  # unchanged


def test_a_registered_decision_no_longer_extracted_is_an_error():
    registry = {MEETING_ID: [_entry(1, Q1), _entry(2, Q2, "item-3-0")]}
    out, errors = assign_decision_ids(MEETING, [_d(Q1)], registry)
    assert _ids(out) == [f"{MEETING_ID}/d01"]
    assert [e["error_type"] for e in errors] == ["RegisteredDecisionMissing"]
    assert f"{MEETING_ID}/d02" in errors[0]["error_message"]
    assert [e["id"] for e in registry[MEETING_ID]] == [
        f"{MEETING_ID}/d01", f"{MEETING_ID}/d02"]


def test_existing_entries_are_never_edited():
    original = [_entry(1, Q1)]
    registry = {MEETING_ID: [dict(e) for e in original]}
    assign_decision_ids(MEETING, [_d(Q1), _d(Q2, "item-3-0")], registry)
    assert registry[MEETING_ID][0] == original[0]


def _write(tmp_path, data):
    (tmp_path / "decision_ids.schema.json").write_text(
        (PIPELINE / "steps/extract_spc_items/decision_ids.schema.json").read_text())
    path = tmp_path / "decision_ids.json"
    path.write_text(json.dumps(data))
    return path


@pytest.mark.parametrize("entries,match", [
    ([_entry(1, Q1), _entry(1, Q2, "item-3-0")], "reuses d01"),
    ([{**_entry(1, Q1), "id": "other/d01"}], "malformed"),
    ([{**_entry(1, Q1), "id": "nonsense"}], None),
    ([_entry(1, Q1, status="gone")], None),
    ([_entry(1, Q1, status="retired")], "needs a reason"),
])
def test_the_loader_rejects_bad_registries(tmp_path, entries, match):
    with pytest.raises(ValueError, **({"match": match} if match else {})):
        load_decision_ids(_write(tmp_path, {MEETING_ID: entries}))


def test_an_absent_registry_is_empty(tmp_path):
    assert load_decision_ids(tmp_path / "decision_ids.json") == {}


def test_every_published_decision_is_active_in_the_registry():
    registry = load_decision_ids(PIPELINE / "steps/extract_spc_items/decision_ids.json")
    published = json.loads((PIPELINE.parents[1] / "public/latest/spc-meetings/"
                            "decisions.jsonld").read_text(encoding="utf-8"))["@graph"]
    assert published
    by_id = {e["id"]: e for entries in registry.values() for e in entries}
    for decision in published:
        entry = by_id[decision["decision_id"]]
        assert entry["status"] == "active"
        assert entry["item_key"] == decision["item_key"]
        assert entry["quote"] == " ".join(decision["decision_text"].split())
    retired = [i for i, e in by_id.items() if e["status"] == "retired"]
    assert not set(retired) & {d["decision_id"] for d in published}
