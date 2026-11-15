"""Extraction gate, row classification and amount normalisation."""
import pytest

from allocations import classify_row, parse_amount
from conftest import page_rows
from steps.classify_grant_rows.process import run as classify_run
from steps.extract_grant_tables.process import gate_page, page_part
from steps.normalize_grant_amounts.process import run as normalize_run


def test_gate_accepts_every_real_page(real_pages):
    for document in real_pages["documents"]:
        for page in document["pages"]:
            gate = gate_page(page["rows"])
            assert gate["accepted"], (
                f"{document['document_id']} page {page['page']} was rejected: "
                f"{gate['failed_checks']}")


def test_gate_records_the_page_shape(real_pages):
    gate = gate_page(page_rows(real_pages, "nta-active-travel-2026", 3))
    assert gate["checks"]["max_columns"] == 3
    assert gate["checks"]["rows"] > 0


def test_every_accepted_page_yields_three_column_rows(real_pages):
    "The three-column assumption is what the rest of the pipeline is written against."
    for document in real_pages["documents"]:
        for page in document["pages"]:
            widths = {len(row) for row in page["rows"]}
            assert widths <= {2, 3}, (
                f"{document['document_id']} page {page['page']} has rows of width {widths}")


def test_gate_rejects_a_table_with_the_wrong_column_count():
    rows = [
        ["Project Code", "Project Name", "2026 Allocation", "Comment"],
        ["AAAA/25/0001", "Scheme", "€ 1,000", "note"],
    ]
    gate = gate_page(rows)
    assert not gate["accepted"]
    assert "column_count" in gate["failed_checks"]


def test_gate_rejects_a_page_with_no_table():
    assert not gate_page([])["accepted"]
    assert gate_page([])["failed_checks"] == ["no_table"]


def test_gate_rejects_rows_that_vary_wildly_in_width():
    rows = [["Project Code", "Project Name", "2026 Allocation"]]
    rows += [["AAAA/25/0001", "Scheme"]] * 9
    rows += [["AAAA/25/0002", "Scheme", "€ 1,000"]]
    gate = gate_page(rows)
    assert not gate["accepted"]
    assert "width_uniformity" in gate["failed_checks"]


def test_page_part_reads_the_header_label(real_pages):
    assert page_part(page_rows(real_pages, "nta-active-travel-2026", 3)) == "project_table"
    assert page_part(page_rows(real_pages, "nta-active-travel-2025", 1)) == "recipient_summary"
    # A continuation page with no header of its own carries the previous part.
    assert page_part(page_rows(real_pages, "nta-active-travel-2024", 6)) is None


def _find(rows: list[list[str]], startswith: str) -> list[str]:
    return next(row for row in rows if row and row[0].startswith(startswith))


def test_each_row_kind_has_a_real_example(real_pages):
    page = page_rows(real_pages, "nta-active-travel-2026", 3)
    assert classify_row(page[1])[0] == "document_title"       # running title
    assert classify_row(page[0])[0] == "document_title"       # Table A: ...
    assert classify_row(page[3])[0] == "column_header"        # Project Code
    assert classify_row(page[2])[0] == "recipient_heading"    # Dublin City Council
    assert classify_row(page[4])[0] == "project"

    other_block = page_rows(real_pages, "nta-active-travel-2026", 7)
    assert classify_row(_find(other_block, "Allocations Through"))[0] == "stream_divider"
    assert classify_row(_find(other_block, "Subtotal"))[0] == "anchor"
    assert classify_row(_find(other_block, "Total"))[0] == "anchor"

    blank_page = page_rows(real_pages, "nta-active-travel-2026", 31)
    assert any(classify_row(row)[0] == "blank" for row in blank_page)

    footnote_page = page_rows(real_pages, "nta-active-travel-2025", 4)
    assert classify_row(_find(footnote_page, "*"))[0] == "footnote"


def test_anchor_amount_is_read_wherever_the_label_sits():
    kind, detail = classify_row(["", "Total:", "€ 3,000,000"])
    assert kind == "anchor"
    assert detail["label"] == "total"
    assert detail["label_column"] == 1
    assert detail["amount_cell"] == "€ 3,000,000"

    kind, detail = classify_row(["Total", "", "€ 21,900,000"])
    assert kind == "anchor" and detail["label"] == "total"

    kind, detail = classify_row(["Totals:", "", "€ 3,750,000"])
    assert kind == "anchor" and detail["label"] == "totals"


def test_header_label_survives_the_2022_type_setting():
    assert classify_row(["Project C ode:", "Project Name", "2022 Allocation"])[0] == "column_header"


def test_a_row_with_no_code_is_not_a_project_and_is_reported():
    rows = [{"document_id": "doc", "year": 2026, "page": 1, "row_index": 0,
             "part": "project_table", "cells": ["", "Some Scheme", "€ 5,000"]}]
    output, errors = classify_run({"rows": rows})
    assert output["rows"] == []
    assert len(output["unknown_rows"]) == 1
    assert [e["error_type"] for e in errors] == ["UnknownRowKind"]
    assert errors[0]["context"]["cells"] == ["", "Some Scheme", "€ 5,000"]


def test_classification_never_emits_a_row_without_a_kind(real_pages):
    rows = []
    index = 0
    for page in page_rows(real_pages, "nta-active-travel-2026", 3):
        rows.append({"document_id": "doc", "year": 2026, "page": 3, "row_index": index,
                     "part": "project_table", "cells": page})
        index += 1
    output, _ = classify_run({"rows": rows})
    assert {row["kind"] for row in output["rows"]} <= {
        "document_title", "column_header", "recipient_heading", "stream_divider",
        "project", "anchor", "footnote", "blank"}


@pytest.mark.parametrize("cell,value,repair", [
    ("€1,100,000", 1100000, False),
    ("€ 2 0,000,000", 20000000, True),
    ("€ 5 ,000", 5000, True),
    ("35,950,000", 35950000, False),
    ("1 60,000.00", 160000, True),
    ("10,000.00", 10000, False),
    ("400.00", 400, False),
    ("€ 0", 0, False),
], ids=[
    "currency_and_separators", "whitespace_split_digits", "space_before_separator",
    "no_currency_symbol", "whitespace_with_cents", "zero_cents_part",
    "whole_euro_sub_unit_amount", "zero_allocation",
])
def test_readable_amounts(cell, value, repair):
    result = parse_amount(cell)
    assert result["error"] is None, result
    assert result["value"] == value
    assert (result["repair"] is not None) is repair


@pytest.mark.parametrize("cell,error", [
    ("€ -", "no_digits"),
    ("", "empty"),
    ("ection€60,000", "letters"),
    ("c.) €200,000", "letters"),
    ("N/A*", "letters"),
    ("€ 1,234.56", "sub_euro_amount"),
    ("€ 12,34,000", "ambiguous_grouping"),
    ("€ 1,2", "ambiguous_grouping"),
], ids=[
    "dash_only", "empty_cell", "run_together_name_overflow",
    "name_fragment_in_cell", "not_applicable", "non_whole_euro",
    "misgrouped_separators", "short_group",
])
def test_rejected_amounts(cell, error):
    result = parse_amount(cell)
    assert result["value"] is None
    assert result["error"] == error


def test_whitespace_repairs_are_reported_and_row_is_kept():
    rows = [{"document_id": "doc", "year": 2026, "page": 1, "row_index": 0,
             "part": "project_table", "cells": ["AAAA/25/0001", "Scheme", "€ 2 0,000"],
             "kind": "project", "detail": {"code": "AAAA/25/0001", "name": "Scheme",
                                           "amount_cell": "€ 2 0,000"}}]
    output, errors = normalize_run({"rows": rows}, repairs=[])
    assert output["rows"][0]["amount_eur"] == 20000
    assert output["rows"][0]["amount_repair"] == {
        "field": "amount_eur", "raw": "€ 2 0,000", "value_used": 20000,
        "rule": "whitespace_inside_number",
    }
    assert errors == []


def test_unreadable_project_amount_withholds_the_row():
    rows = [{"document_id": "doc", "year": 2026, "page": 1, "row_index": 0,
             "part": "project_table", "cells": ["AAAA/25/0001", "Scheme", "€ -"],
             "kind": "project", "detail": {"code": "AAAA/25/0001", "name": "Scheme",
                                           "amount_cell": "€ -"}}]
    output, errors = normalize_run({"rows": rows}, repairs=[])
    assert output["rows"] == []
    assert output["withheld_rows"][0]["withheld_reason"] == "UnreadableAmount"
    assert errors[0]["error_type"] == "UnreadableAmount"
    assert errors[0]["context"]["raw_cell"] == "€ -"


def test_unreadable_anchor_is_kept_so_the_block_can_still_be_bracketed():
    rows = [{"document_id": "doc", "year": 2024, "page": 7, "row_index": 19,
             "part": "project_table", "cells": ["Total:", "", ""],
             "kind": "anchor", "detail": {"label": "total", "amount_cell": ""}}]
    output, errors = normalize_run({"rows": rows}, repairs=[])
    assert len(output["rows"]) == 1
    assert output["rows"][0]["amount_eur"] is None
    assert output["rows"][0]["amount_unreadable"] is True
    assert errors[0]["error_type"] == "UnreadableAmount"


def test_a_committed_repair_replaces_the_printed_cell_and_is_reported():
    rows = [{"document_id": "doc", "year": 2022, "page": 76, "row_index": 16,
             "part": "project_table", "cells": ["NTA", "Costs", "c.) €200,000"],
             "kind": "project", "detail": {"code": "NTA", "name": "Costs",
                                           "amount_cell": "c.) €200,000"}}]
    repairs = [{"document_id": "doc", "page": 76, "row_index": 16, "action": "set_amount",
                "value": 200000, "reason": "name overflows into the amount column",
                "source_method": "manual", "overridden": True}]
    output, errors = normalize_run({"rows": rows}, repairs=repairs)
    assert output["rows"][0]["amount_eur"] == 200000
    assert [e["error_type"] for e in errors] == ["RowRepairApplied"]
    assert errors[0]["context"]["value_used"] == 200000


class _FakePage:
    def __init__(self, text: str, table: list[list[str]]):
        self._text = text
        self._table = table

    def extract_text(self) -> str:
        return self._text

    def extract_table(self) -> list[list[str]]:
        return self._table


class _FakePdf:
    def __init__(self, pages: list[_FakePage]):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _extract_with(monkeypatch, pages):
    from steps.extract_grant_tables import process

    monkeypatch.setattr(process.pdfplumber, "open", lambda path: _FakePdf(pages))
    return process.run({"documents": [
        {"document_id": "doc", "year": 2026, "kinds": ["project_table"],
         "available": True, "cache_file": "cache/unused.pdf"}]})


def test_a_page_with_no_text_layer_is_reported(monkeypatch):
    output, errors = _extract_with(monkeypatch, [_FakePage("   ", [])])
    assert output["rows"] == []
    assert output["pages"][0]["failed_checks"] == ["no_text"]
    assert [error["error_type"] for error in errors] == ["PageHasNoText"]
    assert errors[0]["context"]["page"] == 1


def test_a_page_with_a_wrong_width_table_is_reported(monkeypatch):
    table = [
        ["Project Code", "Project Name", "2026 Allocation", "Comment"],
        ["AAAA/25/0001", "Scheme", "€ 1,000", "note"],
    ]
    output, errors = _extract_with(monkeypatch, [_FakePage("some text", table)])
    assert output["rows"] == []
    assert output["pages"][0]["failed_checks"] == ["column_count"]
    assert [error["error_type"] for error in errors] == ["TableStructureUnreliable"]
    assert errors[0]["context"]["failed_checks"] == ["column_count"]


def test_a_summary_page_keeps_its_rows_out_of_the_project_stream(monkeypatch):
    table = [
        ["Agency", "2026 AT Allocations", "BSEP allocations"],
        ["Dublin City Council", "35,950,000", "500,000"],
    ]
    output, errors = _extract_with(monkeypatch, [_FakePage("some text", table)])
    assert output["rows"] == []
    assert output["pages"][0]["part"] == "recipient_summary"
    assert [row["cells"][0] for row in output["summary_rows"]] == [
        "Agency", "Dublin City Council"]
