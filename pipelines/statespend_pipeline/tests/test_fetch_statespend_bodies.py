import pytest

from steps.fetch_statespend_bodies.process import (
    build_record, fetch_bodies, fetch_page, API_URL, MIN_BODY_COUNT,
)

import steps.fetch_statespend_bodies.process as proc


def page_url(offset):
    return f"{API_URL}?dim=bodies&metric=count&limit={proc.PAGE_SIZE}&offset={offset}"


RAW_ROWS = [
    {"id": 52, "label": "Health Service Executive", "entity_type": "agency",
     "type_method": "inferred", "n": 78869},
    {"id": 68, "label": "Irish Water", "entity_type": "agency",
     "type_method": "inferred", "n": 412},
]


def test_build_record_namespaces_fields_and_constructs_url():
    record = build_record(RAW_ROWS[0])
    assert record == {
        "statespend_id": 52,
        "statespend_name": "Health Service Executive",
        "statespend_entity_type": "agency",
        "statespend_url": "https://statespend.ie/body/52",
    }


def test_fetch_page_returns_rows_on_success(requests_mock):
    requests_mock.get(page_url(0), json=RAW_ROWS)
    assert fetch_page(0) == RAW_ROWS


def test_fetch_page_fatal_exits_on_http_error(requests_mock):
    requests_mock.get(page_url(0), status_code=500)
    with pytest.raises(SystemExit):
        fetch_page(0)


def test_fetch_page_fatal_exits_on_non_json(requests_mock):
    # The SPA fallback returns 200 + HTML — must be rejected loudly
    requests_mock.get(page_url(0), text="<html><body>spa</body></html>")
    with pytest.raises(SystemExit):
        fetch_page(0)


def test_fetch_page_fatal_exits_on_unexpected_shape(requests_mock):
    requests_mock.get(page_url(0), json={"bodies": []})
    with pytest.raises(SystemExit):
        fetch_page(0)


def test_fetch_bodies_single_page_below_page_size(requests_mock):
    requests_mock.get(page_url(0), json=RAW_ROWS)
    monkey_min = MIN_BODY_COUNT
    proc.MIN_BODY_COUNT = 1
    try:
        records = fetch_bodies()
    finally:
        proc.MIN_BODY_COUNT = monkey_min
    assert [r["statespend_id"] for r in records] == [52, 68]


def test_fetch_bodies_paginates_until_short_page(requests_mock, monkeypatch):
    monkeypatch.setattr(proc, "PAGE_SIZE", 2)
    monkeypatch.setattr(proc, "MIN_BODY_COUNT", 3)
    rows = [{"id": i, "label": f"Body {i}", "entity_type": "agency"} for i in range(5)]
    requests_mock.get(f"{API_URL}?dim=bodies&metric=count&limit=2&offset=0", json=rows[0:2])
    requests_mock.get(f"{API_URL}?dim=bodies&metric=count&limit=2&offset=2", json=rows[2:4])
    requests_mock.get(f"{API_URL}?dim=bodies&metric=count&limit=2&offset=4", json=rows[4:])
    records = fetch_bodies()
    assert [r["statespend_id"] for r in records] == [0, 1, 2, 3, 4]


def test_fetch_bodies_fatal_exits_below_minimum_body_count(requests_mock, monkeypatch):
    monkeypatch.setattr(proc, "MIN_BODY_COUNT", 100)
    requests_mock.get(page_url(0), json=RAW_ROWS)
    with pytest.raises(SystemExit):
        fetch_bodies()


def test_fetch_bodies_fatal_exits_on_duplicate_ids(requests_mock, monkeypatch):
    monkeypatch.setattr(proc, "MIN_BODY_COUNT", 3)
    rows = [
        {"id": 7, "label": "Body A", "entity_type": "agency"},
        {"id": 8, "label": "Body B", "entity_type": "agency"},
        {"id": 9, "label": "Body C", "entity_type": "agency"},
        {"id": 7, "label": "Body A again", "entity_type": "agency"},
    ]
    requests_mock.get(page_url(0), json=rows)
    with pytest.raises(SystemExit):
        fetch_bodies()
