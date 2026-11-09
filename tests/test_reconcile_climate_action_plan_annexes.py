import openpyxl
import pytest
from scripts.reconcile_climate_action_plan_annexes import (
    load_reference, normalise, reconcile, edition_of,
)


def _workbook(path, sheets):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for title, rows in sheets.items():
        ws = wb.create_sheet(title)
        ws.append(["Chapter", "Theme", "Measure", "Action Number", "Action"])
        for ref, text in rows:
            ws.append(["c", "t", "m", ref, text])
    wb.save(path)


def test_edition_of_uses_code_year():
    assert edition_of("EL/24/6/A") == 2024
    assert edition_of("not a code") is None


def test_normalise_ignores_case_spacing_and_ligatures():
    assert normalise("Ofﬁce  of\nthe  State") == normalise("office of the state")


def test_load_reference_groups_by_code_year_and_strips_flags(tmp_path):
    _workbook(tmp_path / "a.xlsx", {
        "Q1": [("CN/23/1", "Do A"), (" EL/24/6/A ", "Do B")],
        "Legacy": [("CN/23/1", "Do A"), ("blank?", "x"), (None, "y")],
    })
    ref = load_reference(tmp_path)
    assert set(ref[2023]) == {"CN/23/1"}
    assert set(ref[2024]) == {"EL/24/6/A"}
    assert ref[2023]["CN/23/1"]["text"] == "Do A"
    assert ref[2023]["CN/23/1"]["sources"] == ["a.xlsx:Q1", "a.xlsx:Legacy"]


def test_reconcile_classifies_missing_mismatch_and_extra():
    reference = {"A/23/1": {"text": "Alpha plan", "sources": ["x"]},
                 "A/23/2": {"text": "Beta plan", "sources": ["x"]},
                 "A/23/3": {"text": "Gamma plan", "sources": ["x"]}}
    extracted = {"A/23/1": "Alpha plan", "A/23/3": "Something entirely different",
                 "A/23/9": "Extra"}
    r = reconcile(extracted, reference)
    assert r["missing"] == ["A/23/2"]
    assert [m["reference"] for m in r["text_mismatches"]] == ["A/23/3"]
    assert r["extra"] == ["A/23/9"]
    assert r["matched"] == 1


def test_reconcile_accepts_prefix_when_one_text_contains_the_other():
    reference = {"A/23/1": {"text": "Alpha plan for water", "sources": []}}
    r = reconcile({"A/23/1": "Alpha plan for water."}, reference)
    assert r["text_mismatches"] == []


def test_dash_text_is_accepted_when_xlsx_repeats_the_parent_text():
    reference = {"A/23/1/A": {"text": "Alpha plan", "sources": []},
                 "A/23/2/A": {"text": "Not the parent", "sources": []}}
    extracted = {"A/23/1": "Alpha plan", "A/23/1/A": "-",
                 "A/23/2": "Beta", "A/23/2/A": "-"}
    r = reconcile(extracted, reference)
    assert r["placeholder_text"] == ["A/23/1/A"]
    assert [m["reference"] for m in r["text_mismatches"]] == ["A/23/2/A"]
