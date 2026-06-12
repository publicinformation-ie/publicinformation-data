import importlib.util
from pathlib import Path

_RUNPY = Path(__file__).parents[1] / "experiments/2026-06-09-pdf-extraction-comparison/run.py"
spec = importlib.util.spec_from_file_location("exp_run", _RUNPY)
assert spec is not None and spec.loader is not None
_run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_run)  # type: ignore[union-attr]

apply_merge_groups = _run.apply_merge_groups
row_to_text = _run.row_to_text
score_extractor = _run.score_extractor


# --- apply_merge_groups ---

def test_apply_merge_groups_no_merges():
    rows = [["A", "B"], ["C", "D"]]
    assert apply_merge_groups(rows, []) == [["A", "B"], ["C", "D"]]


def test_apply_merge_groups_single_pair():
    rows = [
        ["FOI/001", "15/01/2017", "Granted", None],
        [None, None, "in part", None],
    ]
    result = apply_merge_groups(rows, [[0, 1]])
    assert result == [["FOI/001", "15/01/2017", "Granted in part", None]]


def test_apply_merge_groups_multiple_groups():
    rows = [
        ["H1", "H2"],          # idx 0: header part 1
        ["/Ref", None],        # idx 1: header part 2 — merged into 0
        ["R1", "data"],        # idx 2: normal row
        ["R2", "more"],        # idx 3: normal row
        [None, "text"],        # idx 4: continuation — merged into 3
    ]
    result = apply_merge_groups(rows, [[0, 1], [3, 4]])
    assert len(result) == 3
    assert result[0] == ["H1 /Ref", "H2"]
    assert result[1] == ["R1", "data"]
    assert result[2] == ["R2", "more text"]


def test_apply_merge_groups_three_way_merge():
    rows = [
        ["A", None],
        [None, "B"],
        ["C", None],
    ]
    result = apply_merge_groups(rows, [[0, 1, 2]])
    assert len(result) == 1
    assert result[0] == ["A C", "B"]


def test_apply_merge_groups_skips_already_merged():
    """Rows listed as continuations must not appear in output."""
    rows = [["A", "1"], ["B", None], ["C", "2"]]
    result = apply_merge_groups(rows, [[0, 1]])
    assert len(result) == 2
    assert result[0] == ["A B", "1"]
    assert result[1] == ["C", "2"]


# --- row_to_text ---

def test_row_to_text_all_populated():
    assert row_to_text(["FOI/001", "15/01/2017", "Granted"]) == "FOI/001 15/01/2017 Granted"


def test_row_to_text_with_nulls():
    assert row_to_text([None, "15/01/2017", None, "Granted"]) == "15/01/2017 Granted"


def test_row_to_text_all_null():
    assert row_to_text([None, None, None]) == ""


def test_row_to_text_normalises_whitespace():
    assert row_to_text(["A  B", "  C  "]) == "A B C"


# --- score_extractor ---

def test_score_extractor_perfect_match():
    truth = [["FOI/001", "Granted"], ["FOI/002", "Refused"]]
    extracted = [["FOI/001", "Granted"], ["FOI/002", "Refused"]]
    result = score_extractor(truth, extracted)
    assert result["row_count_match"] is True
    assert result["exact_row_match"] is True
    assert result["exact_matches"] == 2


def test_score_extractor_wrong_row_count():
    truth = [["FOI/001", "Granted"], ["FOI/002", "Refused"]]
    extracted = [["FOI/001", "Granted"]]
    result = score_extractor(truth, extracted)
    assert result["row_count_match"] is False
    assert result["exact_row_match"] is False


def test_score_extractor_right_count_wrong_content():
    truth = [["FOI/001", "Granted"]]
    extracted = [["FOI/999", "Refused"]]
    result = score_extractor(truth, extracted)
    assert result["row_count_match"] is True
    assert result["exact_row_match"] is False
    assert result["exact_matches"] == 0


def test_score_extractor_partial_match():
    truth = [["A"], ["B"], ["C"]]
    extracted = [["A"], ["B"], ["Z"]]
    result = score_extractor(truth, extracted)
    assert result["row_count_match"] is True
    assert result["exact_row_match"] is False
    assert result["exact_matches"] == 2


def test_score_extractor_order_independent():
    """Exact row match checks presence, not position."""
    truth = [["FOI/001", "Granted"], ["FOI/002", "Refused"]]
    extracted = [["FOI/002", "Refused"], ["FOI/001", "Granted"]]
    result = score_extractor(truth, extracted)
    assert result["exact_row_match"] is True
