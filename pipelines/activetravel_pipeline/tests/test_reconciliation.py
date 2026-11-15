"""Section and summary reconciliation: what may be published, and what is withheld."""
import copy

import pytest

from conftest import rows_from_pages
from steps.classify_grant_rows.process import run as classify_run
from steps.normalize_grant_amounts.process import run as normalize_run
from steps.reconcile_sections.process import run as reconcile_run
from steps.reconcile_summary.process import run as summary_run
from steps.resolve_recipients.process import run as resolve_run
from steps.segment_funding_streams.process import run as segment_run


def prepared_document(real_pages, document_id: str, year: int, pages: list[int]) -> dict:
    """Run classification, amounts, segmentation and recipient resolution."""
    rows, _ = rows_from_pages(real_pages, document_id, year, pages)
    classified, _ = classify_run({"rows": rows})
    normalized, _ = normalize_run({"rows": classified["rows"]}, repairs=[])
    segmented, _ = segment_run({"rows": normalized["rows"]})
    resolved, errors = resolve_run({**segmented, "documents": []})
    assert errors == []
    return resolved


def withheld_streams(output: dict) -> set[tuple[str, str]]:
    return {(section["section_id"], stream)
            for section in output["sections"]
            for stream in section["withheld_streams"]}


def test_a_reconciling_stream_is_published_and_a_short_one_is_withheld(real_pages):
    "2026 Wicklow: active travel adds up to €7,000,000; the other-streams block prints only €115,974 of its €615,974 subtotal."
    document = prepared_document(real_pages, "nta-active-travel-2026", 2026, [21, 22, 23])
    output, errors = reconcile_run(document, repairs=[])

    section = output["sections"][0]
    assert section["withheld_streams"] == ["other_nta_streams"]
    assert withheld_streams(output) == {(section["section_id"], "other_nta_streams")}
    published = [row for row in output["rows"] if row.get("section_id")]
    assert {row["funding_stream"] for row in published} == {"active_travel"}
    assert sum(row["amount_eur"] for row in published) == 7000000

    assert len(errors) == 1
    error = errors[0]
    assert error["error_type"] == "SectionReconciliationMismatch"
    assert error["context"]["funding_stream"] == "other_nta_streams"
    assert error["context"]["extracted_eur"] == 115974
    assert error["context"]["declared_eur"] == 615974
    assert error["context"]["delta_eur"] == -500000
    assert error["context"]["recipient"] == "Wicklow County Council"


def test_a_one_euro_difference_withholds_the_stream():
    "Every stream is checked to the euro: a rounding error in the source is a mismatch."
    rows = [_project("AAAA/25/0001", "Scheme A", 1000, row_index=0)]
    section = _section(total=1001, rows=rows)
    output, errors = reconcile_run({"rows": rows, "sections": [section]}, repairs=[])
    assert output["rows"] == []
    assert errors[0]["context"]["delta_eur"] == -1
    assert "one euro" not in errors[0]["error_message"]  # the numbers speak for themselves


def test_a_duplicated_block_sequence_does_not_reconcile():
    "Two runs of the same rows double-count and must be caught."
    rows = [_project("AAAA/25/0001", "Scheme A", 1000, row_index=0),
            _project("AAAA/25/0001", "Scheme A", 1000, row_index=1)]
    section = _section(total=1000, rows=rows)
    output, errors = reconcile_run({"rows": rows, "sections": [section]}, repairs=[])
    assert output["rows"] == []
    assert errors[0]["context"]["extracted_eur"] == 2000
    assert errors[0]["context"]["declared_eur"] == 1000


def test_a_drop_repair_removes_the_row_and_reports_itself():
    rows = [_project("AAAA/25/0001", "Scheme A", 1000, row_index=0),
            _project("AAAA/25/0001", "Scheme A", 1000, row_index=1)]
    section = _section(total=1000, rows=rows)
    repairs = [{"document_id": "doc", "page": 1, "row_index": 1, "action": "drop_row",
                "reason": "the row is printed twice", "source_method": "manual",
                "overridden": True}]
    output, errors = reconcile_run({"rows": rows, "sections": [section]}, repairs=repairs)
    assert len(output["rows"]) == 1
    assert [e["error_type"] for e in errors] == ["RowRepairApplied"]
    assert output["sections"][0]["withheld_streams"] == []


def test_a_missing_declared_total_withholds_everything():
    rows = [_project("AAAA/25/0001", "Scheme A", 1000, row_index=0)]
    section = _section(total=None, rows=rows)
    output, errors = reconcile_run({"rows": rows, "sections": [section]}, repairs=[])
    assert output["rows"] == []
    assert "no declared total" in errors[0]["error_message"]


def test_money_declared_for_an_unprinted_block_withholds_only_that_stream(real_pages):
    "2025 Kerry declares €3,350,000 but prints €2,750,000 of active-travel rows and nothing else."
    rows = [_project("KY/21/0010", "Rock Road", 2750000, row_index=0)]
    section = _section(total=3350000, rows=rows, block_declared=2750000)
    output, errors = reconcile_run({"rows": rows, "sections": [section]}, repairs=[])
    assert len(output["rows"]) == 1
    assert output["sections"][0]["withheld_streams"] == ["other_nta_streams"]
    assert errors[0]["context"]["declared_eur"] == 600000
    assert errors[0]["context"]["extracted_eur"] == 0


def _summary_document(real_pages, declared: str) -> dict:
    "2026 Wicklow's reconciled section plus one synthetic per-recipient summary line."
    document = prepared_document(real_pages, "nta-active-travel-2026", 2026, [21, 22, 23])
    reconciled, _ = reconcile_run(document, repairs=[])
    reconciled["documents"] = [
        {"document_id": "nta-active-travel-2026", "year": 2026,
         "kinds": ["project_table", "recipient_summary"]},
        {"document_id": "nta-active-travel-2022-annex-1", "year": 2022,
         "kinds": ["programme_summary"]},
    ]
    reconciled["summary_rows"] = [{
        "document_id": "nta-active-travel-2026", "year": 2026, "page": 1, "row_index": 2,
        "part": "recipient_summary",
        "cells": ["Wicklow County Council", declared, "500,000"],
    }]
    return reconciled


def test_a_matching_summary_line_confirms_the_section(real_pages):
    document = _summary_document(real_pages, "7,000,000")
    output, errors = summary_run(document)
    assert errors == []
    assert output["metadata"]["comparisons"] == 1
    assert len(output["rows"]) > 0


def test_a_mismatching_summary_line_withholds_the_active_travel_stream(real_pages):
    document = _summary_document(real_pages, "7,000,001")
    output, errors = summary_run(document)
    assert [e["error_type"] for e in errors] == ["SummaryMismatch"]
    assert errors[0]["context"]["declared_eur"] == 7000001
    assert [row for row in output["rows"] if row.get("section_id")] == []
    assert output["sections"][0]["withheld_streams"] == ["other_nta_streams", "active_travel"]


def test_the_programme_summary_document_is_skipped_not_compared(real_pages):
    document = _summary_document(real_pages, "7,000,000")
    output, errors = summary_run(document)
    skipped = {item["document_id"]: item["reason"] for item in output["summary_skipped"]}
    assert "nta-active-travel-2022-annex-1" in skipped
    assert "programme budget" in skipped["nta-active-travel-2022-annex-1"]


def test_a_non_local_authority_summary_line_is_excluded_from_the_comparison(real_pages):
    document = _summary_document(real_pages, "7,000,000")
    document["summary_rows"].append({
        "document_id": "nta-active-travel-2026", "year": 2026, "page": 2, "row_index": 20,
        "part": "recipient_summary",
        "cells": ["Campuses, Hospitals and other non Local Authority projects", "6,390,000", ""],
    })
    output, errors = summary_run(document)
    assert errors == []
    assert output["metadata"]["comparisons"] == 1


def test_a_summary_recipient_with_no_project_table_is_reported(real_pages):
    document = _summary_document(real_pages, "7,000,000")
    document["summary_rows"].append({
        "document_id": "nta-active-travel-2026", "year": 2026, "page": 1, "row_index": 9,
        "part": "recipient_summary", "cells": ["Longford County Council", "3,000,000", "500,000"],
    })
    output, errors = summary_run(document)
    assert [e["error_type"] for e in errors] == ["SummaryMismatch"]
    assert e_context(errors[0]) == "Longford County Council"


def e_context(error: dict) -> str:
    return error["context"]["recipient"]


def _project(code: str, name: str, amount: int, *, row_index: int,
             document_id: str = "doc", year: int = 2025) -> dict:
    return {
        "document_id": document_id, "year": year, "page": 1, "row_index": row_index,
        "part": "project_table",
        "cells": [code, name, f"€ {amount:,}"],
        "kind": "project",
        "detail": {"code": code, "name": name, "amount_cell": f"€ {amount:,}"},
        "amount_eur": amount,
        "section_id": "doc#0", "section_heading": "Test County Council",
        "block_index": 0, "funding_stream": "active_travel",
        "recipient_name": "Test County Council", "recipient_kind": "local_authority",
        "recipient_slug": "test-county-council", "public_body_id": 1000,
        "public_body": "https://data.publicinformation.ie/body/test-county-council",
    }


def _section(total: int | None, rows: list[dict], *, stream: str = "active_travel",
             block_declared: int | None = None) -> dict:
    blocks = [{"block_index": 0, "funding_stream": stream, "row_count": len(rows),
               "declared": None if block_declared is None else {
                   "label": "total", "amount_eur": block_declared, "page": 1,
                   "row_index": 98}}]
    return {
        "section_id": "doc#0", "document_id": "doc", "year": 2025, "heading": "Test County Council",
        "title": None, "first_page": 1, "block_count": 1,
        "section_total": None if total is None else {
            "label": "total", "amount_eur": total, "page": 1, "row_index": 99},
        "blocks": blocks,
        "recipient_name": "Test County Council", "recipient_kind": "local_authority",
        "recipient_slug": "test-county-council", "public_body_id": 1000,
        "public_body": "https://data.publicinformation.ie/body/test-county-council",
    }
