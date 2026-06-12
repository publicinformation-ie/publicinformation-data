import json
from pathlib import Path

import pytest

from lib.file_utils import (
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
from lib.file_utils import IncrementalWriter


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

    def test_force_with_target_public_body_preserves_other_bodies(self, tmp_path):
        existing = {
            "metadata": {"step": "test_step"},
            "results": [{"public_body_id": 1}, {"public_body_id": 2}],
        }
        write_json(tmp_path / "output.json", existing)
        w = IncrementalWriter(tmp_path / "output.json", "test_step", force=True,
                              target_public_body=2)
        # body 2 evicted for re-processing; body 1 retained
        assert len(w.results) == 1
        assert w.results[0]["public_body_id"] == 1
        assert 1 in w.processed_keys
        assert 2 not in w.processed_keys

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


class TestIncrementalWriterOverride:
    def test_override_records_preloaded(self, tmp_path):
        override_path = tmp_path / "override.json"
        write_json(override_path, [
            {"public_body_id": 99, "name": "Manual Body", "overridden": True, "source_method": "manual"}
        ])
        w = IncrementalWriter(tmp_path / "output.json", "test_step", override_path=override_path)
        assert 99 in w.processed_keys
        assert w.results[0]["public_body_id"] == 99
        assert w.results[0]["overridden"] is True

    def test_override_survives_force(self, tmp_path):
        override_path = tmp_path / "override.json"
        write_json(override_path, [
            {"public_body_id": 99, "name": "Manual Body", "overridden": True, "source_method": "manual"}
        ])
        w = IncrementalWriter(tmp_path / "output.json", "test_step", force=True, override_path=override_path)
        assert 99 in w.processed_keys
        assert len(w.results) == 1
        assert w.results[0]["public_body_id"] == 99

    def test_override_duplicate_first_wins(self, tmp_path):
        override_path = tmp_path / "override.json"
        write_json(override_path, [
            {"public_body_id": 99, "name": "First", "overridden": True},
            {"public_body_id": 99, "name": "Second", "overridden": True},
        ])
        w = IncrementalWriter(tmp_path / "output.json", "test_step", override_path=override_path)
        assert len([r for r in w.results if r["public_body_id"] == 99]) == 1
        assert w.results[0]["name"] == "First"

    def test_override_prints_notice(self, tmp_path, capsys):
        override_path = tmp_path / "override.json"
        write_json(override_path, [{"public_body_id": 99, "name": "Manual Body", "overridden": True}])
        IncrementalWriter(tmp_path / "output.json", "test_step", override_path=override_path)
        out = capsys.readouterr().out
        assert "Override" in out
        assert "99" in out

    def test_override_replaces_existing_output_record(self, tmp_path):
        output_path = tmp_path / "output.json"
        write_json(output_path, {
            "metadata": {"step": "test_step"},
            "results": [
                {"public_body_id": 99, "name": "Stale Name", "foi_page_url": "http://old.example.com", "disclosure_page_url": "http://old.example.com/disclosure"},
            ],
        })
        override_path = tmp_path / "override.json"
        write_json(override_path, [
            {"public_body_id": 99, "name": "Corrected Name", "foi_page_url": "http://new.example.com", "disclosure_page_url": "http://new.example.com/disclosure", "overridden": True},
        ])
        w = IncrementalWriter(output_path, "test_step", override_path=override_path)
        matching = [r for r in w.results if r["public_body_id"] == 99]
        assert len(matching) == 1
        assert matching[0]["name"] == "Corrected Name"
        assert matching[0].get("overridden") is True

    def test_override_missing_file_is_ignored(self, tmp_path):
        w = IncrementalWriter(tmp_path / "output.json", "test_step",
                              override_path=tmp_path / "nonexistent.json")
        assert w.results == []
        assert w.processed_keys == set()

    def test_invalid_override_raises_with_body_id(self, tmp_path):
        schema = {
            "type": "object",
            "required": ["metadata", "results"],
            "properties": {
                "metadata": {"type": "object"},
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["public_body_id", "name"],
                        "properties": {
                            "public_body_id": {"type": "integer"},
                            "name": {"type": "string"},
                        },
                    },
                },
            },
        }
        write_json(tmp_path / "output_schema.json", schema)
        override_path = tmp_path / "override.json"
        write_json(override_path, [{"public_body_id": 99}])  # missing required "name"
        with pytest.raises(ValueError, match="99"):
            IncrementalWriter(tmp_path / "output.json", "test_step", override_path=override_path)


class TestIncrementalWriterDirtyPropagation:
    _RECORD = {"public_body_id": 99, "name": "Body", "foi_page_url": "http://x.com", "disclosure_page_url": "http://x.com/d"}

    def _output_with(self, tmp_path, records):
        p = tmp_path / "output.json"
        write_json(p, {"metadata": {"step": "test_step"}, "results": records})
        return p

    def test_evicts_record_matching_dirty_id(self, tmp_path):
        output_path = self._output_with(tmp_path, [self._RECORD])
        dirty_path = tmp_path / "dirty_ids.json"
        write_json(dirty_path, [99])
        w = IncrementalWriter(output_path, "test_step", upstream_dirty_path=dirty_path)
        assert 99 not in w.processed_keys
        assert all(r["public_body_id"] != 99 for r in w.results)

    def test_eviction_not_processed_so_step_reruns(self, tmp_path):
        output_path = self._output_with(tmp_path, [self._RECORD])
        dirty_path = tmp_path / "dirty_ids.json"
        write_json(dirty_path, [99])
        w = IncrementalWriter(output_path, "test_step", upstream_dirty_path=dirty_path)
        assert not w.is_processed(99)

    def test_evicts_by_public_body_id_when_key_is_file_url(self, tmp_path):
        record = {**self._RECORD, "file_url": "http://x.com/file.pdf", "file_type": "pdf"}
        output_path = self._output_with(tmp_path, [record])
        dirty_path = tmp_path / "dirty_ids.json"
        write_json(dirty_path, [99])
        w = IncrementalWriter(output_path, "test_step", key_field="file_url",
                              upstream_dirty_path=dirty_path)
        assert "http://x.com/file.pdf" not in w.processed_keys
        assert w.results == []

    def test_finalize_writes_dirty_ids_json_after_eviction(self, tmp_path):
        output_path = self._output_with(tmp_path, [self._RECORD])
        dirty_path = tmp_path / "dirty_ids.json"
        write_json(dirty_path, [99])
        w = IncrementalWriter(output_path, "test_step", upstream_dirty_path=dirty_path)
        w.finalize()
        written = read_json(tmp_path / "dirty_ids.json")
        assert 99 in written

    def test_finalize_writes_empty_dirty_ids_when_no_eviction(self, tmp_path):
        output_path = self._output_with(tmp_path, [self._RECORD])
        w = IncrementalWriter(output_path, "test_step")
        w.finalize()
        written = read_json(tmp_path / "dirty_ids.json")
        assert written == []

    def test_override_marks_dirty_when_data_changes(self, tmp_path):
        output_path = self._output_with(tmp_path, [self._RECORD])
        changed = {**self._RECORD, "disclosure_page_url": "http://x.com/new"}
        override_path = tmp_path / "override.json"
        write_json(override_path, [changed])
        w = IncrementalWriter(output_path, "test_step", override_path=override_path)
        w.finalize()
        assert 99 in read_json(tmp_path / "dirty_ids.json")

    def test_override_does_not_mark_dirty_when_data_unchanged(self, tmp_path):
        output_path = self._output_with(tmp_path, [self._RECORD])
        override_path = tmp_path / "override.json"
        write_json(override_path, [self._RECORD])  # identical record
        w = IncrementalWriter(output_path, "test_step", override_path=override_path)
        w.finalize()
        assert read_json(tmp_path / "dirty_ids.json") == []

    def test_empty_upstream_dirty_file_is_ignored(self, tmp_path):
        output_path = self._output_with(tmp_path, [self._RECORD])
        dirty_path = tmp_path / "dirty_ids.json"
        write_json(dirty_path, [])
        w = IncrementalWriter(output_path, "test_step", upstream_dirty_path=dirty_path)
        assert 99 in w.processed_keys  # nothing evicted

    def test_nonexistent_upstream_dirty_file_is_ignored(self, tmp_path):
        output_path = self._output_with(tmp_path, [self._RECORD])
        w = IncrementalWriter(output_path, "test_step",
                              upstream_dirty_path=tmp_path / "nonexistent.json")
        assert 99 in w.processed_keys


import threading


def test_append_error_thread_safe(tmp_path):
    """Concurrent appends must not lose entries."""
    from lib.file_utils import append_error, read_json, write_json
    errors_path = tmp_path / "errors.json"
    write_json(errors_path, [])

    def add_error(i):
        append_error(tmp_path, {
            "step": "step",
            "timestamp": "2026-01-01T00:00:00+00:00",
            "error_type": "TestError",
            "error_message": f"error {i}",
            "context": {},
        })

    threads = [threading.Thread(target=add_error, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    errors = read_json(errors_path)
    assert len(errors) == 20, f"Expected 20 errors, got {len(errors)} — some were lost to race"


class TestIncrementalWriterTargetBody:
    def _output_with(self, tmp_path, records):
        p = tmp_path / "output.json"
        write_json(p, {"metadata": {"step": "test_step"}, "results": records})
        return p

    def test_target_body_evicts_only_that_body(self, tmp_path):
        records = [{"public_body_id": 1001}, {"public_body_id": 1002}, {"public_body_id": 1003}]
        output_path = self._output_with(tmp_path, records)
        w = IncrementalWriter(output_path, "test_step", target_public_body=1002)
        assert 1002 not in w.processed_keys
        assert 1001 in w.processed_keys
        assert 1003 in w.processed_keys
        assert all(r["public_body_id"] != 1002 for r in w.results)

    def test_target_body_not_processed_so_step_reruns(self, tmp_path):
        output_path = self._output_with(tmp_path, [{"public_body_id": 1002}])
        w = IncrementalWriter(output_path, "test_step", target_public_body=1002)
        assert not w.is_processed(1002)

    def test_target_body_marked_dirty_in_finalize(self, tmp_path):
        output_path = self._output_with(tmp_path, [{"public_body_id": 1002}])
        w = IncrementalWriter(output_path, "test_step", target_public_body=1002)
        w.finalize()
        assert 1002 in read_json(tmp_path / "dirty_ids.json")

    def test_target_body_none_is_noop(self, tmp_path):
        output_path = self._output_with(tmp_path, [{"public_body_id": 1001}])
        w = IncrementalWriter(output_path, "test_step", target_public_body=None)
        assert 1001 in w.processed_keys

    def test_target_body_evicts_all_file_rows_for_body(self, tmp_path):
        # key_field is file_url, but eviction is by public_body_id
        records = [
            {"public_body_id": 1002, "file_url": "a.pdf"},
            {"public_body_id": 1002, "file_url": "b.pdf"},
            {"public_body_id": 1003, "file_url": "c.pdf"},
        ]
        output_path = self._output_with(tmp_path, records)
        w = IncrementalWriter(output_path, "test_step", key_field="file_url",
                              target_public_body=1002)
        assert "a.pdf" not in w.processed_keys
        assert "b.pdf" not in w.processed_keys
        assert "c.pdf" in w.processed_keys
