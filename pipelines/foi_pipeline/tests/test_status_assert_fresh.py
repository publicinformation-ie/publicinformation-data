import json
import sys
import time
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _run_assert_fresh(tmp_path, monkeypatch):
    """Import and call assert_fresh with tmp_path as pipeline_dir. Returns (exit_code, stdout)."""
    from status import assert_fresh
    import io
    captured = io.StringIO()
    monkeypatch.setattr("sys.stdout", captured)
    try:
        assert_fresh(tmp_path)
        return 0, captured.getvalue()
    except SystemExit as e:
        return e.code, captured.getvalue()


def _write_file(path, content="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


class TestAssertFresh:
    def test_exits_0_when_output_newer_than_sources(self, tmp_path, monkeypatch):
        lib_dir = tmp_path / "lib"
        lib_dir.mkdir()
        req = tmp_path / "requirements.txt"
        req.write_text("requests==2.33.1")
        # Write export_status output AFTER sources
        time.sleep(0.05)
        out = tmp_path / "steps" / "export_status" / "output.json"
        out.parent.mkdir(parents=True)
        out.write_text(json.dumps({"metadata": {}}))

        code, msg = _run_assert_fresh(tmp_path, monkeypatch)
        assert code == 0

    def test_exits_1_when_lib_file_newer_than_output(self, tmp_path, monkeypatch):
        out = tmp_path / "steps" / "export_status" / "output.json"
        out.parent.mkdir(parents=True)
        out.write_text(json.dumps({"metadata": {}}))
        # Write lib file AFTER output
        time.sleep(0.05)
        lib_file = tmp_path / "lib" / "file_utils.py"
        lib_file.parent.mkdir(parents=True)
        lib_file.write_text("# changed")

        code, msg = _run_assert_fresh(tmp_path, monkeypatch)
        assert code == 1
        assert "stale" in msg.lower() or "file_utils" in msg

    def test_exits_1_when_requirements_newer_than_output(self, tmp_path, monkeypatch):
        out = tmp_path / "steps" / "export_status" / "output.json"
        out.parent.mkdir(parents=True)
        out.write_text(json.dumps({}))
        time.sleep(0.05)
        req = tmp_path / "requirements.txt"
        req.write_text("new-package==1.0")

        code, msg = _run_assert_fresh(tmp_path, monkeypatch)
        assert code == 1

    def test_exits_1_when_run_py_newer_than_output(self, tmp_path, monkeypatch):
        out = tmp_path / "steps" / "export_status" / "output.json"
        out.parent.mkdir(parents=True)
        out.write_text(json.dumps({}))
        time.sleep(0.05)
        run_py = tmp_path / "steps" / "sync_backlog" / "run.py"
        run_py.parent.mkdir(parents=True)
        run_py.write_text("# logic changed")

        code, msg = _run_assert_fresh(tmp_path, monkeypatch)
        assert code == 1

    def test_exits_1_when_output_missing(self, tmp_path, monkeypatch):
        # No export_status/output.json exists
        code, msg = _run_assert_fresh(tmp_path, monkeypatch)
        assert code == 1
        assert "missing" in msg.lower() or "not run" in msg.lower() or "not found" in msg.lower()

    def test_exits_0_with_no_source_files(self, tmp_path, monkeypatch):
        out = tmp_path / "steps" / "export_status" / "output.json"
        out.parent.mkdir(parents=True)
        out.write_text(json.dumps({}))
        # No lib/, no requirements.txt, no run.py files

        code, msg = _run_assert_fresh(tmp_path, monkeypatch)
        assert code == 0
