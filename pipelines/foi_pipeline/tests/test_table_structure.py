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


def test_fingal_2016_continuations_are_fragments():
    assert score_table(load("fingal_2016_continuations")).fragment_share > 0.05


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


@pytest.mark.parametrize("name", NAMES)
def test_fragment_metric_agrees_with_eval_flag(name):
    rows = load(name)
    score = score_table(rows)
    assert (score.fragment_share > 0) == has_newline_split_row(rows)


def test_default_thresholds_calibrated_values():
    # Calibrated in the extractor bake-off (small gold set); see bakeoff.md.
    assert DEFAULT_THRESHOLDS.min_width_uniformity == 0.85
    assert DEFAULT_THRESHOLDS.max_fragment_share == 0.10
    assert DEFAULT_THRESHOLDS.max_split_word_rate == 0.02
    assert DEFAULT_THRESHOLDS.max_repeated_header_share == 0.07
