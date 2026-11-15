import pytest

from lib.value_kinds import _is_date


@pytest.mark.parametrize("text", [
    "04-Jan-18", "4-Jan-2018", "04-JAN-18", "04-jan-18", "4-jAn-2018",
    "04-Jan- 18",
])
def test_is_date_accepts_d_mon_yy(text):
    assert _is_date(text)


@pytest.mark.parametrize("text", [
    "2 7 - J a n -20", "Jan-18", "-Jan-18", "04-January-18", "04-Jan",
])
def test_is_date_rejects_garbled_or_incomplete(text):
    assert not _is_date(text)


@pytest.mark.parametrize("text", [
    "04/01/2018", "4.1.18", "04-01-2018", "1 February 2023",
])
def test_is_date_existing_formats_unchanged(text):
    assert _is_date(text)


@pytest.mark.parametrize("text", ["Granted", "FOI/2018/12", "hello world"])
def test_is_date_non_dates_unchanged(text):
    assert not _is_date(text)
