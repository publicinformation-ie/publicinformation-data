from lib.date_parse import EMPTY_STRUCTURED, PRECISIONS, parse_date, structured_fields


def test_bare_year():
    assert parse_date("2029") == {
        "year": 2029, "quarter": None, "month": None, "day": None,
        "precision": "year", "start": "2029-01-01", "end": "2029-12-31"}


def test_quarter():
    parsed = parse_date("Q4 2024")
    assert parsed["precision"] == "quarter"
    assert (parsed["start"], parsed["end"]) == ("2024-10-01", "2024-12-31")


def test_quarter_year_first_form():
    """The progress reports write the quarter as `2022 Q4`, not `Q4 2022` —
    both forms must parse to the same structured date."""
    assert parse_date("2022 Q4") == parse_date("Q4 2022")


def test_quarter_range_has_no_single_year_or_quarter():
    parsed = parse_date("Q1 2024 - Q3 2025")
    assert parsed["precision"] == "range"
    assert parsed["year"] is None and parsed["quarter"] is None
    assert (parsed["start"], parsed["end"]) == ("2024-01-01", "2025-09-30")


def test_month_and_day_forms():
    assert parse_date("March 2025")["precision"] == "month"
    assert parse_date("3 March 2025")["precision"] == "day"
    assert parse_date("2025-03-03")["precision"] == "day"


def test_unparseable_returns_none():
    assert parse_date("As soon as practicable") is None
    assert parse_date("") is None
    assert parse_date(None) is None


def test_open_ended_cells_have_an_explicit_precision():
    assert parse_date("Ongoing")["precision"] == "ongoing"
    assert parse_date("Annual")["precision"] == "annual"
    assert parse_date("Annual campaigns")["precision"] == "annual"
    assert parse_date("Annual grant subject to funding availability.")["precision"] == "annual"


def test_open_ended_cells_have_no_date_bounds():
    for text in ("Ongoing", "Annual campaigns"):
        parsed = parse_date(text)
        assert parsed["start"] is None
        assert parsed["end"] is None
        assert parsed["year"] is None


def test_an_annual_milestone_list_is_not_open_ended():
    assert parse_date(
        "Annual: Train 5,000 pupils. 2022: Programme commenced.") is None


def test_structured_fields_never_returns_the_shared_empty_dict():
    fields = structured_fields(None)
    assert fields == EMPTY_STRUCTURED
    assert fields is not EMPTY_STRUCTURED


def test_every_precision_the_parser_emits_is_declared():
    emitted = {parse_date(text)["precision"] for text in
               ("2029", "Q4 2024", "Q1 2024 - Q3 2025", "March 2025",
                "3 March 2025", "2025-03-03", "2024-2026", "Ongoing",
                "Annual")}
    assert emitted <= set(PRECISIONS)
