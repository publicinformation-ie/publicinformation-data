import sqlite3
import pytest
from lib.db_client import DbClient
from scripts.audit_disclosures import Check, CHECKS, get_check, run_checks


def test_check_dataclass_fields():
    c = Check(name="foo", description="Foo check", where_clause="foo IS NULL")
    assert c.name == "foo"
    assert c.description == "Foo check"
    assert c.where_clause == "foo IS NULL"


def test_checks_registry_has_four_entries():
    assert len(CHECKS) == 4


def test_checks_registry_names():
    names = [c.name for c in CHECKS]
    assert "blank_request_description" in names
    assert "invalid_decision_date" in names
    assert "invalid_date_received" in names
    assert "decision_status_is_date" in names


def test_get_check_found():
    c = get_check("blank_request_description")
    assert c is not None
    assert c.name == "blank_request_description"


def test_get_check_not_found():
    assert get_check("nonexistent") is None


def _make_db_with_disclosures(rows: list[dict]) -> DbClient:
    """Build an in-memory SQLite DB with foi_disclosures rows for testing."""
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE foi_disclosures (
            file_url TEXT,
            request_description TEXT,
            decision_date TEXT,
            date_received TEXT,
            decision_status TEXT
        )
    """)
    for row in rows:
        conn.execute(
            "INSERT INTO foi_disclosures VALUES (?, ?, ?, ?, ?)",
            (
                row.get("file_url"),
                row.get("request_description"),
                row.get("decision_date"),
                row.get("date_received"),
                row.get("decision_status"),
            ),
        )
    conn.commit()
    db = DbClient.__new__(DbClient)
    db._local = True
    db._conn = conn
    db._conn.row_factory = sqlite3.Row
    return db


def test_run_checks_blank_request_description():
    db = _make_db_with_disclosures([
        {"file_url": "https://a.ie/1.pdf", "request_description": None},
        {"file_url": "https://a.ie/1.pdf", "request_description": ""},
        {"file_url": "https://a.ie/1.pdf", "request_description": "valid"},
        {"file_url": "https://b.ie/2.pdf", "request_description": "also valid"},
    ])
    checks = [c for c in CHECKS if c.name == "blank_request_description"]
    result = run_checks(db, checks)
    assert result["https://a.ie/1.pdf"]["blank_request_description"] == 2
    assert "https://b.ie/2.pdf" not in result


def test_run_checks_invalid_decision_date():
    db = _make_db_with_disclosures([
        {"file_url": "https://a.ie/1.pdf", "decision_date": "not-a-date"},
        {"file_url": "https://a.ie/1.pdf", "decision_date": "2023-01-15"},
        {"file_url": "https://a.ie/1.pdf", "decision_date": None},
    ])
    checks = [c for c in CHECKS if c.name == "invalid_decision_date"]
    result = run_checks(db, checks)
    assert result["https://a.ie/1.pdf"]["invalid_decision_date"] == 1


def test_run_checks_multiple_checks_accumulate():
    db = _make_db_with_disclosures([
        {"file_url": "https://a.ie/1.pdf", "request_description": None, "decision_date": "bad"},
        {"file_url": "https://a.ie/1.pdf", "request_description": None, "decision_date": "2023-01-01"},
    ])
    result = run_checks(db, CHECKS)
    file_result = result.get("https://a.ie/1.pdf", {})
    assert file_result.get("blank_request_description", 0) == 2
    assert file_result.get("invalid_decision_date", 0) == 1


def test_run_checks_empty_db():
    db = _make_db_with_disclosures([])
    result = run_checks(db, CHECKS)
    assert result == {}
