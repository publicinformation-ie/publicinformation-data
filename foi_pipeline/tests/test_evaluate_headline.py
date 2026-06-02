import evaluate_headline as headline


def test_is_valid_record_requires_decision_date_and_summary():
    assert headline.is_valid_record(
        {"decision_date": "2019-04-11T00:00:00", "request_description": "x"}) is True
    assert headline.is_valid_record(
        {"decision_date": "2019-04-11T00:00:00", "request_description": ""}) is False
    assert headline.is_valid_record(
        {"decision_date": "not a date", "request_description": "x"}) is False
    assert headline.is_valid_record(
        {"decision_date": None, "request_description": "x"}) is False


def test_compute_headline_counts_records_and_bodies():
    records = [
        {"public_body_id": 1, "decision_date": "2019-04-11T00:00:00", "request_description": "a"},
        {"public_body_id": 1, "decision_date": "2019-05-11T00:00:00", "request_description": "b"},
        {"public_body_id": 2, "decision_date": None, "request_description": "c"},  # invalid
    ]
    h = headline.compute_headline(records)
    assert h["valid_records"] == 2
    assert h["bodies_with_record"] == 1


def test_bonus_coverage_tracks_decision_and_reference():
    records = [
        {"public_body_id": 1, "decision_date": "2019-04-11T00:00:00",
         "request_description": "a", "decision_status": "Granted", "foi_reference_id": "R1"},
        {"public_body_id": 1, "decision_date": "2019-05-11T00:00:00",
         "request_description": "b", "decision_status": None, "foi_reference_id": None},
    ]
    h = headline.compute_headline(records)
    assert h["bonus_coverage"]["decision_status"] == 0.5
    assert h["bonus_coverage"]["foi_reference_id"] == 0.5
