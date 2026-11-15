"""Anchor-bounded segmentation: sections, blocks and funding streams."""
import pytest

from conftest import rows_from_pages
from steps.classify_grant_rows.process import run as classify_run
from steps.normalize_grant_amounts.process import run as normalize_run
from steps.segment_funding_streams.process import run as segment_run


def prepare(rows: list[dict]) -> list[dict]:
    classified, _ = classify_run({"rows": rows})
    normalized, _ = normalize_run({"rows": classified["rows"]}, repairs=[])
    return normalized["rows"]


def segment(real_pages, document_id: str, year: int, pages: list[int]):
    rows, _ = rows_from_pages(real_pages, document_id, year, pages)
    normalized = prepare(rows)
    output, errors = segment_run({"rows": normalized})
    return output, errors, normalized


def project_rows(output: dict, section_id: str, block_index: int | None = None) -> list[dict]:
    rows = [row for row in output["rows"]
            if row.get("section_id") == section_id and row["kind"] == "project"]
    if block_index is None:
        return rows
    return [row for row in rows if row.get("block_index") == block_index]


def test_two_anchor_blocks_become_active_travel_then_other_streams(real_pages):
    output, errors, normalized = segment(real_pages, "nta-active-travel-2026", 2026, [3, 7])
    assert [s["heading"] for s in output["sections"]] == ["Dublin City Council"]
    section = output["sections"][0]
    assert section["block_count"] == 2
    assert section["section_total"]["amount_eur"] == 42650000
    assert section["blocks"][1]["declared"]["amount_eur"] == 6700000
    assert {row["funding_stream"] for row in project_rows(output, section["section_id"], 0)} == {
        "active_travel"}
    assert {row["funding_stream"] for row in project_rows(output, section["section_id"], 1)} == {
        "other_nta_streams"}


def test_a_second_block_with_no_divider_heading_is_still_other_streams(real_pages):
    "2026 Wicklow: page 23's block opens with rows only; its anchors bracket it."
    output, errors, normalized = segment(real_pages, "nta-active-travel-2026", 2026, [21, 22, 23])
    assert [s["heading"] for s in output["sections"]] == ["Wicklow County Council"]
    section = output["sections"][0]
    assert section["section_total"]["amount_eur"] == 7615974
    other = project_rows(output, section["section_id"], 1)
    assert other and {row["page"] for row in other} == {23}
    assert {row["funding_stream"] for row in other} == {"other_nta_streams"}
    assert sum(row["amount_eur"] for row in other) == 115974
    assert section["blocks"][1]["declared"]["amount_eur"] == 615974
    assert errors == []


def test_a_heading_less_section_is_kept_so_the_prefix_can_attribute_it(real_pages):
    "2026 Galway City has no Table A title and no heading on pages 35-37."
    output, errors, normalized = segment(real_pages, "nta-active-travel-2026", 2026, [36, 37])
    sections = output["sections"]
    assert len(sections) == 1
    assert sections[0]["heading"] is None
    assert sections[0]["section_total"]["amount_eur"] == 11600000
    assert {row["funding_stream"] for row in project_rows(output, sections[0]["section_id"], 0)} == {
        "active_travel"}
    assert {row["funding_stream"] for row in project_rows(output, sections[0]["section_id"], 1)} == {
        "other_nta_streams"}


def test_a_block_that_opens_without_a_subtotal_is_bracketed_by_the_section_total(real_pages):
    "2024 Fingal: rows, then an empty Total, then the other-streams block."
    output, errors, normalized = segment(real_pages, "nta-active-travel-2024", 2024, [6, 7])
    section = output["sections"][0]
    assert section["heading"] is None
    assert section["section_total"]["amount_eur"] == 22000000
    assert section["blocks"][0]["declared"]["amount_eur"] is None
    active = project_rows(output, section["section_id"], 0)
    assert len(active) > 30
    assert {row["funding_stream"] for row in active} == {"active_travel"}


def test_an_anchor_with_its_label_in_the_second_column_still_closes_the_section(real_pages):
    "2026 Longford prints ['', 'Total:', '€ 3,000,000']."
    output, errors, normalized = segment(real_pages, "nta-active-travel-2026", 2026, [58])
    section = output["sections"][0]
    assert section["section_total"]["amount_eur"] == 3000000
    assert section["block_count"] == 1


def test_rows_that_no_declared_total_brackets_are_withheld(real_pages):
    "2024 Galway County's table has no total at all."
    output, errors, normalized = segment(real_pages, "nta-active-travel-2024", 2024, [34])
    assert output["sections"] == []
    assert [e["error_type"] for e in errors] == ["UnbracketedBlock"] * len(errors)
    assert all(row["withheld_reason"] == "UnbracketedBlock" for row in output["withheld_rows"])
    assert not [row for row in output["rows"] if "funding_stream" in row]


def test_a_missing_declared_total_leaves_rows_unassigned():
    "A synthetic section with no anchors at all: nothing may be published from it."
    rows = [
        {"document_id": "doc", "year": 2026, "page": 1, "row_index": 0,
         "part": "project_table", "cells": ["WCC/25/0001", "Scheme", "€ 10,000"]},
    ]
    normalized = prepare(rows)
    normalized[0]["amount_eur"] = 10000
    output, errors = segment_run({"rows": normalized})
    assert output["sections"] == []
    assert errors and errors[0]["error_type"] == "UnbracketedBlock"


def test_repeated_page_headings_do_not_start_a_new_section(real_pages):
    "2026 Dublin City repeats title + heading + column header on every page."
    rows, _ = rows_from_pages(real_pages, "nta-active-travel-2024", 2024, [4, 5, 6, 7])
    normalized = prepare(rows)
    output, _ = segment_run({"rows": normalized})
    headings = [section["heading"] for section in output["sections"]]
    assert headings == ["South Dublin County Council", None]
