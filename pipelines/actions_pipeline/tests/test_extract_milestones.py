import importlib.util
from pathlib import Path

import pytest

_PATH = Path(__file__).parents[1] / "steps" / "extract_milestones" / "process.py"
_spec = importlib.util.spec_from_file_location("extract_milestones_process", _PATH)
step = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(step)

ACTION_4 = ("Q1 2029 – Convene working group to review contract. Q3 2030 – "
            "Secure Ministerial sign-off.")


def action(action_id, text):
    return {"action_id": action_id, "original_deadline_milestones": text}


def test_one_record_per_milestone_with_ids():
    records, errors = step.build_milestones([action("smp#4", ACTION_4)])
    assert [r["milestone_id"] for r in records] == ["smp#4/m1", "smp#4/m2"]
    assert records[0]["due_precision"] == "quarter"
    assert errors == []


def test_action_without_milestone_text_yields_no_records():
    records, _ = step.build_milestones([action("a#1", ""), action("a#2", None)])
    assert records == []


def test_round_trip_failure_falls_back_and_logs(monkeypatch):
    def boom(_text):
        raise step.MilestoneRoundTripFailed("x")
    monkeypatch.setattr(step, "split_milestones", boom)
    records, errors = step.build_milestones([action("a#1", "2024: x.")])
    assert len(records) == 1 and records[0]["due_label"] == ""
    assert records[0]["milestone_text"] == "2024: x."
    assert errors[0]["error_type"] == "MilestoneRoundTripFailed"


def test_records_follow_input_order():
    records, _ = step.build_milestones(
        [action("b#1", "2024: x."), action("a#1", "2023: y.")])
    assert [r["action_id"] for r in records] == ["b#1", "a#1"]


def test_every_record_action_id_exists_in_input():
    actions = [action("a#1", ACTION_4), action("a#2", "2024: x.")]
    records, _ = step.build_milestones(actions)
    assert {r["action_id"] for r in records} <= {a["action_id"] for a in actions}
