"""Tests for get_foi_emails/eval/evaluate.py scoring logic."""
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parent))  # foi_pipeline/

# Import the module under test — will fail until evaluate.py exists
from steps.get_foi_emails.eval.evaluate import score_records, STEP


# ── score_records unit tests ──────────────────────────────────────────────────

def _record(public_body_id, foi_email, email_status):
    return {
        "public_body_id": public_body_id,
        "name": f"Body {public_body_id}",
        "foi_email": foi_email,
        "email_status": email_status,
    }


def _label(public_body_id, expected_email):
    return {"public_body_id": public_body_id, "expected_email": expected_email}


def test_exact_email_match_is_correct():
    records = [_record(1, "foi@example.ie", "found")]
    labels = [_label(1, "foi@example.ie")]
    results, issues = score_records(records, labels, input_hash="abc")
    accuracy = next(m for m in results.metrics if m.name == "accuracy")
    assert accuracy.value == 1.0
    assert accuracy.counts["correct"] == 1
    assert accuracy.counts["total"] == 1
    assert issues == []


def test_both_empty_is_correct():
    """A body with no FOI email that is labelled as no-email should be correct."""
    records = [_record(1, None, "not_found")]
    labels = [_label(1, "")]
    results, issues = score_records(records, labels, input_hash="abc")
    accuracy = next(m for m in results.metrics if m.name == "accuracy")
    assert accuracy.value == 1.0
    assert issues == []


def test_mismatch_is_incorrect():
    records = [_record(1, "wrong@example.ie", "found")]
    labels = [_label(1, "right@example.ie")]
    results, issues = score_records(records, labels, input_hash="abc")
    accuracy = next(m for m in results.metrics if m.name == "accuracy")
    assert accuracy.value == 0.0
    assert accuracy.counts["correct"] == 0
    assert len(issues) == 1
    assert issues[0].severity == "warning"
    assert "1" in issues[0].description or 1 in issues[0].affected_ids


def test_null_vs_expected_email_is_incorrect():
    """Fixture has null foi_email but label expects a real address — should be incorrect."""
    records = [_record(1, None, "multiple_found")]
    labels = [_label(1, "foi@example.ie")]
    results, issues = score_records(records, labels, input_hash="abc")
    accuracy = next(m for m in results.metrics if m.name == "accuracy")
    assert accuracy.value == 0.0
    assert len(issues) == 1


def test_accuracy_across_mixed_records():
    records = [
        _record(1, "a@example.ie", "found"),
        _record(2, "b@example.ie", "found"),
        _record(3, None, "not_found"),
    ]
    labels = [
        _label(1, "a@example.ie"),   # correct
        _label(2, "wrong@example.ie"),  # incorrect
        _label(3, ""),                # correct (both empty)
    ]
    results, issues = score_records(records, labels, input_hash="abc")
    accuracy = next(m for m in results.metrics if m.name == "accuracy")
    assert accuracy.value == pytest.approx(2 / 3, abs=1e-3)
    assert accuracy.counts["correct"] == 2
    assert accuracy.counts["total"] == 3
    assert len(issues) == 1


def test_per_status_accuracy_metrics_present():
    records = [
        _record(1, "a@example.ie", "found"),
        _record(2, None, "multiple_found"),
        _record(3, None, "not_found"),
    ]
    labels = [
        _label(1, "a@example.ie"),
        _label(2, ""),
        _label(3, ""),
    ]
    results, issues = score_records(records, labels, input_hash="abc")
    metric_names = {m.name for m in results.metrics}
    assert "found_accuracy" in metric_names
    assert "multiple_found_accuracy" in metric_names
    assert "not_found_accuracy" in metric_names


def test_per_status_accuracy_values():
    records = [
        _record(1, "a@example.ie", "found"),
        _record(2, "b@example.ie", "found"),
        _record(3, None, "not_found"),
    ]
    labels = [
        _label(1, "a@example.ie"),     # found correct
        _label(2, "wrong@example.ie"),  # found incorrect
        _label(3, ""),                 # not_found correct
    ]
    results, issues = score_records(records, labels, input_hash="abc")
    found_acc = next(m for m in results.metrics if m.name == "found_accuracy")
    not_found_acc = next(m for m in results.metrics if m.name == "not_found_accuracy")
    assert found_acc.value == pytest.approx(0.5)
    assert not_found_acc.value == 1.0


def test_step_name_in_results():
    records = [_record(1, "a@b.ie", "found")]
    labels = [_label(1, "a@b.ie")]
    results, issues = score_records(records, labels, input_hash="abc")
    assert results.step == STEP


def test_primary_metric_is_accuracy():
    records = [_record(1, "a@b.ie", "found")]
    labels = [_label(1, "a@b.ie")]
    results, issues = score_records(records, labels, input_hash="abc")
    primary = [m for m in results.metrics if m.is_primary]
    assert len(primary) == 1
    assert primary[0].name == "accuracy"
