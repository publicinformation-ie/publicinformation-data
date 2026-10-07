"""Tests for the motion-model-sweep scorer (Task 5).

Loads compare.py via importlib: the experiment directory name contains
dashes so it is not importable with a plain `from ... import` (same loader
pattern as test_motion_model_sweep_sample.py).

Matcher contract (spec section 7): normalise motion_text (lowercase,
collapse whitespace/punctuation), greedy token-set IoU >= 0.8;
meeting_date/stated_date excluded from scoring. Missing cost raises, never
zero-filled.
"""
import importlib.util
from pathlib import Path

import pytest

_COMPARE_PY = (Path(__file__).parent.parent / "experiments"
               / "2026-10-07-motion-model-sweep" / "compare.py")


def _load_compare_module():
    spec = importlib.util.spec_from_file_location("motion_sweep_compare", _COMPARE_PY)
    assert spec is not None and spec.loader is not None, f"Cannot load {_COMPARE_PY}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load_compare_module()
match_motions = _mod.match_motions
score_combo = _mod.score_combo

_MOTION_A = {
    "motion_text": "That the council approves the works.",
    "proposer": "Cllr A",
    "seconder": "Cllr B",
    "status_label": "carried",
}
# Base tokens: {that, the, council, approves, works} (5). One added word:
# 5/6 ~= 0.833 >= 0.8 -> match.
_NEAR_TEXT_ABOVE_08 = "That the council approves the works unanimously."
# Two added words: 5/7 ~= 0.714 < 0.8 -> no match.
_NEAR_TEXT_BELOW_08 = "That the council approves the works unanimously today."
# Dropped word ("council"): 4 shared / 5 union = 0.8 exactly -> match (>=).
_NEAR_TEXT_AT_08 = "That the approves the works."
# Disjoint topic: {that, the, playground, closes, at, dusk} shares only
# {that, the} with _MOTION_A -> 2/9 ~= 0.22 -> no match.
_FAR_TEXT = "That the playground closes at dusk."

_TOKENS = {"prompt": 100, "completion": 20, "total": 120}


def _f(pred, gold, cost_usd=0.0001, tokens=None, error=None):
    """One score_combo file entry: arms-shaped pred record + gold motions."""
    return {
        "pred": {
            "file_url": "https://example.ie/minutes/file01.pdf",
            "motions": pred,
            "stated_date": None,
            "tokens": dict(_TOKENS) if tokens is None else tokens,
            "cost_usd": cost_usd,
            "error": error,
        },
        "gold": gold,
    }


def test_exact_match_scores_one():
    assert score_combo([_f(pred=[_MOTION_A], gold=[_MOTION_A])])["text_f1"] == 1.0


def test_paraphrase_boundary():
    near = _MOTION_A | {"motion_text": _NEAR_TEXT_ABOVE_08}
    far = _MOTION_A | {"motion_text": _NEAR_TEXT_BELOW_08}
    assert match_motions([near], [_MOTION_A])[0][0] is not None
    assert match_motions([far], [_MOTION_A])[0][0] is None


def test_null_gold_fails_loudly():
    with pytest.raises(ValueError):
        score_combo([_f(pred=[_MOTION_A], gold=None)])


def test_threshold_is_inclusive_at_exactly_08():
    at = _MOTION_A | {"motion_text": _NEAR_TEXT_AT_08}
    assert match_motions([at], [_MOTION_A])[0][0] is not None


def test_aggregates_count_failure_and_fields():
    motion_b = _MOTION_A | {"motion_text": _FAR_TEXT}
    files = [
        _f(pred=[_MOTION_A], gold=[_MOTION_A]),  # TP=1
        _f(pred=[_MOTION_A, motion_b], gold=[_MOTION_A]),  # TP+1, FP+1, count err 1
        _f(pred=None, gold=[_MOTION_A, motion_b],  # full miss: FN+2, count err 2
           error="RuntimeError: backend down"),
    ]
    out = score_combo(files)
    # TP=2, FP=1, FN=2 -> 2*2/(2*2+1+2) = 4/7.
    assert out["text_f1"] == round(4 / 7, 4)
    assert out["count_mae"] == 1.0
    assert out["failure_rate"] == round(1 / 3, 4)
    # Both matched pairs are exact copies -> all fields correct.
    assert out["field_acc"] == 1.0


def test_field_accuracy_counts_each_field():
    pred = _MOTION_A | {"proposer": "Cllr Z"}  # 1 of 3 fields wrong
    out = score_combo([_f(pred=[pred], gold=[_MOTION_A])])
    assert out["text_f1"] == 1.0
    assert out["field_acc"] == round(2 / 3, 4)


def test_missing_cost_raises():
    with pytest.raises(ValueError):
        score_combo([_f(pred=[_MOTION_A], gold=[_MOTION_A], cost_usd=None)])


_REPORT_PY = (Path(__file__).parent.parent / "experiments"
              / "2026-10-07-motion-model-sweep" / "report.py")


def _load_report_module():
    spec = importlib.util.spec_from_file_location("motion_sweep_report", _REPORT_PY)
    assert spec is not None and spec.loader is not None, f"Cannot load {_REPORT_PY}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_report_mod = _load_report_module()
report = _report_mod.report

_FIXTURE_RESULTS_WITH_ALL_ROWS = {
    "combos": {
        "opencode-go/deepseek-v4.1-flash@default": {
            "text_f1": 0.9,
            "count_mae": 0.1,
            "field_acc": 0.8,
            "failure_rate": 0.0,
            "mean_cost": 0.0001,
            "extrapolated_2026": 0.2,
        },
        # Null field_acc (zero pairs matched) + 15% failures: high F1 but
        # DISQUALIFIED regardless of F1 (spec section 8).
        "opencode-go/qwen3.8-flash": {
            "text_f1": 0.95,
            "count_mae": 0.0,
            "field_acc": None,
            "failure_rate": 0.15,
            "mean_cost": 0.00005,
            "extrapolated_2026": 0.1,
        },
        "baseline": {
            "text_f1": 0.85,
            "count_mae": 0.2,
            "field_acc": 0.7,
            "failure_rate": 0.05,
            "mean_cost": None,
            "extrapolated_2026": None,
        },
    }
}


def test_report_carries_gradient_caveat(capsys):
    report(_FIXTURE_RESULTS_WITH_ALL_ROWS)
    out = capsys.readouterr().out
    assert "gradient" in out and "not testable" in out


def test_report_null_field_acc_disqualified_and_delta(capsys):
    report(_FIXTURE_RESULTS_WITH_ALL_ROWS)
    out = capsys.readouterr().out
    assert "n/a" in out  # null field_acc (and null baseline costs)
    assert "DISQUALIFIED" in out  # 15% failures despite F1 0.95
    assert "+0.0500" in out  # 0.90 - 0.85 baseline ΔF1
