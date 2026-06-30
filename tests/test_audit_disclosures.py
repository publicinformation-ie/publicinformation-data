import sqlite3
import pytest
from lib.db_client import DbClient
from scripts.audit_disclosures import Check, CHECKS, get_check, run_checks, aggregate, format_report, parse_args, main


def test_check_dataclass_fields():
    c = Check(name="foo", description="Foo check", where_clause="foo IS NULL")
    assert c.name == "foo"
    assert c.description == "Foo check"
    assert c.where_clause == "foo IS NULL"


def test_checks_registry_has_seven_entries():
    assert len(CHECKS) == 7


def test_checks_registry_names():
    names = [c.name for c in CHECKS]
    assert "blank_request_description" in names
    assert "invalid_decision_date" in names
    assert "invalid_date_received" in names
    assert "decision_status_is_date" in names
    assert "decision_status_is_slashdate" in names
    assert "decision_status_nonstandard" in names
    assert "requester_type_nonstandard" in names


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
            decision_status TEXT,
            requester_type TEXT
        )
    """)
    for row in rows:
        conn.execute(
            "INSERT INTO foi_disclosures VALUES (?, ?, ?, ?, ?, ?)",
            (
                row.get("file_url"),
                row.get("request_description"),
                row.get("decision_date"),
                row.get("date_received"),
                row.get("decision_status"),
                row.get("requester_type"),
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


def test_aggregate_sorts_descending():
    raw = {
        "https://a.ie/1.pdf": {"blank_request_description": 5, "invalid_decision_date": 3},
        "https://b.ie/2.pdf": {"blank_request_description": 1},
        "https://c.ie/3.pdf": {"decision_status_is_date": 10},
    }
    result = aggregate(raw)
    assert result[0][0] == "https://c.ie/3.pdf"
    assert result[0][1] == 10
    assert result[1][0] == "https://a.ie/1.pdf"
    assert result[1][1] == 8
    assert result[2][0] == "https://b.ie/2.pdf"
    assert result[2][1] == 1


def test_aggregate_min_errors_filter():
    raw = {
        "https://a.ie/1.pdf": {"blank_request_description": 1},
        "https://b.ie/2.pdf": {"blank_request_description": 5},
    }
    result = aggregate(raw, min_errors=3)
    assert len(result) == 1
    assert result[0][0] == "https://b.ie/2.pdf"


def test_aggregate_preserves_per_check_counts():
    raw = {
        "https://a.ie/1.pdf": {"blank_request_description": 7, "invalid_date_received": 2},
    }
    result = aggregate(raw)
    assert result[0][2] == {"blank_request_description": 7, "invalid_date_received": 2}


def test_aggregate_empty():
    assert aggregate({}) == []


def test_format_report_check_summary_line():
    checks = [c for c in CHECKS if c.name == "blank_request_description"]
    raw = {
        "https://a.ie/1.pdf": {"blank_request_description": 10},
        "https://b.ie/2.pdf": {"blank_request_description": 5},
    }
    ranked = [
        ("https://a.ie/1.pdf", 10, {"blank_request_description": 10}),
        ("https://b.ie/2.pdf", 5, {"blank_request_description": 5}),
    ]
    report = format_report(checks, raw, ranked, top=20, run_date="2026-06-23")
    assert "CHECK SUMMARY" in report
    assert "blank_request_description" in report
    assert "15 rows in  2 files" in report


def test_format_report_file_ranking():
    checks = [c for c in CHECKS if c.name == "blank_request_description"]
    raw = {"https://a.ie/1.pdf": {"blank_request_description": 7}}
    ranked = [("https://a.ie/1.pdf", 7, {"blank_request_description": 7})]
    report = format_report(checks, raw, ranked, top=20, run_date="2026-06-23")
    assert "TOP 20 FILES BY ERROR COUNT" in report
    assert "1. https://a.ie/1.pdf" in report
    assert "(7 errors)" in report
    assert "blank_request_description: 7" in report


def test_format_report_top_limits_files():
    checks = [c for c in CHECKS if c.name == "blank_request_description"]
    raw = {f"https://a.ie/{i}.pdf": {"blank_request_description": i} for i in range(1, 6)}
    ranked = [(f"https://a.ie/{i}.pdf", i, {"blank_request_description": i}) for i in range(5, 0, -1)]
    report = format_report(checks, raw, ranked, top=3, run_date="2026-06-23")
    assert "TOP 3 FILES BY ERROR COUNT" in report
    assert "1. https://a.ie/5.pdf" in report
    assert "https://a.ie/1.pdf" not in report


def test_format_report_header():
    report = format_report(CHECKS, {}, [], top=20, run_date="2026-06-23")
    assert "FOI Disclosures Quality Report" in report
    assert "7 checks" in report
    assert "2026-06-23" in report


def test_format_report_no_errors():
    report = format_report(CHECKS, {}, [], top=20, run_date="2026-06-23")
    assert "No issues found." in report


def test_parse_args_defaults():
    args = parse_args([])
    assert args.top == 20
    assert args.check is None
    assert args.min_errors == 1


def test_parse_args_top():
    args = parse_args(["--top", "5"])
    assert args.top == 5


def test_parse_args_check():
    args = parse_args(["--check", "invalid_decision_date"])
    assert args.check == "invalid_decision_date"


def test_parse_args_min_errors():
    args = parse_args(["--min-errors", "3"])
    assert args.min_errors == 3


def test_main_unknown_check(capsys):
    code = main(["--check", "nonexistent_check"])
    assert code == 1
    captured = capsys.readouterr()
    assert "unknown check" in captured.err
    assert "nonexistent_check" in captured.err


def test_main_missing_database(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", str(tmp_path / "missing.db"))
    code = main([])
    assert code == 1
    captured = capsys.readouterr()
    assert "database not found" in captured.err
