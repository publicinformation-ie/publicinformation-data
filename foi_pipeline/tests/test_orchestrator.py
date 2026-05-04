import json
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from orchestrator import is_stale, main


# --- is_stale unit tests ---

def test_is_stale_no_output_no_prev(tmp_path):
    step_out = tmp_path / "output.json"
    assert is_stale(step_out, prev_out=None) is True


def test_is_stale_output_exists_no_prev(tmp_path):
    step_out = tmp_path / "output.json"
    step_out.write_text("{}")
    assert is_stale(step_out, prev_out=None) is False


def test_is_stale_prev_newer_than_step(tmp_path):
    step_out = tmp_path / "step.json"
    step_out.write_text("{}")
    time.sleep(0.05)
    prev_out = tmp_path / "prev.json"
    prev_out.write_text("{}")
    assert is_stale(step_out, prev_out=prev_out) is True


def test_is_stale_step_newer_than_prev(tmp_path):
    prev_out = tmp_path / "prev.json"
    prev_out.write_text("{}")
    time.sleep(0.05)
    step_out = tmp_path / "step.json"
    step_out.write_text("{}")
    assert is_stale(step_out, prev_out=prev_out) is False


def test_is_stale_prev_missing(tmp_path):
    step_out = tmp_path / "step.json"
    step_out.write_text("{}")
    prev_out = tmp_path / "prev.json"  # does not exist
    assert is_stale(step_out, prev_out=prev_out) is False


# --- orchestrator integration tests ---

def _make_pipeline(tmp_path, steps):
    """Build a minimal pipeline dir with pipeline.json and stub step dirs."""
    pipeline_dir = tmp_path / "foi_pipeline"
    (pipeline_dir).mkdir()
    (pipeline_dir / "pipeline.json").write_text(json.dumps({"steps": steps}))
    for step in steps:
        step_dir = pipeline_dir / "steps" / step
        step_dir.mkdir(parents=True)
    return pipeline_dir


def test_orchestrator_skips_up_to_date_step(tmp_path, capsys):
    pipeline_dir = _make_pipeline(tmp_path, ["find_public_bodies"])
    output = pipeline_dir / "steps" / "find_public_bodies" / "output.json"
    output.write_text("[]")

    with patch("orchestrator.subprocess.run") as mock_run:
        sys.argv = ["orchestrator.py", str(pipeline_dir)]
        main()
        mock_run.assert_not_called()

    captured = capsys.readouterr()
    assert "up to date" in captured.out


def test_orchestrator_runs_stale_step(tmp_path):
    pipeline_dir = _make_pipeline(tmp_path, ["find_public_bodies"])
    # No output.json → stale

    with patch("orchestrator.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        sys.argv = ["orchestrator.py", str(pipeline_dir)]
        main()
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "process.py" in cmd[1]
        assert "--output" in cmd


def test_orchestrator_force_reruns(tmp_path):
    pipeline_dir = _make_pipeline(tmp_path, ["find_public_bodies"])
    output = pipeline_dir / "steps" / "find_public_bodies" / "output.json"
    output.write_text("[]")

    with patch("orchestrator.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        sys.argv = ["orchestrator.py", str(pipeline_dir), "--force"]
        main()
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "--force" in cmd


def test_orchestrator_stop_on_error(tmp_path):
    pipeline_dir = _make_pipeline(tmp_path, ["step_a", "step_b"])

    with patch("orchestrator.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        with pytest.raises(SystemExit) as exc:
            sys.argv = ["orchestrator.py", str(pipeline_dir), "--stop-on-error"]
            main()
        assert exc.value.code == 1
        assert mock_run.call_count == 1  # halted after step_a


def test_orchestrator_from_flag_skips_earlier_steps(tmp_path):
    pipeline_dir = _make_pipeline(tmp_path, ["step_a", "step_b"])

    with patch("orchestrator.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        sys.argv = ["orchestrator.py", str(pipeline_dir), "--from", "step_b"]
        main()
        # Only step_b should run
        assert mock_run.call_count == 1
        cmd = mock_run.call_args[0][0]
        assert "step_b" in cmd[1]


def test_orchestrator_sets_pythonpath(tmp_path):
    pipeline_dir = _make_pipeline(tmp_path, ["find_public_bodies"])

    with patch("orchestrator.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        sys.argv = ["orchestrator.py", str(pipeline_dir)]
        main()
        env = mock_run.call_args[1]["env"]
        assert str(pipeline_dir) in env["PYTHONPATH"]
