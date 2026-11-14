import json
from pathlib import Path

import pytest

from lib.table_structure import (
    DEFAULT_THRESHOLDS,
    failed_checks,
    passes,
    score_table,
)
from steps.transform_disclosure_files.eval.evaluate import has_newline_split_row

FIXTURES = Path(__file__).parent / "fixtures" / "table_structure"
NAMES = [
    "rte_2018_shifted",
    "rte_q4_2019_split_words",
    "fingal_2016_continuations",
    "charities_regulator_2024_clean",
]


def load(name):
    return json.loads((FIXTURES / f"{name}.json").read_text())


def clean_rows(n=20):
    header = ["Reference Number", "Date of Request", "Description", "Requester", "Decision"]
    rows = [header]
    for i in range(n):
        rows.append([f"FOI/2020/{i:03d}", f"{(i % 28) + 1:02d}/01/2020",
                     "Information about housing", "Journalist", "Full Grant"])
    return rows


def test_clean_fixture_passes():
    score = score_table(load("charities_regulator_2024_clean"))
    assert passes(score), failed_checks(score)
    assert score.composite > 0.8


def test_rte_2018_shift_fails_uniformity():
    score = score_table(load("rte_2018_shifted"))
    assert "width_uniformity" in failed_checks(score)


def test_rte_q4_2019_split_words_detected():
    assert score_table(load("rte_q4_2019_split_words")).split_word_rate > 0.01


def test_fingal_2016_continuations_fold():
    """filter_phantom_rows merges these rows, so the gate no longer counts them."""
    assert score_table(load("fingal_2016_continuations")).fragment_share < 0.05


def test_wicklow_continuations_fold():
    score = score_table(load("wicklow_2023_continuations"))
    assert score.fragment_share == 0.0
    assert "fragment_share" not in failed_checks(score)


def test_two_cell_continuation_still_fragment():
    rows = clean_rows(20)
    for pos in (15, 10, 5):
        rows.insert(pos, ["", "", "more text", "", "tail"])
    assert score_table(rows).fragment_share > 0


def test_blank_separator_before_continuation_still_fragment():
    # filter_phantom_rows merges raw rows before dropping blanks, so a
    # continuation row after an all-blank row fills the blank row and survives
    # as a fragment. The scorer must follow the same order and see it.
    rows = clean_rows(20)
    for pos in (15, 10, 5):
        rows.insert(pos, ["", None, "", "", ""])
        rows.insert(pos + 1, ["", "", "", "", "tail"])
    assert score_table(rows).fragment_share > 0


def test_orphan_continuation_after_header_still_fragment():
    rows = clean_rows(20)
    rows.insert(1, ["", "", "orphan text 2020", "", ""])
    assert score_table(rows).fragment_share > 0


def test_non_string_continuation_not_folded():
    rows = clean_rows(20)
    for pos in (15, 10, 5):
        rows.insert(pos, ["", "", 12345, "", ""])
    assert score_table(rows).fragment_share > 0


def test_sparse_layout_not_folded():
    rows = [["Reference Number", "Date of Request", "Description", "Requester", "Decision"]]
    for i in range(20):
        row = [None] * 5
        row[i % 5] = f"value {i}"
        rows.append(row)
    assert score_table(rows).fragment_share > 0


def test_rows_above_header_are_ignored():
    rows = [["Title"], ["Subtitle"], ["Year"]] + clean_rows()
    score = score_table(rows)
    assert passes(score), failed_checks(score)


def test_bilingual_two_row_header_not_counted_as_fragments():
    rows = clean_rows(20)
    irish = ["Uimhir Thagartha", "Dáta", "Tuairisc", "Iarrthóir", "Cinneadh"]
    rows = [rows[0], irish] + rows[1:]
    score = score_table(rows)
    assert score.fragment_share == 0.0
    assert score.n_rows == 20


@pytest.mark.parametrize("rows", [[], [["a", "b"]], [["x"]] * 10])
def test_degenerate_tables_fail_without_raising(rows):
    score = score_table(rows)
    assert score.composite == 0.0
    assert not passes(score)


# The eval flag measures raw newline splits, while the gate now measures what is
# left after the filter_phantom_rows merge, so fixtures whose newline-split rows are
# single-cell continuations (fingal_2016, rte_2018_shifted) are excluded.
AGREEMENT_NAMES = [n for n in NAMES
                   if n not in ("fingal_2016_continuations", "rte_2018_shifted")]


@pytest.mark.parametrize("name", AGREEMENT_NAMES)
def test_fragment_metric_agrees_with_eval_flag(name):
    rows = load(name)
    score = score_table(rows)
    assert (score.fragment_share > 0) == has_newline_split_row(rows)


def test_default_thresholds_calibrated_values():
    # Calibrated in the extractor bake-off (small gold set); see bakeoff.md.
    assert DEFAULT_THRESHOLDS.min_width_uniformity == 0.92
    assert DEFAULT_THRESHOLDS.max_fragment_share == 0.08
    assert DEFAULT_THRESHOLDS.max_split_word_rate == 0.02
    assert DEFAULT_THRESHOLDS.max_repeated_header_share == 0.07


def test_optional_trailing_columns_uniform():
    score = score_table(load("qqi_2026_trailing_optional"))
    assert score.width_uniformity >= 0.92


def test_three_missing_trailing_cells_not_uniform():
    rows = [r + ["Note"] for r in clean_rows(20)]
    for i in range(1, 21):
        if i % 10 < 3:  # 30% of rows lose their last three cells
            rows[i] = rows[i][:3] + [""] * 3
    score = score_table(rows)
    assert score.modal_width == 6
    assert "width_uniformity" in failed_checks(score)


@pytest.mark.parametrize(
    "tok", ["WhatsApp", "EirGrid;", "(\u201cEirGrid\u201d)", "ComReg's", "BowelScreen", "ServiceNow,"]
)
def test_brand_tokens_not_split_words(tok):
    from lib.table_structure import _count_split_words

    assert _count_split_words([[f"request about {tok} usage"]])[0] == 0


def test_lowercase_join_still_split_word():
    from lib.table_structure import _count_split_words

    assert _count_split_words([["request dateAll usage"]])[0] == 1


def test_stvincents_brand_passes_split_check():
    assert "split_word_rate" not in failed_checks(score_table(load("stvincents_2018_brand")))


def _is_lone_year(row):
    import re
    cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
    return len(cells) == 1 and re.fullmatch(r"(19|20)\d{2}", cells[0]) is not None


def test_year_divider_rows_dropped():
    rows = load("body1505_2019_2025_year_dividers")
    stripped = [r for r in rows if not _is_lone_year(r)]
    assert len(stripped) < len(rows)
    assert score_table(rows) == score_table(stripped)


def test_year_like_values_in_records_kept():
    rows = clean_rows(10)
    base = score_table(rows).n_rows
    rows.append(["FOI-2019-001", "05/01/2019", "Information about housing", "Journalist", "Full Grant"])
    rows.append(["2019", "Business", "Information about roads", "Journalist", "Full Grant"])
    assert score_table(rows).n_rows == base + 2
