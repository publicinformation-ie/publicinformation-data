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


# ── process() integration tests ───────────────────────────────────────────────

def _make_input(results):
    return {"metadata": {"step": "transform_disclosure_files"}, "results": results}


BASE_FILE = {
    "public_body_id": 1001,
    "name": "Dept A",
    "disclosure_page_url": "https://dept-a.ie/disclosures/",
    "file_url": "https://assets.gov.ie/log.pdf",
    "file_type": "pdf",
    "sheet_name": "page 1",
}


def test_process_pdf_normalizes_cells(tmp_path, make_writer):
    rows = [
        ["(cid:9)\nRequest ID", "Date Rec'd"],
        ["\nFOI-001-2026", "  2026-01-01  "],
    ]
    item = {**BASE_FILE, "rows": rows}
    writer = make_writer(STEP_NAME, key_field="file_url")
    from steps.normalize_disclosure_cells.process import process
    process(_make_input([item]), tmp_path, writer)

    r = writer.results[0]
    assert r["rows"][0][0] == "Request ID"
    assert r["rows"][1][0] == "FOI-001-2026"
    assert r["rows"][1][1] == "2026-01-01"

    changes = read_json(tmp_path / "changes.json")
    assert len(changes) > 0
    # First cell: (cid:9)\nRequest ID → Request ID
    first = next(c for c in changes if c["before"] == "(cid:9)\nRequest ID")
    assert first["after"] == "Request ID"
    assert "cid_stripped" in first["rules_applied"]
    assert first["file_url"] == BASE_FILE["file_url"]
    assert first["file_type"] == "pdf"
    assert first["row_idx"] == 0
    assert first["col_idx"] == 0


def test_process_xlsx_strips_whitespace_only(tmp_path, make_writer):
    item = {
        **BASE_FILE,
        "file_url": "https://assets.gov.ie/log.xlsx",
        "file_type": "xlsx",
        "sheet_name": "Sheet1",
        "rows": [
            ["  Our Reference  ", "Date"],
            ["16/001", "line1\nline2"],
        ],
    }
    writer = make_writer(STEP_NAME, key_field="file_url")
    from steps.normalize_disclosure_cells.process import process
    process(_make_input([item]), tmp_path, writer)

    r = writer.results[0]
    assert r["rows"][0][0] == "Our Reference"
    assert r["rows"][1][1] == "line1\nline2"  # newline preserved in xlsx

    changes = read_json(tmp_path / "changes.json")
    assert all(c["rules_applied"] == ["strip_whitespace"] for c in changes)


def test_process_no_changes(tmp_path, make_writer):
    item = {
        **BASE_FILE,
        "rows": [["Request ID", "Date"], ["FOI-001-2026", "2026-01-01"]],
    }
    writer = make_writer(STEP_NAME, key_field="file_url")
    from steps.normalize_disclosure_cells.process import process
    process(_make_input([item]), tmp_path, writer)

    changes = read_json(tmp_path / "changes.json")
    assert changes == []


def test_process_incremental_resume(tmp_path, make_writer):
    # Simulate run 1: file A already processed, changes.json already written
    file_a_url = "https://assets.gov.ie/log-a.pdf"
    existing_result = {
        **BASE_FILE,
        "file_url": file_a_url,
        "rows": [["Request ID"]],
    }
    write_json(
        tmp_path / "output.json",
        {"metadata": {"step": STEP_NAME}, "results": [existing_result]},
    )
    write_json(
        tmp_path / "changes.json",
        [{
            "file_url": file_a_url,
            "file_type": "pdf",
            "row_idx": 0,
            "col_idx": 0,
            "rules_applied": ["strip_whitespace"],
            "before": " Request ID ",
            "after": "Request ID",
        }],
    )

    # Run 2: resume (force=False), process file B only
    file_b = {
        **BASE_FILE,
        "file_url": "https://assets.gov.ie/log-b.pdf",
        "rows": [[" Date "]],
    }
    file_a_input = {**BASE_FILE, "file_url": file_a_url, "rows": [[" Request ID "]]}
    writer = IncrementalWriter(tmp_path / "output.json", STEP_NAME, key_field="file_url", force=False)
    from steps.normalize_disclosure_cells.process import process
    process(_make_input([file_a_input, file_b]), tmp_path, writer)

    changes = read_json(tmp_path / "changes.json")
    urls_in_changes = [c["file_url"] for c in changes]
    assert file_a_url in urls_in_changes           # entry from run 1 preserved
    assert file_b["file_url"] in urls_in_changes   # new entry from run 2 appended
    assert len(writer.results) == 2                # both files in output


def test_process_rows_none_passthrough(tmp_path, make_writer):
    item = {
        **BASE_FILE,
        "file_url": "https://assets.gov.ie/log-norows.pdf",
        "rows": None,
    }
    writer = make_writer(STEP_NAME, key_field="file_url")
    from steps.normalize_disclosure_cells.process import process
    process(_make_input([item]), tmp_path, writer)

    # Item passed through unchanged
    assert len(writer.results) == 1
    assert writer.results[0]["rows"] is None

    # changes.json still exists (as empty list)
    changes = read_json(tmp_path / "changes.json")
    assert changes == []


import sys as _sys
from scripts.file_utils import read_json as _read_json, write_json as _write_json
import steps.normalize_disclosure_cells.process as _proc


def test_public_body_scoped_leaves_others_untouched(tmp_path, monkeypatch):
    out = tmp_path / "output.json"
    seeded = [
        {"public_body_id": 1001, "file_url": "https://a.ie/f.xlsx", "marker": "keep-1001"},
        {"public_body_id": 1002, "file_url": "https://b.ie/f1.xlsx", "marker": "old-1002-f1"},
        {"public_body_id": 1002, "file_url": "https://b.ie/f2.xlsx", "marker": "old-1002-f2"},
        {"public_body_id": 1003, "file_url": "https://c.ie/f.xlsx", "marker": "keep-1003"},
    ]
    _write_json(out, {"metadata": {"step": "normalize_disclosure_cells"}, "results": seeded})

    inp = tmp_path / "input.json"
    _write_json(inp, {"results": [
        {"public_body_id": 1001, "file_url": "https://a.ie/f.xlsx", "file_type": "xlsx",
         "rows": [["Ref", "Date"], ["001", "2024-01-01"]]},
        {"public_body_id": 1002, "file_url": "https://b.ie/f1.xlsx", "file_type": "xlsx",
         "rows": [["Ref", "Date"], ["002", "2024-02-01"]]},
        {"public_body_id": 1002, "file_url": "https://b.ie/f2.xlsx", "file_type": "xlsx",
         "rows": [["Ref", "Date"], ["003", "2024-03-01"]]},
        {"public_body_id": 1003, "file_url": "https://c.ie/f.xlsx", "file_type": "xlsx",
         "rows": [["Ref", "Date"], ["004", "2024-04-01"]]},
    ]})

    monkeypatch.setattr(_proc, "__file__", str(tmp_path / "process.py"))
    _sys.argv = ["process.py", "--input", str(inp), "--output", str(out),
                 "--public-body", "1002"]
    _proc.main()

    results = _read_json(out)["results"]
    body_map = {}
    for r in results:
        body_map.setdefault(r["public_body_id"], []).append(r)

    assert body_map[1001][0]["marker"] == "keep-1001"
    assert body_map[1003][0]["marker"] == "keep-1003"
    assert not any(r.get("marker", "").startswith("old-1002") for r in body_map.get(1002, []))
    assert _read_json(tmp_path / "dirty_ids.json") == [1002]
