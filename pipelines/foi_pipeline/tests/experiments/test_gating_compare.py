import json

import pytest

from experiments.gating.compare import (GOLD_KEY, agreement, calibrate, gold_score,
                                        independent, load_gold)

HDR = ["Ref", "Date", "Request", "Decision", "Notes"]
T = [HDR] + [[f"FOI-{i:03d}", f"0{i}/01/2020", f"Request about topic {i}", f"Granted {i}", f"Note {i}"]
             for i in range(1, 5)]


def _copy(t):
    return [list(r) for r in t]


def test_identical_tables_agree_fully():
    assert agreement(T, T) == 1.0


def test_one_changed_cell_in_4x5_table():
    t2 = _copy(T)
    t2[2][3] = "Refused"
    assert agreement(T, t2) == pytest.approx(19 / 20)


def test_all_empty_column_is_ignored():
    t2 = [r[:2] + [""] + r[2:] for r in T]
    t3 = [r[:2] + [None] + r[2:] for r in T]
    assert agreement(T, t2) == 1.0
    assert agreement(T, t3) == 1.0


def test_whitespace_and_bullet_normalised():
    t2 = _copy(T)
    t2[1][2] = "  Request   about topic 1 "
    t2[2][4] = "Note 2"
    t1 = _copy(T)
    t1[2][4] = " Note 2"
    t2[2][4] = "• Note 2"
    assert agreement(t1, t2) == 1.0
    assert agreement(T, t2[:2] + [T[2]] + t2[3:]) == 1.0


def test_different_column_counts_give_none():
    t2 = [r[:2] + [r[2][:8], r[2][8:]] + r[3:] for r in T]
    assert agreement(T, t2) is None


def test_fewer_than_three_keyed_rows_gives_none():
    assert agreement(T[:3], T[:3]) is None
    nokey = [HDR] + [["alpha", "beta", "gamma", "delta", f"word {i}"] for i in range(5)]
    assert agreement(nokey, nokey) is None


def test_none_input_gives_none():
    assert agreement(None, T) is None
    assert agreement(T, None) is None


def test_shifted_columns_score_low():
    # shift every data cell one column right, keeping the column count
    sh = [HDR] + [["x"] + r[:-1] for r in T[1:]]
    assert agreement(T, sh) < 0.5


def test_independent_needs_two_known_distinct_families():
    assert independent("camelot", "docling")
    assert not independent("camelot", "camelot")
    assert not independent(None, "docling")
    assert not independent("camelot", None)


def test_calibrate_picks_lowest_safe_threshold():
    s = [dict(agreement=0.93, gold_a=0.85, gold_b=0.99), dict(agreement=0.97, gold_a=0.96, gold_b=0.98)]
    r = calibrate(s)
    assert r["threshold"] == pytest.approx(0.94)
    assert r["pairs"] == 2
    assert len(r["violations_at_0_90"]) == 1


def test_calibrate_none_when_no_threshold_qualifies():
    s = [dict(agreement=0.995, gold_a=0.5, gold_b=0.99)]
    assert calibrate(s)["threshold"] is None
    assert calibrate([])["threshold"] == pytest.approx(0.80)


def test_gold_score_none_rows_is_zero():
    assert gold_score(None, {"rows": T[1:]}) == 0.0


def test_gold_score_perfect_and_partial():
    g = {"rows": T[1:]}
    assert GOLD_KEY == "normalised"
    assert gold_score(T, g) == 1.0
    t2 = _copy(T)
    t2[1][3] = "zzz"
    assert gold_score(t2, g) == pytest.approx(19 / 20)


def test_load_gold(tmp_path):
    (tmp_path / "abc.json").write_text(json.dumps({"rows": T[1:]}))
    assert load_gold("abc", tmp_path)["rows"] == T[1:]
    assert load_gold("missing", tmp_path) is None
