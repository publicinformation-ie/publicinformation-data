import json

import openpyxl
import pytest

from steps.extract_annex_status import process as mod
from steps.extract_annex_status.process import (
    LAYOUTS, extract_document, header_signature, map_status, parse_timeline, process)

HEADER = ["Chapter", "Theme", "Measure", "Action Number", "Action",
          "Step", "Output", "Timeline", "Lead", "Responsible Department",
          "Stakeholders", "Status: Complete / Delayed", "Text Update"]


def _sig(header):
    return header_signature(header)


def _row(ref, status, timeline="Q3 2023", text="Do the thing", update="done"):
    return ["c", "t", "m", ref, text, "step", "out", timeline, "l", "d", "s", status, update]


def _book(tmp_path, sheets, name="a.xlsx"):
    wb = openpyxl.Workbook()
    wb.remove(wb.worksheets[0])
    for title, rows in sheets.items():
        ws = wb.create_sheet(title)
        for r in rows:
            ws.append(r)
    path = tmp_path / name
    wb.save(path)
    return path


def _extract(tmp_path, sheets, published: str | None = "2024-01-31"):
    path = _book(tmp_path, sheets)
    errors = []
    record = extract_document(path, {"doc_slug": "rep", "published_date": published}, errors)
    return record, errors


def _types(errors):
    return [e["error_type"] for e in errors]


def test_header_layout_is_a_known_signature():
    assert _sig(HEADER) in LAYOUTS


def test_every_reviewed_layout_resolves_its_columns():
    assert len(LAYOUTS) == 12
    for columns in LAYOUTS.values():
        assert set(columns) == {"reference", "action_text", "output", "timeline",
                                "status", "status_text"}


def test_recognised_layout_yields_rows_with_provenance(tmp_path):
    rec, errors = _extract(tmp_path, {"Q1": [HEADER, _row("EN/23/1", "Complete"),
                                             _row("EN/23/2", "Delayed")]})
    assert errors == []
    assert rec["status_counts"] == {"Complete": 1, "Delayed": 1}
    obs = rec["observations"][0]
    assert (obs["action_number"], obs["status"], obs["as_of"]) == ("EN/23/1", "Complete", "2024-01-31")
    assert (obs["sheet"], obs["row"], obs["source_ref"]) == ("Q1", 2, "Q1!r2")
    assert obs["reported_deadline_start"] == "2023-07-01"
    assert obs["reported_deadline_precision"] == "quarter"


def test_unrecognised_header_skips_sheet_and_logs(tmp_path):
    bad = list(HEADER)
    bad[4] = "Actions and more"
    rec, errors = _extract(tmp_path, {"S": [bad, _row("EN/23/1", "Complete")]})
    assert rec["observations"] == []
    (e,) = errors
    assert e["error_type"] == "UnrecognisedAnnexLayout"
    assert e["context"]["sheet"] == "S"
    assert e["context"]["header_found"][4] == "Actions and more"


def test_header_matching_is_not_a_subset_match(tmp_path):
    # a recognised header plus one extra named column is not recognised
    extended = HEADER + ["Extra"]
    rec, errors = _extract(tmp_path, {"S": [extended, _row("EN/23/1", "Complete")]})
    assert rec["observations"] == [] and _types(errors) == ["UnrecognisedAnnexLayout"]


def test_trailing_empty_header_cells_are_ignored(tmp_path):
    rec, errors = _extract(tmp_path, {"S": [HEADER + [None, None], _row("EN/23/1", "Complete")]})
    assert errors == [] and len(rec["observations"]) == 1


def test_merged_header_is_skipped(tmp_path):
    path = _book(tmp_path, {"S": [HEADER, _row("EN/23/1", "Complete")]})
    wb = openpyxl.load_workbook(path)
    wb["S"].merge_cells("A1:C1")   # chapter/theme/measure collapse to one value + blanks
    wb.save(path)
    errors = []
    rec = extract_document(path, {"doc_slug": "rep", "published_date": "2024-01-31"}, errors)
    assert rec["observations"] == [] and _types(errors) == ["UnrecognisedAnnexLayout"]


def test_two_row_header_is_skipped(tmp_path):
    rec, errors = _extract(tmp_path, {"S": [["Report title"], HEADER, _row("EN/23/1", "Complete")]})
    assert rec["observations"] == [] and _types(errors) == ["UnrecognisedAnnexLayout"]


def test_header_in_row_two_is_skipped(tmp_path):
    rec, errors = _extract(tmp_path, {"S": [[None] * 13, HEADER, _row("EN/23/1", "Complete")]})
    assert rec["observations"] == [] and _types(errors) == ["UnrecognisedAnnexLayout"]


def test_one_bad_sheet_does_not_hide_the_others(tmp_path):
    rec, errors = _extract(tmp_path, {"Bad": [["x"]], "Good": [HEADER, _row("EN/23/1", "Complete")]})
    assert [o["sheet"] for o in rec["observations"]] == ["Good"]
    assert _types(errors) == ["UnrecognisedAnnexLayout"]


def test_discontinued_is_excluded_and_logged_raw(tmp_path):
    rec, errors = _extract(tmp_path, {"S": [HEADER, _row("EN/23/1", "Discontinued ")]})
    assert rec["observations"] == []
    (e,) = errors
    assert e["error_type"] == "UnmappableStatus"
    assert e["context"]["raw_status"] == "Discontinued "
    assert e["context"]["row"] == 2


def test_empty_status_is_missing_not_inferred(tmp_path):
    rec, errors = _extract(tmp_path, {"S": [HEADER, _row("EN/23/1", None)]})
    assert rec["observations"] == [] and _types(errors) == ["MissingStatus"]


def test_status_with_padding_and_case_maps(tmp_path):
    rec, errors = _extract(tmp_path, {"S": [HEADER, _row("EN/23/1", "  DELAYED "),
                                            _row("EN/23/2", "On  Schedule")]})
    assert errors == []
    assert [o["status"] for o in rec["observations"]] == ["Delayed", "OnSchedule"]


def test_map_status_is_closed():
    assert map_status("Complete") == "Complete"
    assert map_status("Ongoing") is None
    assert map_status("Completed") is None


def test_reference_with_nbsp_and_taskforce_flag(tmp_path):
    rec, errors = _extract(tmp_path, {"S": [HEADER, _row("EN/23/ 1 (TF)", "Complete"),
                                            _row("EN/23/2 ( TF )", "Complete"),
                                            _row("EN/23/3*", "Complete")]})
    assert errors == []
    first, second, third = rec["observations"]
    assert (first["action_number"], first["action_flags"]) == ("EN/23/1", ["taskforce"])
    assert (second["action_number"], second["action_flags"]) == ("EN/23/2", ["taskforce"])
    assert third["action_flags"] == ["non_reportable"]


def test_unresolvable_reference_is_excluded(tmp_path):
    rec, errors = _extract(tmp_path, {"S": [HEADER, _row("", "Complete"), _row("EN-23-1", "Complete")]})
    assert rec["observations"] == []
    assert _types(errors) == ["UnresolvedActionNumber", "InvalidActionReference"]


def test_duplicate_reference_excludes_both_and_names_locations(tmp_path):
    rec, errors = _extract(tmp_path, {"A": [HEADER, _row("EN/23/1", "Complete"),
                                            _row("EN/23/2", "Complete")],
                                      "B": [HEADER, _row("EN/23/1", "Delayed")]})
    assert [o["action_number"] for o in rec["observations"]] == ["EN/23/2"]
    (e,) = errors
    assert e["error_type"] == "DuplicateAnnexReference"
    assert e["context"]["locations"] == [{"sheet": "A", "row": 2}, {"sheet": "B", "row": 2}]


def test_timeline_must_be_strict_quarter_year(tmp_path):
    rec, errors = _extract(tmp_path, {"S": [HEADER, _row("EN/23/1", "Complete", "Q3 2023 Delayed"),
                                            _row("EN/23/2", "Complete", "Q 3 2023"),
                                            _row("EN/23/3", "Complete", "Q4 2024")]})
    a, b, c = rec["observations"]
    assert a["reported_deadline_raw"] == "Q3 2023 Delayed" and a["reported_deadline_start"] is None
    assert b["reported_deadline_precision"] is None
    assert c["reported_deadline_start"] == "2024-10-01"
    assert _types(errors) == ["UnparsedTimeline", "UnparsedTimeline"]
    parsed = parse_timeline("Q1 2025")
    assert parsed is not None and parsed["quarter"] == 1
    assert parse_timeline("Q5 2025") is None


def test_undated_report_emits_nothing_and_one_error(tmp_path):
    rec, errors = _extract(tmp_path, {"S": [HEADER, _row("EN/23/1", "Complete"),
                                            _row("EN/23/2", "Complete")]}, published=None)
    assert rec["observations"] == [] and rec["as_of"] is None
    assert _types(errors) == ["MissingReportDate"]


def test_every_sheet_is_dated_from_the_report(tmp_path):
    rec, _ = _extract(tmp_path, {"Q1": [HEADER, _row("EN/23/1", "Complete")],
                                 "Q4": [HEADER, _row("EN/23/2", "Delayed")]},
                      published="2025-02-20")
    assert {o["as_of"] for o in rec["observations"]} == {"2025-02-20"}
    assert [s["sheet"] for s in rec["sheets"]] == ["Q1", "Q4"]


def test_fill_only_status_is_not_read(tmp_path):
    from openpyxl.styles import PatternFill
    path = _book(tmp_path, {"S": [HEADER, _row("EN/23/1", None)]})
    wb = openpyxl.load_workbook(path)
    wb["S"]["L2"].fill = PatternFill("solid", fgColor="FF00FF00")
    wb.save(path)
    errors = []
    rec = extract_document(path, {"doc_slug": "rep", "published_date": "2024-01-31"}, errors)
    assert rec["observations"] == [] and _types(errors) == ["MissingStatus"]


def test_process_writes_records_and_flags_unfetched_annex(tmp_path, make_writer):
    path = _book(tmp_path, {"S": [HEADER, _row("EN/23/1", "Complete")]}, name="a.xlsx")
    records = [{"doc_slug": "rep", "annex_path": path.name, "source_sha256": "abc"}]
    meta = {"rep": {"title": "R", "published_date": "2024-01-31", "reports_on": ["p"],
                    "status_annex": {"url": "u", "format": "xlsx"}},
            "other": {"title": "O", "status_annex": {"url": "u", "format": "xlsx"}}}
    writer = make_writer("extract_annex_status")
    process(records, meta, tmp_path, tmp_path, writer)
    writer.finalize()
    (out,) = json.loads((tmp_path / "output.json").read_text())["results"]
    assert out["annex_sha256"] == "abc" and out["reports_on"] == ["p"]
    errs = json.loads((tmp_path / "errors.json").read_text())
    assert [(e["error_type"], e["context"]["doc_slug"]) for e in errs] == [("AnnexNotFetched", "other")]

