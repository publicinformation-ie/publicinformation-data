import json
from pathlib import Path

import pytest

from lib.table_structure import (
    DEFAULT_THRESHOLDS,
    failed_checks,
    passes,
    score_table,
    StructureScore,
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
    from lib.table_structure import _count_run_together

    assert _count_run_together([[f"request about {tok} usage"]])[0] == 0


def test_lowercase_join_still_split_word():
    from lib.table_structure import _count_run_together

    assert _count_run_together([["request dateAll usage"]])[0] == 1


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


# --- Gate on structure, not text (openspec change foi-gate-on-structure-not-text) ---

def _rows_with_pair(left, right, n=20):
    rows = [["Reference Number", "Date of Request", "Requester", "Description", "Decision"]]
    for i in range(n):
        rows.append([f"FOI/2020/{i:03d}", f"{(i % 28) + 1:02d}/01/2020", left, right, "Full Grant"])
    return rows


@pytest.mark.parametrize("left,right", [
    ("Journalist", "all records relating to housing"),
    ("Client", "social housing"),
])
def test_adjacent_complete_values_not_split_words(left, right):
    score = score_table(_rows_with_pair(left, right))
    assert score.cross_cell_split_rate == 0.0
    assert score.split_word_rate == 0.0
    assert "split_word_rate" not in failed_checks(score)


def test_word_stub_across_boundary_counts():
    score = score_table(_rows_with_pair("S", "ummary of request"))
    assert score.cross_cell_split_rate > 0.02
    assert score.split_word_rate == score.cross_cell_split_rate
    assert "split_word_rate" in failed_checks(score)


def test_courts_adjacent_values_fixture_passes():
    score = score_table(load("courts_2017_q3_adjacent_values"))
    assert score.cross_cell_split_rate == 0.0
    assert passes(score), failed_checks(score)


def test_run_together_tokens_recorded_but_do_not_gate():
    rows = clean_rows(20)
    for row in rows[1:]:
        row[2] = "Information aboutHousing andThe roads"
    score = score_table(rows)
    assert score.run_together_rate > 0.02
    assert score.cross_cell_split_rate == 0.0
    assert "split_word_rate" not in failed_checks(score)
    assert passes(score), failed_checks(score)


def test_run_together_tokens_still_lower_composite():
    clean = score_table(clean_rows(20))
    rows = clean_rows(20)
    for row in rows[1:]:
        row[2] = "Information aboutHousing andThe roads"
    assert score_table(rows).composite < clean.composite


def test_repeated_header_every_page_passes_and_is_recorded():
    rows = load("repeated_header_every_page_2023")
    score = score_table(rows)
    assert score.repeated_header_share > 0
    assert "repeated_header_share" not in failed_checks(score)
    assert passes(score), failed_checks(score)


def test_repeated_header_rows_removed_from_data():
    rows = clean_rows(20)
    for pos in (15, 10, 5):
        rows.insert(pos, list(rows[0]))
    score = score_table(rows)
    assert score.n_rows == 20
    assert score.repeated_header_share == pytest.approx(3 / 23)
    assert passes(score), failed_checks(score)


def test_width_broken_table_still_fails_uniformity():
    rows = clean_rows(20)
    for i, row in enumerate(rows[1:], start=1):
        if i % 2:
            rows[i] = row[:3]
    assert "width_uniformity" in failed_checks(score_table(rows))


def test_from_dict_reads_legacy_score():
    from dataclasses import asdict
    from lib.table_structure import StructureScore

    score = score_table(clean_rows(20))
    legacy = {k: v for k, v in asdict(score).items()
              if k not in ("cross_cell_split_rate", "run_together_rate")}
    legacy["split_word_rate"] = 0.5
    rebuilt = StructureScore.from_dict(legacy)
    assert rebuilt.cross_cell_split_rate == 0.5
    assert rebuilt.run_together_rate == 0.0
    assert StructureScore.from_dict(asdict(score)) == score


# --- role-aware metrics (recorded, not gating) ---

def test_fingal_2023_shifted_contaminated():
    sc = score_table(load("fingal_2023_shifted"))
    assert not sc.roles_unmapped and sc.worst_role_contamination >= 0.5


def test_fingal_2024_camelot_stream_worse_than_alternative():
    c = load("fingal_2024_candidates")
    stream = score_table(c["camelot_stream"])
    best_other = min(score_table(c[n]).worst_role_contamination
                     for n in ("pymupdf", "mistral_cache"))
    assert stream.worst_role_contamination > best_other


def test_waterford_duplicate_status_role():
    rows = load("waterford_2025_clean")
    sc = score_table(rows, role_map={0: "foi_reference_id", 1: "decision_status",
                                     3: "date_received", 4: "decision_status"})
    assert sc.worst_role == "decision_status" and sc.worst_role_contamination >= 0.9


def test_waterford_after_alias_clean():
    assert score_table(load("waterford_2025_clean")).worst_role_contamination == 0.0


def test_rte_lattice_clean():
    sc = score_table(load("rte_q4_2020_lattice"))
    assert sc.worst_role_contamination <= 0.05 and sc.anchored_row_share >= 0.95


def test_unknown_vocab_not_contamination():
    sc = score_table(load("unknown_vocab_tudublin_2023"))
    assert not sc.roles_unmapped and sc.worst_role_contamination == 0.0


def test_ambiguous_value_not_contamination():
    rows = [["Reference", "Date Received", "Requester Type"]]
    rows += [[f"FOI/2024/{i:04d}", "01/02/2024", "Other"] for i in range(1, 11)]
    sc = score_table(rows)
    assert not sc.roles_unmapped and sc.worst_role_contamination == 0.0


def test_headerless_roles_unmapped():
    rows = [[f"FOI/2024/{i:04d}", "01/02/2024", "Journalist", "Records", "Granted"]
            for i in range(1, 11)]
    sc = score_table(rows)
    assert sc.roles_unmapped is True
    assert sc.role_contamination is None and sc.worst_role_contamination is None


def test_from_dict_legacy_without_role_fields():
    d = dict(n_rows=10, modal_width=5, width_uniformity=1.0, fragment_share=0.0,
             column_type_purity=1.0, split_word_rate=0.0, run_together_rate=0.0,
             repeated_header_share=0.0, composite=1.0)
    sc = StructureScore.from_dict(d)
    assert sc.roles_unmapped is True
    assert sc.worst_role_contamination is None and sc.anchored_row_share is None


def test_composite_unchanged():
    expected = {
        'body1505_2019_2025_year_dividers': 0.8,
        'charities_regulator_2024_clean': 0.992736077482,
        'courts_2017_q3_adjacent_values': 1.0,
        'fingal_2016_continuations': 0.961038961039,
        'qqi_2026_trailing_optional': 1.0,
        'repeated_header_every_page_2023': 0.764705882353,
        'rte_2018_p1_override_rows': 1.0,
        'rte_2018_shifted': 0.842936288089,
        'rte_q4_2019_split_words': 0.206611570248,
        'stvincents_2018_brand': 1.0,
        'wicklow_2023_continuations': 0.977142857143,
    }
    for name, value in expected.items():
        assert score_table(load(name)).composite == pytest.approx(value, abs=1e-9), name


def test_default_thresholds_role_values():
    assert (DEFAULT_THRESHOLDS.max_role_contamination,
            DEFAULT_THRESHOLDS.min_anchored_row_share) == (0.2, 0.8)


def test_fingal_2023_fails_role_check():
    assert "role_contamination" in failed_checks(score_table(load("fingal_2023_shifted")))


def test_rte_lattice_passes():
    score = score_table(load("rte_q4_2020_lattice"))
    assert passes(score), failed_checks(score)


def test_unknown_vocab_passes():
    score = score_table(load("unknown_vocab_tudublin_2023"))
    assert passes(score), failed_checks(score)


def test_unmapped_roles_do_not_gate():
    rows = [[f"x{i}", "foo", "bar"] for i in range(20)]  # headerless
    score = score_table(rows)
    assert score.roles_unmapped
    fc = failed_checks(score)
    assert "role_contamination" not in fc and "anchored_row_share" not in fc


def test_legacy_stored_score_does_not_gate_on_roles():
    score = score_table(clean_rows())
    legacy = {k: v for k, v in score.__dict__.items()
              if k not in ("role_contamination", "worst_role_contamination", "worst_role",
                           "anchored_row_share", "roles_unmapped")}
    s = StructureScore.from_dict(legacy)
    fc = failed_checks(s)
    assert "role_contamination" not in fc and "anchored_row_share" not in fc


def test_mapped_but_unmeasured_contamination_does_not_gate_it():
    score = StructureScore(**{**score_table(clean_rows()).__dict__,
                              "roles_unmapped": False, "worst_role_contamination": None,
                              "anchored_row_share": 0.1})
    fc = failed_checks(score)
    assert "role_contamination" not in fc and "anchored_row_share" in fc
