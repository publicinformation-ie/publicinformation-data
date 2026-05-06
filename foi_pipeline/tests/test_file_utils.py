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
