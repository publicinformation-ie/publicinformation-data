import json
from pathlib import Path

import status

MEETING = "meath/x/2026-02-19"
OTHER_MEETING = "meath/x/2026-05-21"
URL = "https://www.meath.ie/x.pdf"
OTHER_URL = "https://www.meath.ie/y.pdf"
PAGE = "https://www.meath.ie/page"

STEPS = [
    "/pipelines/minutes_pipeline/steps/find_local_authorities",
    "find_spc_minutes_files",
    "fetch_spc_minutes",
    "parse_meeting_header",
    "resolve_attendees",
    "render_spc_minutes",
    "extract_spc_items",
    "export_spc_meetings",
]


def _repo(tmp_path):
    root = tmp_path / "repo"
    pipeline = root / "pipelines" / "spc_pipeline"
    pipeline.mkdir(parents=True)
    (pipeline / "pipeline.json").write_text(json.dumps({"steps": STEPS}))
    return root, pipeline


def _step_dir(pipeline: Path, step: str) -> Path:
    if step.startswith("/"):
        return pipeline.parents[1] / step.lstrip("/")
    return pipeline / "steps" / step


def _write(pipeline: Path, step: str, records, errors=None):
    step_dir = _step_dir(pipeline, step)
    step_dir.mkdir(parents=True, exist_ok=True)
    payload = records if isinstance(records, dict) else {"results": records}
    (step_dir / "output.json").write_text(json.dumps(payload))
    if errors is not None:
        (step_dir / "errors.json").write_text(json.dumps(errors))


def _seed(pipeline: Path, *, file_url=URL, meeting=MEETING):
    _write(pipeline, STEPS[0], [{"name": "Meath County Council"}])
    _write(pipeline, "find_spc_minutes_files",
           [{"file_url": file_url, "page_url": PAGE}])
    _write(pipeline, "fetch_spc_minutes", [{"file_url": file_url, "page_url": PAGE}])
    _write(pipeline, "parse_meeting_header",
           [{"meeting_id": meeting, "source_url": file_url}])
    _write(pipeline, "resolve_attendees", [{"meeting_id": meeting, "source_url": file_url}])
    _write(pipeline, "render_spc_minutes", [{"meeting_id": meeting, "source_url": file_url}])
    _write(pipeline, "extract_spc_items", [{"meeting_id": meeting, "source_url": file_url}])
    _write(pipeline, "export_spc_meetings", {"meetings": [{"meeting_id": meeting}]})


def test_complete_run_reports_end_to_end(tmp_path):
    _, pipeline = _repo(tmp_path)
    _seed(pipeline)
    result = status.funnel(pipeline)
    assert [row["count"] for row in result["rows"]] == [1] * 8
    assert "Flowing end to end" in status.verdict(result)[0]


def test_every_stage_is_joined_to_the_same_meeting(tmp_path):
    _, pipeline = _repo(tmp_path)
    _seed(pipeline)
    meeting = status.funnel(pipeline)["meetings"][0]
    assert meeting["meeting_id"] == MEETING
    assert meeting["stages"] == [
        "discovered", "fetched", "header", "attendance", "rendered",
        "extracted", "exported",
    ]


def test_errors_are_attributed_to_their_meeting(tmp_path):
    _, pipeline = _repo(tmp_path)
    _seed(pipeline)
    _write(pipeline, "fetch_spc_minutes",
           [{"file_url": URL, "page_url": PAGE}],
           [{"error_type": "DownloadFailed", "error_message": "timed out",
             "context": {"file_url": URL}}])
    _write(pipeline, "extract_spc_items",
           [{"meeting_id": MEETING, "source_url": URL}],
           [{"error_type": "ProceduralNotProceduralCode",
             "error_message": "item 7.0", "context": {"meeting_id": MEETING}}])
    meeting = status.funnel(pipeline)["meetings"][0]
    assert meeting["error_count"] == 2
    assert {error["error_type"] for error in meeting["errors"]} == {
        "DownloadFailed", "ProceduralNotProceduralCode"}
    assert {error["step"] for error in meeting["errors"]} == {
        "fetch_spc_minutes", "extract_spc_items"}


def test_a_file_that_stalls_before_the_header_stays_visible(tmp_path):
    _, pipeline = _repo(tmp_path)
    _seed(pipeline)
    _write(pipeline, "find_spc_minutes_files",
           [{"file_url": URL, "page_url": PAGE},
            {"file_url": OTHER_URL, "page_url": PAGE}])
    _write(pipeline, "fetch_spc_minutes",
           [{"file_url": URL, "page_url": PAGE},
            {"file_url": OTHER_URL, "page_url": PAGE}])
    result = status.funnel(pipeline)
    stalled = next(m for m in result["meetings"] if m["file_url"] == OTHER_URL)
    assert stalled["meeting_id"] is None
    assert stalled["stages"] == ["discovered", "fetched"]
    assert stalled["last_stage"] == "fetched"


def test_step_order_comes_from_pipeline_json(tmp_path):
    _, pipeline = _repo(tmp_path)
    _seed(pipeline)
    config = json.loads((pipeline / "pipeline.json").read_text())
    config["steps"] = [STEPS[1], STEPS[2], STEPS[7]]
    (pipeline / "pipeline.json").write_text(json.dumps(config))
    result = status.funnel(pipeline)
    assert [row["stage"] for row in result["rows"]] == [
        "discovered", "fetched", "exported"]


def test_truncated_output_names_the_first_dry_step(tmp_path):
    _, pipeline = _repo(tmp_path)
    _seed(pipeline)
    _write(pipeline, "export_spc_meetings", {"meetings": []})
    result = status.funnel(pipeline)
    assert any("Runs dry at: export_spc_meetings" in line
               for line in status.verdict(result))


def test_missing_step_output_is_a_data_error(tmp_path):
    _, pipeline = _repo(tmp_path)
    result = status.funnel(pipeline)
    assert "missing or unreadable" in result["error"]


def test_main_exits_zero_on_a_completed_run(tmp_path, monkeypatch, capsys):
    _, pipeline = _repo(tmp_path)
    _seed(pipeline)
    monkeypatch.setattr(status, "PIPELINE_DIR", pipeline)
    monkeypatch.setattr("sys.argv", ["status.py"])
    assert status.main() == 0
    assert "Flowing end to end" in capsys.readouterr().out
