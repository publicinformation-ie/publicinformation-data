import json
from pathlib import Path

import pytest
import requests as req

from steps.fetch_datacatalogue_orgs import process as fetch_mod
from steps.fetch_datacatalogue_orgs.process import (
    API_URL, build_record, fetch_orgs, filter_orgs,
)

FIXTURE = Path(__file__).parent / "fixtures" / "organization_list_page1.json"
FIXTURE_ORGS = json.loads(FIXTURE.read_text())["result"]


def _org(slug, **kw):
    base = {"name": slug, "display_name": slug.title(), "title": slug.title(),
            "package_count": 1, "type": "organization", "state": "active", "description": ""}
    return {**base, **kw}


def _mock_pages(requests_mock, *pages):
    """Serve `pages` in order for successive requests; an empty page after."""
    responses = [{"json": {"success": True, "result": p}} for p in pages]
    responses.append({"json": {"success": True, "result": []}})
    requests_mock.get(API_URL, responses)


def test_fixture_loads_with_real_shape():
    assert len(FIXTURE_ORGS) == 3
    assert all(o["type"] == "organization" and o["state"] == "active" for o in FIXTURE_ORGS)


def test_filter_orgs_excludes_non_organization_type_and_inactive():
    raw = [_org("keep"), _org("a-group", type="group"), _org("gone", state="deleted"),
           _org("draft", state="draft")]
    assert [o["name"] for o in filter_orgs(raw)] == ["keep"]


def test_build_record_url_format_and_fields():
    rec = build_record(_org("revenue-commissioners", display_name="Revenue Commissioners",
                            package_count=7, description="  Tax body.  "))
    assert rec == {
        "datacatalogue_slug": "revenue-commissioners",
        "datacatalogue_name": "Revenue Commissioners",
        "datacatalogue_url": "https://datacatalogue.gov.ie/organization/revenue-commissioners",
        "datacatalogue_package_count": 7,
        "datacatalogue_description": "Tax body.",
    }


def test_build_record_omits_absent_optional_fields():
    org = {"name": "x", "display_name": "X"}
    assert set(build_record(org)) == {"datacatalogue_slug", "datacatalogue_name", "datacatalogue_url"}


def test_build_record_keeps_zero_package_count_but_drops_empty_description():
    rec = build_record(_org("x", package_count=0, description=""))
    assert rec["datacatalogue_package_count"] == 0
    assert "datacatalogue_description" not in rec


def test_build_record_uses_display_name_when_title_empty():
    assert build_record(_org("x", title="", display_name="X Body"))["datacatalogue_name"] == "X Body"


def test_fetch_orgs_follows_pagination(requests_mock):
    _mock_pages(requests_mock, [_org("a"), _org("b")], [_org("c")])
    records = fetch_orgs()
    assert [r["datacatalogue_slug"] for r in records] == ["a", "b", "c"]
    offsets = [r.qs["offset"][0] for r in requests_mock.request_history]
    assert offsets == ["0", "2", "3"]


def test_fetch_orgs_pages_beyond_page_size(requests_mock):
    first = [_org(f"o{i}") for i in range(fetch_mod.PAGE_SIZE)]
    second = [_org("last")]
    _mock_pages(requests_mock, first, second)
    assert len(fetch_orgs()) == fetch_mod.PAGE_SIZE + 1


def test_fetch_orgs_drops_inactive_entries(requests_mock):
    _mock_pages(requests_mock, [_org("a"), _org("gone", state="deleted"), _org("g", type="group")])
    assert [r["datacatalogue_slug"] for r in fetch_orgs()] == ["a"]


def test_fetch_orgs_rejects_duplicate_slugs(requests_mock, capsys):
    _mock_pages(requests_mock, [_org("a"), _org("b")], [_org("a")])
    with pytest.raises(SystemExit) as exc:
        fetch_orgs()
    assert exc.value.code != 0
    assert "duplicate" in capsys.readouterr().err


def test_fetch_orgs_fatal_on_zero_orgs(requests_mock):
    _mock_pages(requests_mock)
    with pytest.raises(SystemExit) as exc:
        fetch_orgs()
    assert exc.value.code != 0


def test_fetch_orgs_fatal_when_only_inactive(requests_mock):
    _mock_pages(requests_mock, [_org("gone", state="deleted")])
    with pytest.raises(SystemExit):
        fetch_orgs()


def test_fetch_orgs_fatal_on_success_false(requests_mock):
    requests_mock.get(API_URL, json={"success": False, "error": {"message": "boom"}})
    with pytest.raises(SystemExit) as exc:
        fetch_orgs()
    assert exc.value.code != 0


def test_fetch_orgs_fatal_on_http_error(requests_mock):
    requests_mock.get(API_URL, status_code=500)
    with pytest.raises(SystemExit):
        fetch_orgs()


def test_fetch_orgs_fatal_on_unparseable_response(requests_mock):
    requests_mock.get(API_URL, text="<html>not json</html>")
    with pytest.raises(SystemExit):
        fetch_orgs()


def test_fetch_orgs_fatal_on_request_failure(requests_mock):
    requests_mock.get(API_URL, exc=req.exceptions.ConnectionError("refused"))
    with pytest.raises(SystemExit):
        fetch_orgs()


def test_failure_after_first_page_writes_no_output(requests_mock, tmp_path, monkeypatch):
    import sys
    requests_mock.get(API_URL, [
        {"json": {"success": True, "result": [_org("a")]}},
        {"status_code": 500},
    ])
    out = tmp_path / "output.json"
    monkeypatch.setattr(sys, "argv", ["process.py", "--input", "x", "--output", str(out), "--force"])
    with pytest.raises(SystemExit) as exc:
        fetch_mod.main()
    assert exc.value.code != 0
    assert not out.exists()
