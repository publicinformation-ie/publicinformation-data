import pytest

from steps.fetch_datagovie_orgs.process import filter_orgs, build_record, fetch_orgs, API_URL


RAW_ORGS = [
    {"name": "an-garda-siochana", "title": "An Garda Síochána", "display_name": "An Garda Síochána",
     "package_count": 3, "type": "organization", "state": "active"},
    {"name": "3d", "title": "", "display_name": "3d",
     "package_count": 1, "type": "organization", "state": "active"},
    {"name": "some-group", "title": "Some Group", "display_name": "Some Group",
     "package_count": 0, "type": "group", "state": "active"},
    {"name": "deleted-org", "title": "Deleted Org", "display_name": "Deleted Org",
     "package_count": 0, "type": "organization", "state": "deleted"},
]


def test_filter_orgs_excludes_non_organization_type():
    filtered = filter_orgs(RAW_ORGS)
    assert not any(o["name"] == "some-group" for o in filtered)


def test_filter_orgs_excludes_inactive_state():
    filtered = filter_orgs(RAW_ORGS)
    assert not any(o["name"] == "deleted-org" for o in filtered)


def test_filter_orgs_keeps_active_organizations():
    filtered = filter_orgs(RAW_ORGS)
    assert {o["name"] for o in filtered} == {"an-garda-siochana", "3d"}


def test_build_record_uses_display_name_and_constructs_url():
    record = build_record(RAW_ORGS[0])
    assert record == {
        "datagovie_slug": "an-garda-siochana",
        "datagovie_name": "An Garda Síochána",
        "datagovie_url": "https://data.gov.ie/organization/an-garda-siochana",
        "datagovie_package_count": 3,
    }


def test_build_record_uses_display_name_when_title_empty():
    record = build_record(RAW_ORGS[1])
    assert record["datagovie_name"] == "3d"


def test_fetch_orgs_returns_records_on_success(requests_mock):
    requests_mock.get(API_URL, json={"success": True, "result": RAW_ORGS})
    records = fetch_orgs()
    assert {r["datagovie_slug"] for r in records} == {"an-garda-siochana", "3d"}


def test_fetch_orgs_fatal_exits_on_success_false(requests_mock):
    requests_mock.get(API_URL, json={"success": False, "error": {"message": "boom"}})
    with pytest.raises(SystemExit) as exc:
        fetch_orgs()
    assert exc.value.code != 0


def test_fetch_orgs_fatal_exits_on_zero_records(requests_mock):
    requests_mock.get(API_URL, json={"success": True, "result": []})
    with pytest.raises(SystemExit):
        fetch_orgs()


def test_fetch_orgs_fatal_exits_on_request_failure(requests_mock):
    import requests as req
    requests_mock.get(API_URL, exc=req.exceptions.ConnectionError("refused"))
    with pytest.raises(SystemExit):
        fetch_orgs()
