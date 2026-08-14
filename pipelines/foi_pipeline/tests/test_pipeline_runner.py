import json
import sys
import time
from unittest.mock import patch

import pytest

from lib.pipeline_runner import is_stale, main


# --- is_stale unit tests ---

def test_is_stale_no_output(tmp_path):
    assert is_stale(tmp_path / "output.json", prev_out=None) is True


def test_is_stale_output_exists_no_prev(tmp_path):
    out = tmp_path / "output.json"
    out.write_text("{}")
    assert is_stale(out, prev_out=None) is False


def test_is_stale_prev_newer(tmp_path):
    step_out = tmp_path / "step.json"
    step_out.write_text("{}")
    time.sleep(0.05)
    prev_out = tmp_path / "prev.json"
    prev_out.write_text("{}")
    assert is_stale(step_out, prev_out=prev_out) is True


def test_is_stale_step_newer(tmp_path):
    prev_out = tmp_path / "prev.json"
    prev_out.write_text("{}")
    time.sleep(0.05)
    step_out = tmp_path / "step.json"
    step_out.write_text("{}")
    assert is_stale(step_out, prev_out=prev_out) is False


def test_is_stale_prev_missing(tmp_path):
    step_out = tmp_path / "step.json"
    step_out.write_text("{}")
    prev_out = tmp_path / "missing.json"
    assert is_stale(step_out, prev_out=prev_out) is False


# --- orchestrator integration tests ---

def _make_pipeline(tmp_path, steps, always_run=None):
    """Build a minimal pipeline dir at the expected pipelines/<name>/ depth."""
    pipeline_dir = tmp_path / "pipelines" / "foi_pipeline"
    pipeline_dir.mkdir(parents=True)
    config = {"steps": steps}
    if always_run is not None:
        config["always_run"] = always_run
    (pipeline_dir / "pipeline.json").write_text(json.dumps(config))
    for step in steps:
        (pipeline_dir / "steps" / step).mkdir(parents=True)
    return pipeline_dir


def test_orchestrator_skips_up_to_date_step(tmp_path, capsys):
    pipeline_dir = _make_pipeline(tmp_path, ["find_public_bodies"])
    (pipeline_dir / "steps" / "find_public_bodies" / "output.json").write_text("[]")

    with patch("lib.pipeline_runner.subprocess.run") as mock_run:
        sys.argv = ["process.py", str(pipeline_dir)]
        main()
        mock_run.assert_not_called()

    assert "up to date" in capsys.readouterr().out


def test_orchestrator_runs_stale_step(tmp_path):
    pipeline_dir = _make_pipeline(tmp_path, ["find_public_bodies"])

    with patch("lib.pipeline_runner.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        sys.argv = ["process.py", str(pipeline_dir)]
        main()
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "process.py" in cmd[1]
        assert "--output" in cmd


def test_orchestrator_force_reruns(tmp_path):
    pipeline_dir = _make_pipeline(tmp_path, ["find_public_bodies"])
    (pipeline_dir / "steps" / "find_public_bodies" / "output.json").write_text("[]")

    with patch("lib.pipeline_runner.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        sys.argv = ["process.py", str(pipeline_dir), "--force"]
        main()
        mock_run.assert_called_once()
        assert "--force" in mock_run.call_args[0][0]


def test_orchestrator_always_run_step_runs_despite_fresh_output(tmp_path):
    """A step listed in always_run must run even though its output.json
    already exists (i.e. is_stale() alone would report 'not stale', exactly
    as in test_orchestrator_skips_up_to_date_step above)."""
    pipeline_dir = _make_pipeline(
        tmp_path, ["fingerprint_disclosure_pages"],
        always_run=["fingerprint_disclosure_pages"],
    )
    (pipeline_dir / "steps" / "fingerprint_disclosure_pages" / "output.json").write_text("{}")

    with patch("lib.pipeline_runner.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        sys.argv = ["process.py", str(pipeline_dir)]
        main()
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "fingerprint_disclosure_pages" in cmd[1]
        assert "--force" not in cmd


def test_orchestrator_non_always_run_step_still_skipped_when_fresh(tmp_path, capsys):
    """With one step in always_run, a later step NOT in always_run is still
    skipped when its output.json is already newer than prev_out — always_run
    exempts only the named step(s), not the whole pipeline."""
    pipeline_dir = _make_pipeline(
        tmp_path,
        ["fingerprint_disclosure_pages", "verify_disclosure_files"],
        always_run=["fingerprint_disclosure_pages"],
    )
    fingerprint_out = pipeline_dir / "steps" / "fingerprint_disclosure_pages" / "output.json"
    fingerprint_out.write_text("{}")
    time.sleep(0.05)
    # verify_disclosure_files's output.json is newer than prev_out
    # (fingerprint_disclosure_pages's output.json) -> is_stale() says False
    verify_out = pipeline_dir / "steps" / "verify_disclosure_files" / "output.json"
    verify_out.write_text("{}")

    with patch("lib.pipeline_runner.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        sys.argv = ["process.py", str(pipeline_dir)]
        main()
        # only fingerprint_disclosure_pages runs (forced by always_run);
        # verify_disclosure_files is skipped (fresh, not in always_run)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "fingerprint_disclosure_pages" in cmd[1]
        assert "Skipping verify_disclosure_files (up to date)" in capsys.readouterr().out


def test_orchestrator_always_run_with_force_still_passes_force(tmp_path):
    """--force plus always_run: --force must still be passed through, and
    always_run must not double-force or otherwise change subprocess args."""
    pipeline_dir = _make_pipeline(
        tmp_path, ["fingerprint_disclosure_pages"],
        always_run=["fingerprint_disclosure_pages"],
    )
    (pipeline_dir / "steps" / "fingerprint_disclosure_pages" / "output.json").write_text("{}")

    with patch("lib.pipeline_runner.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        sys.argv = ["process.py", str(pipeline_dir), "--force"]
        main()
        assert mock_run.call_count == 1
        assert "--force" in mock_run.call_args[0][0]


def test_orchestrator_missing_always_run_key_defaults_to_empty(tmp_path):
    """pipeline.json without an always_run key behaves exactly as before:
    no step is exempted from the staleness gate."""
    pipeline_dir = _make_pipeline(tmp_path, ["find_public_bodies"])  # no always_run kwarg
    (pipeline_dir / "steps" / "find_public_bodies" / "output.json").write_text("[]")

    with patch("lib.pipeline_runner.subprocess.run") as mock_run:
        sys.argv = ["process.py", str(pipeline_dir)]
        main()
        mock_run.assert_not_called()


def test_orchestrator_stop_on_error(tmp_path):
    pipeline_dir = _make_pipeline(tmp_path, ["step_a", "step_b"])

    with patch("lib.pipeline_runner.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        with pytest.raises(SystemExit) as exc:
            sys.argv = ["process.py", str(pipeline_dir), "--stop-on-error"]
            main()
        assert exc.value.code == 1
        assert mock_run.call_count == 1


def test_orchestrator_from_flag_skips_earlier_steps(tmp_path):
    pipeline_dir = _make_pipeline(tmp_path, ["step_a", "step_b"])

    with patch("lib.pipeline_runner.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        sys.argv = ["process.py", str(pipeline_dir), "--from", "step_b"]
        main()
        assert mock_run.call_count == 1
        assert "step_b" in mock_run.call_args[0][0][1]


def test_orchestrator_sets_pythonpath_to_src(tmp_path):
    """PYTHONPATH passed to step subprocesses must be <repo_root>/src."""
    pipeline_dir = _make_pipeline(tmp_path, ["find_public_bodies"])

    with patch("lib.pipeline_runner.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        sys.argv = ["process.py", str(pipeline_dir)]
        main()
        env = mock_run.call_args[1]["env"]
        expected = str(pipeline_dir.parent.parent / "src")
        assert expected in env["PYTHONPATH"]


def test_orchestrator_uses_configured_input_step(tmp_path):
    pipeline_dir = _make_pipeline(tmp_path, ["extract_pages", "extract_figures"])
    config_path = pipeline_dir / "pipeline.json"
    config = json.loads(config_path.read_text())
    config["input_steps"] = {"extract_figures": "extract_pages"}
    config_path.write_text(json.dumps(config))

    with patch("lib.pipeline_runner.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        sys.argv = ["process.py", str(pipeline_dir), "--force"]
        main()

    assert mock_run.call_count == 2
    figure_cmd = mock_run.call_args_list[1].args[0]
    input_index = figure_cmd.index("--input") + 1
    assert figure_cmd[input_index].endswith("steps/extract_pages/output.json")


from lib.file_utils import write_json as _write_json


def _seed_bodies(pipeline_dir, ids):
    fpb = pipeline_dir / "steps" / "find_public_bodies"
    fpb.mkdir(parents=True, exist_ok=True)
    _write_json(fpb / "output.json",
                {"public_bodies": [{"public_body_id": i} for i in ids]})


def test_orchestrator_public_body_passthrough(tmp_path):
    pipeline_dir = _make_pipeline(tmp_path, ["find_public_bodies", "validate_websites"])
    _seed_bodies(pipeline_dir, [1001])

    with patch("lib.pipeline_runner.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        sys.argv = ["process.py", str(pipeline_dir), "--public-body", "1001"]
        main()
        for call in mock_run.call_args_list:
            cmd = call[0][0]
            assert "--public-body" in cmd
            assert cmd[cmd.index("--public-body") + 1] == "1001"
            assert "--force" not in cmd


def test_orchestrator_public_body_not_found_exits(tmp_path):
    pipeline_dir = _make_pipeline(tmp_path, ["find_public_bodies"])
    _seed_bodies(pipeline_dir, [1001])

    with patch("lib.pipeline_runner.subprocess.run"):
        with pytest.raises(SystemExit) as exc:
            sys.argv = ["process.py", str(pipeline_dir), "--public-body", "9999"]
            main()
        assert exc.value.code != 0


def test_orchestrator_public_body_missing_bodies_file_exits(tmp_path):
    pipeline_dir = _make_pipeline(tmp_path, ["find_public_bodies"])

    with patch("lib.pipeline_runner.subprocess.run"):
        with pytest.raises(SystemExit) as exc:
            sys.argv = ["process.py", str(pipeline_dir), "--public-body", "1001"]
            main()
        assert exc.value.code != 0


# --- absolute-path step tests ---

def _make_pipeline_with_abs(tmp_path, steps):
    """Build a minimal pipeline dir where absolute-path steps are external dirs."""
    pipeline_dir = tmp_path / "pipelines" / "foi_pipeline"
    pipeline_dir.mkdir(parents=True)
    (pipeline_dir / "pipeline.json").write_text(json.dumps({"steps": steps}))
    for step in steps:
        if not step.startswith("/"):
            (pipeline_dir / "steps" / step).mkdir(parents=True)
    return pipeline_dir


def _seed_upstream(tmp_path, step_path, content=None):
    """Create an upstream step output.json under tmp_path (acting as repo root)."""
    out = tmp_path / step_path.lstrip("/") / "output.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content or json.dumps({"public_bodies": [{"public_body_id": 1000}]}))
    return out


def test_absolute_step_sets_prev_out_and_skips_subprocess(tmp_path):
    pipeline_dir = _make_pipeline_with_abs(
        tmp_path, ["/pipelines/cso_pipeline/resolve_website_urls", "find_public_bodies"]
    )
    _seed_upstream(tmp_path, "/pipelines/cso_pipeline/resolve_website_urls")

    with patch("lib.pipeline_runner.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        sys.argv = ["process.py", str(pipeline_dir)]
        main()
        # subprocess called once for find_public_bodies, never for the absolute-path step
        assert mock_run.call_count == 1
        cmd = mock_run.call_args[0][0]
        assert "find_public_bodies" in cmd[1]


def test_absolute_step_passes_its_output_as_input_to_next_step(tmp_path):
    pipeline_dir = _make_pipeline_with_abs(
        tmp_path, ["/pipelines/cso_pipeline/resolve_website_urls", "find_public_bodies"]
    )
    upstream_out = _seed_upstream(tmp_path, "/pipelines/cso_pipeline/resolve_website_urls")

    with patch("lib.pipeline_runner.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        sys.argv = ["process.py", str(pipeline_dir)]
        main()
        cmd = mock_run.call_args[0][0]
        assert str(upstream_out) in cmd


def test_absolute_step_missing_output_exits_with_error(tmp_path):
    pipeline_dir = _make_pipeline_with_abs(
        tmp_path, ["/pipelines/cso_pipeline/resolve_website_urls", "find_public_bodies"]
    )
    # upstream output NOT seeded -> should exit with message naming the pipeline

    with patch("lib.pipeline_runner.subprocess.run"):
        with pytest.raises(SystemExit) as exc:
            sys.argv = ["process.py", str(pipeline_dir)]
            main()
        # sys.exit("message") sets exc.value.code to the message string
        assert "cso_pipeline" in str(exc.value.code)


def test_absolute_step_empty_output_exits_with_error(tmp_path):
    pipeline_dir = _make_pipeline_with_abs(
        tmp_path, ["/pipelines/cso_pipeline/resolve_website_urls", "find_public_bodies"]
    )
    upstream = tmp_path / "pipelines" / "cso_pipeline" / "resolve_website_urls" / "output.json"
    upstream.parent.mkdir(parents=True)
    upstream.write_text("")  # empty file

    with patch("lib.pipeline_runner.subprocess.run"):
        with pytest.raises(SystemExit) as exc:
            sys.argv = ["process.py", str(pipeline_dir)]
            main()
        assert exc.value.code != 0


def test_from_flag_skips_absolute_step_but_sets_prev_out(tmp_path):
    pipeline_dir = _make_pipeline_with_abs(
        tmp_path,
        ["/pipelines/cso_pipeline/resolve_website_urls", "find_public_bodies", "validate_websites"],
    )
    upstream_out = _seed_upstream(tmp_path, "/pipelines/cso_pipeline/resolve_website_urls")
    (pipeline_dir / "steps" / "validate_websites").mkdir(parents=True, exist_ok=True)

    with patch("lib.pipeline_runner.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        sys.argv = ["process.py", str(pipeline_dir), "--from", "validate_websites"]
        main()
        # only validate_websites runs
        assert mock_run.call_count == 1
        cmd = mock_run.call_args[0][0]
        assert "validate_websites" in cmd[1]
