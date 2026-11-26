import json
from pathlib import Path

import status


def _write(pipeline: Path, step: str, records, errors=None):
    step_dir = pipeline / "steps" / step
    step_dir.mkdir(parents=True, exist_ok=True)
    (step_dir / "output.json").write_text(json.dumps({"results": records}))
    if errors is not None:
        (step_dir / "errors.json").write_text(json.dumps(errors))


def _seed(pipeline: Path, stages=7):
    steps = [step for step, _ in status.STEPS][:stages]
    for index, step in enumerate(steps):
        if step == "export_spc_meetings":
            payload = [{"meeting_id": "meath/x/2026-02-19"}]
        elif step == "find_spc_minutes_files":
            payload = [{"file_url": "https://www.meath.ie/x.pdf"}]
        else:
            payload = [{"meeting_id": "meath/x/2026-02-19"}]
        _write(pipeline, step, payload if index < stages else [])


def test_complete_run_reports_end_to_end(tmp_path):
    _seed(tmp_path)
    result = status.funnel(tmp_path)
    assert [row["count"] for row in result["rows"]] == [1] * 7
    assert "Flowing end to end" in status.verdict(result)[0]


def test_truncated_output_names_the_first_dry_step(tmp_path):
    _seed(tmp_path)
    _write(tmp_path, "export_spc_meetings", [])
    result = status.funnel(tmp_path)
    assert any("Runs dry at: export_spc_meetings" in line
               for line in status.verdict(result))


def test_missing_step_output_is_a_data_error(tmp_path):
    result = status.funnel(tmp_path)
    assert "missing or unreadable" in result["error"]


def test_main_exits_zero_on_a_completed_run(tmp_path, monkeypatch, capsys):
    _seed(tmp_path)
    monkeypatch.setattr(status, "PIPELINE_DIR", tmp_path)
    monkeypatch.setattr("sys.argv", ["status.py"])
    assert status.main() == 0
    assert "Flowing end to end" in capsys.readouterr().out
