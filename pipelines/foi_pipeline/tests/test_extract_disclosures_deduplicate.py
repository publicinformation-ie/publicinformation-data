import sys as _sys
from lib.file_utils import read_json as _read_json, write_json as _write_json
import steps.extract_disclosures_deduplicate.process as _proc


def _rec(body_id=1008, url="https://example.com/log.pdf", ref_id=None, desc=None, status=None):
    return {
        "public_body_id": body_id,
        "file_url": url,
        "foi_reference_id": ref_id,
        "date_received": None,
        "decision_date": None,
        "requester_type": None,
        "decision_status": status,
        "review_status": None,
        "related_request": None,
        "request_description": desc,
    }


def test_null_ref_blank_rows_are_deduplicated():
    """Repeated blank rows from PDF page headers/separators are collapsed."""
    blank = _rec()
    records = [blank, blank, blank]
    result, removed, kept = _proc.deduplicate_records(records)
    assert len(result) == 1
    assert removed == 2
    assert kept == 1


def test_null_ref_distinct_descriptions_are_kept():
    """Null-ref records with different request_description are kept as distinct."""
    records = [
        _rec(desc="Request about contracts"),
        _rec(desc="Request about salaries"),
        _rec(desc="Request about contracts"),  # true duplicate
    ]
    result, removed, kept = _proc.deduplicate_records(records)
    assert len(result) == 2
    assert removed == 1
    assert kept == 2


def test_null_ref_same_desc_different_files_are_kept():
    """Same content from two different source files is kept (may be distinct publications)."""
    records = [
        _rec(url="https://example.com/q1.pdf", desc="Request about budgets"),
        _rec(url="https://example.com/q2.pdf", desc="Request about budgets"),
    ]
    result, removed, kept = _proc.deduplicate_records(records)
    assert len(result) == 2
    assert removed == 0
    assert kept == 2


def test_null_ref_empty_string_treated_same_as_none():
    """Empty string fields are normalised to empty string; records with '' and None desc are deduplicated."""
    r1 = _rec(desc=None, status=None)
    r2 = _rec(desc="", status="")
    result, removed, _ = _proc.deduplicate_records([r1, r2])
    assert len(result) == 1
    assert removed == 1


def test_public_body_scoped_preserves_other_bodies(tmp_path, monkeypatch):
    out = tmp_path / "output.json"
    _write_json(out, {"metadata": {"step": "extract_disclosures_deduplicate"}, "results": [
        {"public_body_id": 1001, "foi_reference_id": "A", "marker": "keep"},
        {"public_body_id": 1002, "foi_reference_id": "OLD", "marker": "stale"},
    ]})
    inp = tmp_path / "input.json"
    _write_json(inp, {"results": [
        {"public_body_id": 1001, "foi_reference_id": "A"},
        {"public_body_id": 1002, "foi_reference_id": "B"},
        {"public_body_id": 1002, "foi_reference_id": "B"},  # duplicate within 1002
    ]})

    monkeypatch.setattr(_proc, "__file__", str(tmp_path / "process.py"))
    _sys.argv = ["process.py", "--input", str(inp), "--output", str(out),
                 "--public-body", "1002"]
    _proc.main()

    results = _read_json(out)["results"]
    assert {"public_body_id": 1001, "foi_reference_id": "A", "marker": "keep"} in results
    assert not any(r.get("marker") == "stale" for r in results)
    # the within-1002 duplicate is collapsed to one row
    assert sum(1 for r in results if r["public_body_id"] == 1002) == 1



def test_deduplicate_preserves_row_id_and_known_issues():
    record = _rec(body_id=1, ref_id="16/001")
    record["row_id"] = "abc123def456"
    record["known_issues"] = [
        {"field": "requester_type", "issue_type": "UnrecognizedRequesterType", "raw_value": "Alien"}
    ]
    record["missing_columns"] = ["review_status"]
    result, removed, kept = _proc.deduplicate_records([record])
    assert result[0]["row_id"] == "abc123def456"
    assert result[0]["known_issues"] == [
        {"field": "requester_type", "issue_type": "UnrecognizedRequesterType", "raw_value": "Alien"}
    ]
    assert result[0]["missing_columns"] == ["review_status"]
