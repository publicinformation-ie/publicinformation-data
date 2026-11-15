import json
from pathlib import Path

import pytest

from experiments.gating.downstream import (
    FileOutcome, default_gate, item_for, reproduce, run_downstream, transform_index)
from experiments.gating.paths import STEPS

URL = "https://x.test/a.pdf"

CLEAN = [["Ref", "Date Received", "Request", "Requester", "Decision"],
         ["FOI-001", "12/01/2023", "Copies of invoices", "Journalist", "Granted"],
         ["FOI-002", "15/01/2023", "Staff numbers", "Business", "Refused"],
         ["FOI-003", "20/01/2023", "Minutes of meetings", "Journalist", "Part Granted"]]


def _item(url, rows, extractor="pdfplumber", file_type="pdf"):
    return {"public_body_id": 9, "name": "Test Body", "file_url": url, "file_type": file_type,
            "sheet_name": "page 1", "pdf_extractor": extractor, "rows": rows}


def _w(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj))


def _snapshot(root: Path) -> dict:
    return {p: (p.stat().st_mtime_ns, p.stat().st_size) for p in root.rglob("*") if p.is_file()}


def test_clean_table_passes_gate_and_yields_three_records(tmp_path):
    out = run_downstream([_item(URL, CLEAN)], "t", scratch=tmp_path)
    o = out[URL]
    assert isinstance(o, FileOutcome)
    assert o.gate_pass and o.failed_checks == [] and o.records == 3 and o.errors == 0
    assert o.error_classes == {} and not o.override_bound and o.score["n_rows"] == 3


def test_gate_failure_still_counts_records(tmp_path):
    def failing_gate(rows, role_map):
        score, _ = default_gate(rows, role_map)
        return score, ["role_contamination"]
    o = run_downstream([_item(URL, CLEAN)], "t", scratch=tmp_path, gate=failing_gate)[URL]
    assert not o.gate_pass and o.failed_checks == ["role_contamination"] and o.records == 3


def test_non_pdf_always_passes_gate(tmp_path):
    def failing_gate(rows, role_map):
        score, _ = default_gate(rows, role_map)
        return score, ["role_contamination"]
    o = run_downstream([_item("https://x.test/a.xlsx", CLEAN, file_type="xlsx")], "t",
                       scratch=tmp_path, gate=failing_gate)["https://x.test/a.xlsx"]
    assert o.gate_pass and o.records == 3


def test_errors_counted_and_classified(tmp_path):
    rows = [r[:] for r in CLEAN]
    rows[2][4] = "zzz qqq"
    o = run_downstream([_item(URL, rows)], "t", scratch=tmp_path)[URL]
    assert o.errors == 1 and sum(o.error_classes.values()) == 1


def test_steps_tree_is_untouched(tmp_path):
    before = _snapshot(STEPS)
    run_downstream([_item(URL, CLEAN)], "t", scratch=tmp_path)
    assert _snapshot(STEPS) == before


def test_variant_dir_is_emptied(tmp_path):
    (tmp_path / "t").mkdir()
    (tmp_path / "t" / "stale.json").write_text("{}")
    run_downstream([_item(URL, CLEAN)], "t", scratch=tmp_path)
    assert not (tmp_path / "t" / "stale.json").exists()


def _config_tree(root: Path, stored_extractor="pdfplumber") -> Path:
    _w(root / "transform_disclosure_files/output.json",
       {"metadata": {}, "results": [_item(URL, CLEAN, extractor=stored_extractor)]})
    _w(root / "extract_disclosures_canonicalize/column_mappings.json", {URL: {
        "source_method": "manual", "overridden": True, "column_mapping": {
            "0": "foi_reference_id", "1": "date_received", "2": "request_description",
            "3": "requester_type", "4": "decision_status"}}})
    return root


def test_override_bound_flag(tmp_path):
    cfg = _config_tree(tmp_path / "steps")
    moved = run_downstream([_item(URL, CLEAN, extractor="camelot")], "t",
                           scratch=tmp_path / "s", config_dir=cfg)[URL]
    same = run_downstream([_item(URL, CLEAN, extractor="pdfplumber")], "t",
                          scratch=tmp_path / "s", config_dir=cfg)[URL]
    other = run_downstream([_item("https://x.test/b.pdf", CLEAN, extractor="camelot")], "t",
                           scratch=tmp_path / "s", config_dir=cfg)["https://x.test/b.pdf"]
    assert moved.override_bound and not same.override_bound and not other.override_bound
    assert moved.records == 3


def test_two_items_same_url_raises(tmp_path):
    with pytest.raises(ValueError):
        run_downstream([_item(URL, CLEAN), _item(URL, CLEAN)], "t", scratch=tmp_path)


def test_transform_index_and_item_for(tmp_path):
    cfg = _config_tree(tmp_path)
    stored = transform_index(cfg)[URL]
    it = item_for(stored, [["a"]], "docling")
    assert it["rows"] == [["a"]] and it["pdf_extractor"] == "docling"
    assert stored["rows"] == CLEAN and stored["pdf_extractor"] == "pdfplumber"
    assert it["public_body_id"] == stored["public_body_id"]


def _stored_tree(root: Path, stored_records: int, gated: bool = False) -> Path:
    item = _item(URL, CLEAN)
    _w(root / "transform_disclosure_files/output.json", {"metadata": {}, "results": [item]})
    assessed = {**item, "rows": [] if gated else CLEAN}
    if gated:
        assessed["table_structure_unreliable"] = True
    _w(root / "assess_table_structure/output.json", {"metadata": {}, "results": [assessed]})
    _w(root / "extract_disclosures_canonicalize_rows/output.json",
       {"metadata": {}, "results": [{"file_url": URL}] * stored_records})
    _w(root / "extract_disclosures_canonicalize_rows/errors.json", [])
    return root


def test_reproduce_matches_when_stored_counts_agree(tmp_path):
    assert reproduce([URL], steps_dir=_stored_tree(tmp_path / "steps", 3), scratch=tmp_path / "s") == []


def test_reproduce_reports_mismatch_fields(tmp_path):
    got = reproduce([URL], steps_dir=_stored_tree(tmp_path / "steps", 2), scratch=tmp_path / "s")
    assert got == [{"file_url": URL, "field": "records", "expected": 2, "got": 3}]


def test_reproduce_reports_gate_mismatch(tmp_path):
    got = reproduce([URL], steps_dir=_stored_tree(tmp_path / "steps", 0, gated=True),
                    scratch=tmp_path / "s")
    assert got == [{"file_url": URL, "field": "gate_pass", "expected": False, "got": True}]


def test_reproduce_reports_missing_url(tmp_path):
    got = reproduce(["https://x.test/missing.pdf"], steps_dir=_stored_tree(tmp_path / "steps", 3),
                    scratch=tmp_path / "s")
    assert [m["field"] for m in got] == ["transform_item"]


def test_step_writes_land_in_scratch(tmp_path):
    rows = [r[:] for r in CLEAN]
    rows[1][2] = "  Copies of\ninvoices "
    run_downstream([_item(URL, rows)], "t", scratch=tmp_path)
    changes = json.loads((tmp_path / "t/01_normalize_disclosure_cells/changes.json").read_text())
    assert [c["row_idx"] for c in changes] == [1]
    assert (tmp_path / "t/05_extract_disclosures_split_combined_columns/output.json").is_file()
    assert (tmp_path / "t/08_extract_disclosures_canonicalize_rows/errors.json").is_file()
