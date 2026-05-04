import json
from pathlib import Path

import pytest

from scripts.file_utils import append_error, read_json, write_json, write_status


def test_write_and_read_json(tmp_path):
    data = [{"key": "value", "num": 42}]
    write_json(tmp_path / "out.json", data)
    assert read_json(tmp_path / "out.json") == data


def test_write_json_uses_utf8(tmp_path):
    data = {"name": "Déartment"}
    write_json(tmp_path / "out.json", data)
    raw = (tmp_path / "out.json").read_text(encoding="utf-8")
    assert "Déartment" in raw


def test_read_json_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_json(tmp_path / "missing.json")


def test_append_error_creates_file(tmp_path):
    error = {
        "step": "test_step",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "error_type": "ValueError",
        "error_message": "something broke",
        "context": {"url": "https://example.com"},
    }
    append_error(tmp_path, error)
    errors = read_json(tmp_path / "errors.json")
    assert len(errors) == 1
    assert errors[0]["error_type"] == "ValueError"


def test_append_error_accumulates(tmp_path):
    for i in range(3):
        append_error(tmp_path, {"step": "s", "timestamp": "t", "error_type": f"E{i}", "error_message": "", "context": {}})
    errors = read_json(tmp_path / "errors.json")
    assert len(errors) == 3
    assert errors[2]["error_type"] == "E2"


def test_write_status(tmp_path):
    write_status(tmp_path, 286)
    status = read_json(tmp_path / "pipeline-status.json")
    assert status["record_count"] == 286
    assert "completed_at" in status
    # ISO-8601 with timezone
    assert "T" in status["completed_at"]
    assert "+" in status["completed_at"] or "Z" in status["completed_at"]
