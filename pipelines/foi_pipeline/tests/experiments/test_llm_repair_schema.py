"""Tests for the llm-structuring-repair schema module."""
import importlib.util
from pathlib import Path

_SCHEMA_PATH = (
    Path(__file__).parents[2]
    / "experiments/2026-07-15-llm-structuring-repair/schema.py"
)
_spec = importlib.util.spec_from_file_location("llm_repair_schema", _SCHEMA_PATH)
assert _spec is not None and _spec.loader is not None
_schema = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_schema)

CANONICAL_FIELDS = _schema.CANONICAL_FIELDS
entries_to_rows = _schema.entries_to_rows


def test_empty_entries_returns_empty():
    assert entries_to_rows([]) == []


def test_header_is_canonical_fields():
    rows = entries_to_rows([
        {
            "foi_reference_id": "FOI-1",
            "date_received": "2024-01-02",
            "request_description": "docs",
            "requester_type": "Journalist",
            "decision_status": "Granted",
            "decision_date": "2024-02-01",
        }
    ])
    assert rows[0] == CANONICAL_FIELDS
    assert rows[1] == [
        "FOI-1", "2024-01-02", "docs", "Journalist", "Granted", "2024-02-01",
    ]


def test_missing_and_null_fields_preserved_as_none():
    # A blank cell must render as None so has_null_column can see it.
    rows = entries_to_rows([
        {"foi_reference_id": "FOI-2", "date_received": None}
    ])
    assert rows[1][0] == "FOI-2"
    # date_received explicitly None, the other four absent -> all None.
    assert rows[1][1:] == [None, None, None, None, None]
