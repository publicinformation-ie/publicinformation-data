import pytest

from lib.value_kinds import cell_kinds, foreign_kind, strip_value_punctuation


@pytest.mark.parametrize("raw,expected", [
    ("Journalist.", "journalist"), ("Member of the \npublic.", "member of the public"),
    (".Journalist.", "journalist"), ("  Refused; ", "refused"),
])
def test_strip_value_punctuation(raw, expected):
    assert strip_value_punctuation(raw) == expected


def test_date_kinds():
    assert "date" in cell_kinds("17/07/2023")
    assert "date" in cell_kinds("04/01/2024  FOI/2024/0001")  # leading date in a merged cell (Fingal 2024 camelot_stream)


@pytest.mark.parametrize("ref", ["FOI/2016/0009", "001-25", "FOI 1020 - 2026", "97."])
def test_reference_not_date(ref):
    assert "date" not in cell_kinds(ref)
    assert foreign_kind(ref, "foi_reference_id") is None


def test_status_requester_header_kinds():
    assert "status" in cell_kinds("Part Grant")
    assert "requester" in cell_kinds("Journalist")
    assert "header" in cell_kinds("Decision")


def test_own_kind_wins():
    # any value recognised as its own role's kind is never foreign
    for role, value in [("requester_type", "Other"), ("decision_status", "Refused. Section 15(1)(a)."),
                        ("decision_date", "30/01/2024")]:
        assert foreign_kind(value, role) is None


def test_foreign_kinds_fingal_2023():
    assert foreign_kind("Journalist", "foi_reference_id") == "requester"
    assert foreign_kind("17/07/2023", "decision_status") == "date"


def test_unknown_value_not_foreign():
    assert foreign_kind("J ournalist.", "requester_type") is None
    assert foreign_kind("Interested business group", "requester_type") is None
