import pytest

from steps.fetch_staff_numbers.process import (
    EXPECTED_COLUMNS, build_records, latest_period, parse_fte, parse_quarter, read_source,
)

HEADER = ",".join(EXPECTED_COLUMNS)


def _csv(*lines):
    return ("\n".join([HEADER, *lines]) + "\n").encode()


def test_parse_fte_handles_thousands_separators():
    assert parse_fte("3,960.56") == 3960.56
    assert parse_fte("0.00") == 0.0
    assert parse_fte(" 70.60 ") == 70.6


@pytest.mark.parametrize("bad", ["", "n/a", "-5", "NaN", "1.2.3"])
def test_parse_fte_rejects_non_numbers(bad):
    assert parse_fte(bad) is None


def test_parse_quarter():
    assert parse_quarter("Qtr 4") == 4
    assert parse_quarter("Q4") is None


def test_read_source_rejects_changed_columns():
    with pytest.raises(ValueError, match="unexpected columns"):
        read_source(b"Year,Quarter,FTE\n2025,Qtr 4,1\n")


def test_latest_period_picks_newest_quarter():
    rows = read_source(_csv("2024,Qtr 4,a,b,c,d,e,,1", "2025,Qtr 2,a,b,c,d,e,,1", "2025,Qtr 1,a,b,c,d,e,,1"))
    assert latest_period(rows) == (2025, 2)


def test_source_name_is_level_6_else_level_5():
    rows = read_source(_csv(
        '2025,Qtr 4,G,Dept,Ncsa,Non Commercial State Agencies,Ncsa - Active,Bord Bia,172.60',
        '2025,Qtr 4,G,Local Authorities,Local Authorities,Local Authorities,County Council - Leitrim,,342.74',
        '2025,Qtr 3,G,Dept,Ncsa,Non Commercial State Agencies,Ncsa - Active,Old Row,1.00',
    ))
    recs = build_records(rows, 2025, 4, "http://x")
    assert [r["source_name"] for r in recs] == ["Bord Bia", "County Council - Leitrim"]
    assert recs[1]["source_key"] == "Local Authorities | County Council - Leitrim"
    assert recs[0]["fte"] == 172.6


def test_duplicate_source_key_is_fatal():
    rows = read_source(_csv("2025,Qtr 4,G,D,C,K,Same,,1", "2025,Qtr 4,G,D,C,K,Same,,2"))
    with pytest.raises(ValueError, match="duplicate source key"):
        build_records(rows, 2025, 4, "http://x")


def test_unparseable_fte_is_logged_not_guessed(tmp_path):
    rows = read_source(_csv("2025,Qtr 4,G,D,C,K,Name,,oops"))
    recs = build_records(rows, 2025, 4, "http://x", step_dir=tmp_path)
    assert recs[0]["fte"] is None
    assert "unparseable_fte" in (tmp_path / "errors.json").read_text()
