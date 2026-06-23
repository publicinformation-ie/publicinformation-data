import pytest
from scripts.audit_disclosures import Check, CHECKS, get_check


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
