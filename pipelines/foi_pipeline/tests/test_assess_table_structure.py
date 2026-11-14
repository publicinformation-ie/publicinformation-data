import json
from pathlib import Path

from lib.file_utils import IncrementalWriter
from steps.assess_table_structure.process import process, STEP_NAME
from steps.filter_phantom_rows import process as phantom
from steps.normalize_disclosure_cells import process as normalize

GOOD_ROWS = [["Ref", "Date", "Status"]] + [
    [f"FOI-{i}", "2024-01-0%d" % (i % 9 + 1), "Granted"] for i in range(20)
]
# Ragged, fragmented: wildly varying widths
BAD_ROWS = [["a"], ["b", "c", "d", "e"], ["f", "g"], ["h"], ["i", "j", "k"], ["l", "m"]] * 4


def _rec(url, file_type, rows, body=7):
    return {"file_url": url, "file_type": file_type, "public_body_id": body,
            "name": "B", "pdf_extractor": "pdfplumber", "rows": rows}


def _run(tmp_path, records, force=True):
    step_dir = tmp_path / "step"
    step_dir.mkdir(exist_ok=True)
    writer = IncrementalWriter(step_dir / "output.json", STEP_NAME,
                               key_field="file_url", force=force)
    process({"results": records}, writer, step_dir=step_dir)
    writer.finalize()
    out = json.loads((step_dir / "output.json").read_text())["results"]
    errs_path = step_dir / "errors.json"
    errs = json.loads(errs_path.read_text()) if errs_path.exists() else []
    return out, errs


def test_passing_pdf_passes_through_unchanged_plus_score(tmp_path):
    out, errs = _run(tmp_path, [_rec("u1", "pdf", GOOD_ROWS)])
    assert errs == []
    rec = out[0]
    assert rec["rows"] == GOOD_ROWS
    assert "table_structure_unreliable" not in rec
    assert set(rec["table_structure"]) >= {"n_rows", "width_uniformity", "composite"}
    base = {k: v for k, v in rec.items() if k != "table_structure"}
    assert base == _rec("u1", "pdf", GOOD_ROWS)


def test_failing_pdf_emptied_flagged_and_one_error_logged(tmp_path):
    out, errs = _run(tmp_path, [_rec("u2", "pdf", BAD_ROWS)])
    rec = out[0]
    assert rec["rows"] == []
    assert rec["table_structure_unreliable"] is True
    assert "table_structure" in rec
    assert len(errs) == 1
    e = errs[0]
    assert e["step"] == "assess_table_structure"
    assert e["error_type"] == "TableStructureUnreliable"
    assert e["error_message"] == "no extractor produced a structurally reliable table"
    ctx = e["context"]
    assert ctx["public_body_id"] == 7 and ctx["file_url"] == "u2"
    assert ctx["pdf_extractor"] == "pdfplumber"
    assert ctx["failed_checks"] and "score" in ctx


def test_xlsx_never_gated_even_when_ragged(tmp_path):
    out, errs = _run(tmp_path, [_rec("u3", "xlsx", BAD_ROWS)])
    assert out[0]["rows"] == BAD_ROWS
    assert "table_structure" in out[0]
    assert "table_structure_unreliable" not in out[0]
    assert errs == []


def test_rerun_does_not_duplicate_error(tmp_path):
    recs = [_rec("u2", "pdf", BAD_ROWS)]
    _run(tmp_path, recs)
    out, errs = _run(tmp_path, recs, force=False)  # resume
    assert len(errs) == 1 and len(out) == 1
    out, errs = _run(tmp_path, recs, force=True)  # forced rebuild
    assert len(errs) == 1 and len(out) == 1


def test_downstream_handles_emptied_record(tmp_path):
    out, _ = _run(tmp_path, [_rec("u2", "pdf", BAD_ROWS)])
    d = tmp_path / "norm"
    d.mkdir()
    w = IncrementalWriter(d / "output.json", "normalize_disclosure_cells",
                          key_field="file_url", force=True)
    normalize.process({"results": out}, d, w)
    w.finalize()
    norm = json.loads((d / "output.json").read_text())["results"]
    w2 = IncrementalWriter(tmp_path / "p.json", "filter_phantom_rows",
                           key_field="file_url", force=True)
    phantom.process({"results": norm}, w2)
    w2.finalize()
    final = json.loads((tmp_path / "p.json").read_text())["results"]
    assert sum(len(r["rows"]) for r in final) == 0


def test_rows_none_passes_through_unscored(tmp_path):
    out, errs = _run(tmp_path, [_rec("u4", "pdf", None)])
    assert out[0] == _rec("u4", "pdf", None)
    assert errs == []


def test_empty_pdf_rows_pass_through_without_error(tmp_path):
    out, errs = _run(tmp_path, [_rec("u5", "pdf", [])])
    assert out[0] == _rec("u5", "pdf", [])
    assert "table_structure" not in out[0]
    assert "table_structure_unreliable" not in out[0]
    assert errs == []


def _run_with_overrides(tmp_path, records, override_urls):
    canon = tmp_path / "extract_disclosures_canonicalize"
    canon.mkdir(exist_ok=True)
    (canon / "column_mappings.json").write_text(json.dumps(
        {u: {"source_method": "manual", "overridden": True, "column_mapping": {}} for u in override_urls}
    ))
    step_dir = tmp_path / "assess_table_structure"
    step_dir.mkdir(exist_ok=True)
    writer = IncrementalWriter(step_dir / "output.json", STEP_NAME, key_field="file_url", force=True)
    process({"results": records}, writer, step_dir=step_dir)
    writer.finalize()
    out = json.loads((step_dir / "output.json").read_text())["results"]
    errs_path = step_dir / "errors.json"
    return out, (json.loads(errs_path.read_text()) if errs_path.exists() else [])


def test_override_pdf_failing_score_keeps_rows_and_logs_no_error(tmp_path):
    out, errs = _run_with_overrides(tmp_path, [_rec("ov", "pdf", BAD_ROWS)], {"ov"})
    rec = out[0]
    assert rec["rows"] == BAD_ROWS
    assert "table_structure_unreliable" not in rec
    assert rec["table_structure"]["override_exempt"] is True
    assert errs == []


def test_non_override_failing_pdf_still_emptied_when_overrides_exist(tmp_path):
    out, errs = _run_with_overrides(
        tmp_path, [_rec("ov", "pdf", BAD_ROWS), _rec("other", "pdf", BAD_ROWS)], {"ov"}
    )
    by_url = {r["file_url"]: r for r in out}
    assert by_url["ov"]["rows"] == BAD_ROWS
    assert by_url["other"]["rows"] == [] and by_url["other"]["table_structure_unreliable"] is True
    assert [e["context"]["file_url"] for e in errs] == ["other"]
