import pytest

from steps.fetch_lobbying_bodies.process import (
    filter_active, build_record, fetch_return_count, fetch_bodies,
    PUBLIC_BODY_URL, SEARCH_URL,
)


RAW_BODIES = [
    {"Id": 1571, "Name": "Some Public Body", "Order": None, "IsActive": True},
    {"Id": 1600, "Name": "Adoption Authority of Ireland", "Order": None, "IsActive": True},
    {"Id": 1234, "Name": "Retired Body", "Order": None, "IsActive": False},
]


def test_filter_active_excludes_inactive_bodies():
    filtered = filter_active(RAW_BODIES)
    assert {b["Id"] for b in filtered} == {1571, 1600}


def test_build_record_constructs_url():
    record = build_record({"Id": 1571, "Name": "Some Public Body"}, returns_count=1777)
    assert record == {
        "lobbyingie_id": 1571,
        "lobbyingie_name": "Some Public Body",
        "lobbyingie_url": "https://www.lobbying.ie/app/home/search?publicBodys=1571",
        "lobbyingie_returns_count": 1777,
    }


def test_fetch_return_count_returns_total_on_success(requests_mock):
    requests_mock.get(SEARCH_URL, json={"Total": 1777, "Data": []})
    assert fetch_return_count(1571) == 1777


def test_fetch_return_count_returns_none_on_request_failure(requests_mock):
    import requests as req
    requests_mock.get(SEARCH_URL, exc=req.exceptions.ConnectionError("refused"))
    assert fetch_return_count(1571) is None


def test_fetch_return_count_returns_none_on_missing_total(requests_mock):
    requests_mock.get(SEARCH_URL, json={"Data": []})
    assert fetch_return_count(1571) is None


def test_fetch_bodies_returns_records_on_success(requests_mock):
    requests_mock.get(PUBLIC_BODY_URL, json=RAW_BODIES)
    requests_mock.get(SEARCH_URL, json={"Total": 42, "Data": []})
    records = fetch_bodies()
    assert {r["lobbyingie_id"] for r in records} == {1571, 1600}
    assert all(r["lobbyingie_returns_count"] == 42 for r in records)


def test_fetch_bodies_does_not_fail_when_one_search_call_fails(requests_mock):
    import requests as req
    requests_mock.get(PUBLIC_BODY_URL, json=RAW_BODIES)
    requests_mock.get(
        SEARCH_URL,
        [
            {"json": {"Total": 42, "Data": []}},
            {"exc": req.exceptions.ConnectionError("refused")},
        ],
    )
    records = fetch_bodies()
    assert len(records) == 2
    assert None in {r["lobbyingie_returns_count"] for r in records}


def test_fetch_bodies_fatal_exits_on_malformed_response(requests_mock):
    requests_mock.get(PUBLIC_BODY_URL, json={"not": "a list"})
    with pytest.raises(SystemExit):
        fetch_bodies()


def test_fetch_bodies_fatal_exits_on_zero_active_records(requests_mock):
    requests_mock.get(PUBLIC_BODY_URL, json=[{"Id": 1, "Name": "X", "IsActive": False}])
    with pytest.raises(SystemExit):
        fetch_bodies()


def test_fetch_bodies_fatal_exits_on_request_failure(requests_mock):
    import requests as req
    requests_mock.get(PUBLIC_BODY_URL, exc=req.exceptions.ConnectionError("refused"))
    with pytest.raises(SystemExit):
        fetch_bodies()
