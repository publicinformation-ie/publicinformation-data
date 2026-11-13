"""The committed transform_disclosure_files output must be reproducible."""
import json

from lib.file_utils import IncrementalWriter


def _run(tmp_path, record_completed_at):
    out = tmp_path / "output.json"
    w = IncrementalWriter(out, "transform_disclosure_files", key_field="file_url",
                          force=True, record_completed_at=record_completed_at)
    w.append([{"file_url": "https://x/a.csv", "public_body_id": 1}])
    w.finalize()
    return out


def test_rerun_with_no_timestamp_is_byte_identical(tmp_path):
    first = _run(tmp_path, False).read_bytes()
    second = _run(tmp_path, False).read_bytes()
    assert first == second
    assert "completed_at" not in json.loads(first)["metadata"]


def test_default_still_records_completed_at(tmp_path):
    assert "completed_at" in json.loads(_run(tmp_path, True).read_text())["metadata"]


def test_transform_disclosure_files_step_opts_out_of_timestamp():
    from pathlib import Path
    src = (Path(__file__).parent.parent / "steps/transform_disclosure_files/process.py").read_text()
    assert "record_completed_at=False" in src
