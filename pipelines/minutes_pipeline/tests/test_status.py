import json

import status as body_status


STEPS = [
    "find_local_authorities",
    "find_meeting_minutes_pages",
    "find_minutes_files",
    "transform_minutes_files",
    "ocr_minutes_files",
    "extract_motions",
    "resolve_meeting_date",
    "canonicalize_motions",
    "export_motions",
]

AUTHORITIES = [
    {"public_body_id": 1456, "name": "Kildare County Council", "slug": "kildare",
     "official_website_url": "https://kildarecoco.ie/", "municipal_districts": []},
    {"public_body_id": 1085, "name": "Carlow County Council", "slug": "carlow",
     "official_website_url": None, "municipal_districts": []},
]


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def make_pipeline(tmp_path, per_step_records, per_step_errors=None):
    """Build a fake pipeline dir. per_step_records maps step -> list of records."""
    _write(tmp_path / "pipeline.json", {"steps": STEPS})
    for step in STEPS:
        records = per_step_records.get(step, [])
        _write(tmp_path / "steps" / step / "output.json",
               {"metadata": {"step": step}, "results": records})
        _write(tmp_path / "steps" / step / "pipeline-status.json",
               {"completed_at": "2026-09-10T18:00:00+00:00", "record_count": len(records)})
        _write(tmp_path / "steps" / step / "errors.json",
               (per_step_errors or {}).get(step, []))
    return tmp_path


def rec(body_id, **extra):
    base = {"public_body_id": body_id, "file_url": f"https://x.ie/{body_id}.pdf",
            "text": "some minutes text", "motions": [{"motion_text": "m"}],
            "meeting_date": "2025-01-01"}
    base.update(extra)
    return base


def test_healthy_body_flows_end_to_end(tmp_path, capsys):
    make_pipeline(tmp_path, {
        "find_local_authorities": AUTHORITIES,
        "find_meeting_minutes_pages": [rec(1456, file_url=None, text=None, motions=None)],
        "find_minutes_files": [rec(1456, text=None, motions=None)],
        "transform_minutes_files": [rec(1456, motions=None)],
        "ocr_minutes_files": [rec(1456, motions=None)],
        "extract_motions": [rec(1456)],
        "resolve_meeting_date": [rec(1456)],
        "canonicalize_motions": [{"public_body_id": 1456, "motion_id": "m1"}],
        "export_motions": [{"public_body_id": 1456, "motion_id": "m1"}],
    })
    (header, rows) = body_status.collect_status(tmp_path, "1456")
    assert header[0] == 1456
    assert all(r["has_output"] and r["count"] == 1 for r in rows)
    assert body_status.diagnose(rows) == ["Flowing end to end: 1 motion(s) exported."]


def test_dry_body_reports_first_empty_step(tmp_path):
    make_pipeline(tmp_path, {
        "find_local_authorities": AUTHORITIES,
        # Carlow (1085) has no minutes pages; Kildare should be untouched.
        "find_meeting_minutes_pages": [rec(1456, file_url=None, text=None, motions=None)],
    })
    (_, rows) = body_status.collect_status(tmp_path, "1085")
    verdicts = body_status.diagnose(rows)
    assert verdicts[0].startswith("Runs dry at: find_meeting_minutes_pages")


def test_slug_ref_resolves(tmp_path):
    make_pipeline(tmp_path, {"find_local_authorities": AUTHORITIES})
    (header, _) = body_status.collect_status(tmp_path, "kildare")
    assert header == (1456, "Kildare County Council", "kildare")


def test_unknown_body_raises(tmp_path):
    make_pipeline(tmp_path, {"find_local_authorities": AUTHORITIES})
    try:
        body_status.collect_status(tmp_path, "9999")
    except ValueError as exc:
        assert "Unknown public body" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_dropoff_flagged_and_errors_attributed(tmp_path, capsys):
    make_pipeline(tmp_path, {
        "find_local_authorities": AUTHORITIES,
        "find_minutes_files": [rec(1456, text=None, motions=None)],
        "transform_minutes_files": [],
    }, per_step_errors={
        "find_minutes_files": [
            {"error_type": "FetchFailed", "error_message": "boom",
             "context": {"public_body_id": 1085, "file_url": "https://x.ie/other.pdf"}},
            {"error_type": "FetchFailed", "error_message": "boom",
             "context": {"public_body_id": 1456, "file_url": "https://x.ie/1456.pdf"}},
        ],
    })
    (_, rows) = body_status.collect_status(tmp_path, "1456")
    by_name = {r["name"]: r for r in rows}
    assert len(by_name["find_minutes_files"]["errors"]) == 1  # only this body's error
    verdicts = body_status.diagnose(rows)
    assert any("find_minutes_files=1 -> transform_minutes_files=0" in v for v in verdicts)


def test_main_exit_codes(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(body_status, "collect_status",
                        lambda *a: ((1085, "Carlow County Council", "carlow"),
                                    [{"name": s, "has_output": True, "count": 0,
                                      "detail": "", "completed": None, "errors": []}
                                     for s in STEPS]))
    assert body_status.main(["--public-body", "1085"]) == 1
    out = capsys.readouterr().out
    assert "Runs dry at:" in out


def _two_body_pipeline(tmp_path):
    return make_pipeline(tmp_path, {
        "find_local_authorities": AUTHORITIES,
        "find_meeting_minutes_pages": [rec(1456, file_url=None, text=None, motions=None)],
        "find_minutes_files": [rec(1456, text=None, motions=None)],
        "transform_minutes_files": [rec(1456, motions=None)],
        "ocr_minutes_files": [rec(1456, motions=None)],
        "extract_motions": [rec(1456)],
        "resolve_meeting_date": [rec(1456)],
        "canonicalize_motions": [{"public_body_id": 1456, "motion_id": "m1"}],
        "export_motions": [{"public_body_id": 1456, "motion_id": "m1"}],
    })


def test_collect_all_covers_every_authority(tmp_path):
    _two_body_pipeline(tmp_path)
    steps, bodies = body_status.collect_all(tmp_path)
    assert steps == STEPS
    assert [h[0] for h, _ in bodies] == [1456, 1085]
    by_id = {h[0]: rows for h, rows in bodies}
    assert all(r["count"] == 1 for r in by_id[1456])
    assert by_id[1085][1]["count"] == 0  # Carlow dry at pages


def test_matrix_rows_and_dry_step(tmp_path):
    _two_body_pipeline(tmp_path)
    steps, bodies = body_status.collect_all(tmp_path)
    rows = body_status.matrix_rows(steps, bodies)
    assert rows[0][:2] == (1456, "kildare")
    assert rows[0][2][-1] == "1"  # export count
    assert rows[0][3] == 0 and rows[0][4] == "flowing"
    assert rows[1][4] == "pages"  # Carlow dry step, short label


def test_main_all_table_and_csv(tmp_path, capsys):
    _two_body_pipeline(tmp_path)
    assert body_status.main(["--all"], pipeline_dir=tmp_path) == 0
    out = capsys.readouterr().out
    assert "kildare" in out and "carlow" in out and "DRY_AT" in out
    assert body_status.main(["--all", "--csv"], pipeline_dir=tmp_path) == 0
    csv_out = capsys.readouterr().out
    assert csv_out.splitlines()[0] == "id,slug," + ",".join(
        body_status.short_label(s) for s in STEPS) + ",errs,dry_at"
    assert any(line.startswith("1456,kildare,") for line in csv_out.splitlines())
