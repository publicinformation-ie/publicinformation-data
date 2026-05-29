import datetime
import json
import pytest
from steps.normalize_disclosure_cells.process import (
    _normalize_cell,
    STEP_NAME,
)
from scripts.file_utils import read_json, write_json, IncrementalWriter


# ── _normalize_cell unit tests ────────────────────────────────────────────────

def test_normalize_cell_strip_whitespace():
    val, rules = _normalize_cell("xlsx", "  FOI-001  ")
    assert val == "FOI-001"
    assert rules == ["strip_whitespace"]


def test_normalize_cell_pdf_newline_to_space():
    val, rules = _normalize_cell("pdf", "Request\nID")
    assert val == "Request ID"
    assert "newline_to_space" in rules


def test_normalize_cell_pdf_cid_known():
    # (cid:9) is a tab-like glyph — should be stripped; newline then replaced
    val, rules = _normalize_cell("pdf", "(cid:9)\nFOI-001")
    assert val == "FOI-001"
    assert "cid_stripped" in rules
    assert "newline_to_space" in rules
    assert "strip_whitespace" in rules


def test_normalize_cell_pdf_cid_unknown():
    # (cid:415) is a font-specific glyph — also stripped
    val, rules = _normalize_cell("pdf", "foo(cid:415)bar")
    assert val == "foobar"
    assert rules == ["cid_stripped"]


def test_normalize_cell_pdf_collapse_spaces():
    # Removing a CID with space before and after leaves adjacent spaces
    val, rules = _normalize_cell("pdf", "Hello (cid:415)  World")
    assert val == "Hello World"
    assert "cid_stripped" in rules
    assert "collapse_spaces" in rules


def test_normalize_cell_non_string_passthrough():
    assert _normalize_cell("pdf", None) == (None, [])
    assert _normalize_cell("pdf", 42) == (42, [])
    assert _normalize_cell("xlsx", datetime.date(2024, 1, 1)) == (datetime.date(2024, 1, 1), [])


def test_normalize_cell_xlsx_newline_preserved():
    # Excel newlines are intentional multi-line content — must not be touched
    val, rules = _normalize_cell("xlsx", "line1\nline2")
    assert val == "line1\nline2"
    assert rules == []


def test_normalize_cell_rules_applied_list():
    # Multi-rule case: CID stripped → newline replaced → spaces collapsed → leading/trailing stripped
    val, rules = _normalize_cell("pdf", "(cid:9)\nFOI-001-2026  ")
    assert val == "FOI-001-2026"
    assert rules == ["cid_stripped", "newline_to_space", "collapse_spaces", "strip_whitespace"]
