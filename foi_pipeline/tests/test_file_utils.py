import json
from pathlib import Path

import pytest

from scripts.file_utils import (
    append_error,
    read_json,
    sanitize_error_context,
    sanitize_url_for_logging,
    write_json,
    write_status,
)


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


class TestSanitizeUrlForLogging:
    """Tests for URL sanitization in logs."""

    def test_full_url_returns_domain_only(self):
        result = sanitize_url_for_logging("https://www.gov.ie/en/department/?param=value")
        assert result == "www.gov.ie"

    def test_http_url(self):
        result = sanitize_url_for_logging("http://health.gov.ie/path/")
        assert result == "health.gov.ie"

    def test_url_with_port(self):
        result = sanitize_url_for_logging("https://example.com:8443/path")
        assert result == "example.com:8443"

    def test_invalid_url(self):
        assert sanitize_url_for_logging(None) == "[invalid-url]"
        assert sanitize_url_for_logging("") == "[invalid-url]"
        assert sanitize_url_for_logging("not a url") == "[invalid-url]"
        assert sanitize_url_for_logging(123) == "[invalid-url]"

    def test_long_domain_truncated(self):
        long_domain = "a" * 60 + ".com"
        result = sanitize_url_for_logging(f"https://{long_domain}/path")
        assert len(result) <= 50
        assert "..." in result


class TestSanitizeErrorContext:
    """Tests for error context sanitization."""

    def test_url_sanitized_in_context(self):
        context = {
            "url": "https://example.com/secret/path?key=value",
            "name": "Test Body"
        }
        result = sanitize_error_context(context)
        assert result["url"] == "example.com"
        assert result["name"] == "Test Body"

    def test_api_key_redacted(self):
        context = {
            "api_key": "secret-key-12345",
            "url": "https://example.com"
        }
        result = sanitize_error_context(context)
        assert result["api_key"] == "[REDACTED]"
        assert result["url"] == "example.com"

    def test_case_insensitive_redaction(self):
        context = {
            "API_KEY": "secret",
            "Token": "token123",
            "PASSWORD": "pass"
        }
        result = sanitize_error_context(context)
        assert result["API_KEY"] == "[REDACTED]"
        assert result["Token"] == "[REDACTED]"
        assert result["PASSWORD"] == "[REDACTED]"

    def test_long_value_truncated(self):
        context = {
            "message": "A" * 300
        }
        result = sanitize_error_context(context)
        assert len(result["message"]) <= 200
        assert result["message"].endswith("...")

    def test_non_dict_returns_empty(self):
        assert sanitize_error_context(None) == {}
        assert sanitize_error_context("string") == {}
        assert sanitize_error_context(123) == {}


import sys
from scripts.file_utils import IncrementalWriter


class TestIncrementalWriter:
    def test_fresh_start_empty_results(self, tmp_path):
        w = IncrementalWriter(tmp_path / "output.json", "test_step")
        assert w.results == []
        assert w.processed_keys == set()

    def test_resume_loads_existing_results(self, tmp_path):
        existing = {
            "metadata": {"step": "test_step"},
            "results": [
                {"public_body_id": 1, "name": "A"},
                {"public_body_id": 2, "name": "B"},
            ],
        }
        write_json(tmp_path / "output.json", existing)
        w = IncrementalWriter(tmp_path / "output.json", "test_step")
        assert len(w.results) == 2
        assert w.processed_keys == {1, 2}

    def test_force_ignores_existing_output(self, tmp_path):
        existing = {
            "metadata": {"step": "test_step"},
            "results": [{"public_body_id": 1}],
        }
        write_json(tmp_path / "output.json", existing)
        w = IncrementalWriter(tmp_path / "output.json", "test_step", force=True)
        assert w.results == []
        assert w.processed_keys == set()

    def test_is_processed_returns_true_for_loaded_key(self, tmp_path):
        existing = {
            "metadata": {"step": "test_step"},
            "results": [{"public_body_id": 42}],
        }
        write_json(tmp_path / "output.json", existing)
        w = IncrementalWriter(tmp_path / "output.json", "test_step")
        assert w.is_processed(42) is True
        assert w.is_processed(99) is False

    def test_append_empty_writes_partial_and_prints_dot(self, tmp_path, capsys):
        w = IncrementalWriter(tmp_path / "output.json", "test_step")
        w.append([])
        out = capsys.readouterr().out
        assert "." in out
        data = read_json(tmp_path / "output.json")
        assert data["results"] == []
        assert "completed_at" not in data["metadata"]

    def test_append_items_extends_results_and_writes(self, tmp_path):
        w = IncrementalWriter(tmp_path / "output.json", "test_step")
        w.append([{"public_body_id": 1, "val": "x"}])
        w.append([{"public_body_id": 2, "val": "y"}, {"public_body_id": 2, "val": "z"}])
        assert len(w.results) == 3
        data = read_json(tmp_path / "output.json")
        assert len(data["results"]) == 3

    def test_append_updates_processed_keys(self, tmp_path):
        w = IncrementalWriter(tmp_path / "output.json", "test_step")
        w.append([{"public_body_id": 7}])
        assert 7 in w.processed_keys

    def test_append_empty_does_not_update_processed_keys(self, tmp_path):
        w = IncrementalWriter(tmp_path / "output.json", "test_step")
        w.append([])
        assert w.processed_keys == set()

    def test_finalize_adds_completed_at(self, tmp_path):
        w = IncrementalWriter(tmp_path / "output.json", "test_step")
        w.append([{"public_body_id": 1}])
        w.finalize()
        data = read_json(tmp_path / "output.json")
        assert "completed_at" in data["metadata"]

    def test_finalize_returns_count(self, tmp_path):
        w = IncrementalWriter(tmp_path / "output.json", "test_step")
        w.append([{"public_body_id": 1}, {"public_body_id": 2}])
        assert w.finalize() == 2

    def test_finalize_prints_newline(self, tmp_path, capsys):
        w = IncrementalWriter(tmp_path / "output.json", "test_step")
        w.finalize()
        out = capsys.readouterr().out
        assert "\n" in out

    def test_custom_key_field(self, tmp_path):
        existing = {
            "metadata": {"step": "test_step"},
            "results": [{"file_url": "https://example.com/a.pdf"}],
        }
        write_json(tmp_path / "output.json", existing)
        w = IncrementalWriter(tmp_path / "output.json", "test_step", key_field="file_url")
        assert "https://example.com/a.pdf" in w.processed_keys

    def test_append_writes_atomically_via_tmp(self, tmp_path, monkeypatch):
        # Verify tmp file is used (replaced, not left behind)
        w = IncrementalWriter(tmp_path / "output.json", "test_step")
        w.append([{"public_body_id": 1}])
        assert not (tmp_path / "output.tmp").exists()
        assert (tmp_path / "output.json").exists()
