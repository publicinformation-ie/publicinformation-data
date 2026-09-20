from steps.find_meeting_minutes_pages_search.process import (
    STEP_NAME,
    _build_query,
    _pick_minutes_url,
    process,
)
import json
from unittest import mock

import pytest

from lib.file_utils import write_json, IncrementalWriter


def test_step_name():
    assert STEP_NAME == "find_meeting_minutes_pages_search"


def test_build_query():
    assert _build_query("https://www.dlrcoco.ie/", "Dun Laoghaire Rathdown County Council") == \
        "site:www.dlrcoco.ie Dun Laoghaire Rathdown County Council council meeting minutes"


def test_pick_prefers_explicit_minutes_link():
    results = [
        {"url": "https://www.x.ie/about/", "link": "https://www.x.ie/about/", "title": "About us"},
        {"url": "https://www.x.ie/council-minutes/", "link": "https://www.x.ie/council-minutes/",
         "title": "Council Minutes"},
    ]
    assert _pick_minutes_url(results) == "https://www.x.ie/council-minutes/"


def test_pick_rejects_everything():
    assert _pick_minutes_url([]) is None
    assert _pick_minutes_url([
        {"url": "https://www.x.ie/meeting-stuff/", "link": "https://www.x.ie/meeting-stuff/",
         "title": "Meeting stuff"},
    ]) is None
    assert _pick_minutes_url([
        {"url": "https://www.x.ie/ga/council-minutes/", "link": "https://www.x.ie/ga/council-minutes/",
         "title": "Council Minutes"},
    ]) is None
    assert _pick_minutes_url([
        {"url": "javascript:void(0)", "link": "javascript:void(0)", "title": "Council Minutes"},
    ]) is None


STEP = "find_meeting_minutes_pages_search"

YIELD_POSITIVE_HTML = ('<a href="/files/minutes-jan.pdf">Council Minutes January</a>')
YIELD_EMPTY_HTML = '<p>No documents here</p>'


def _resp_for(url):
    m = mock.Mock()
    m.text = ('<p>No documents here</p>' if "recent-minutes" in url
              else '<a href="/files/minutes-jan.pdf">Council Minutes January</a>')
    return m


def test_rerank_picks_yield_over_first_hit(monkeypatch):
    from steps.find_meeting_minutes_pages_search.process import _pick_minutes_url_yield
    monkeypatch.setattr(
        "steps.find_meeting_minutes_pages_search.process.fetch",
        lambda method, url, **kw: _resp_for(url))
    results = [
        {"url": "https://www.x.ie/recent-minutes/", "link": "https://www.x.ie/recent-minutes/",
         "title": "Council Meeting Minutes"},
        {"url": "https://www.x.ie/minutes/", "link": "https://www.x.ie/minutes/",
         "title": "Council Minutes"},
    ]
    assert _pick_minutes_url_yield(results) == "https://www.x.ie/minutes/"


def test_rerank_all_fetch_fail_returns_none(monkeypatch):
    from steps.find_meeting_minutes_pages_search.process import _pick_minutes_url_yield
    def _boom(method, url, **kw):
        raise ConnectionError("down")
    monkeypatch.setattr(
        "steps.find_meeting_minutes_pages_search.process.fetch", _boom)
    results = [
        {"url": "https://www.x.ie/minutes/", "link": "https://www.x.ie/minutes/",
         "title": "Council Minutes"},
    ]
    assert _pick_minutes_url_yield(results) is None


CRAWL_OUTPUT = {
    "metadata": {"step": "find_meeting_minutes_pages", "completed_at": "2026-06-01T00:00:00+00:00"},
    "results": [
        {"public_body_id": 1511, "municipal_district": None,
         "minutes_page_url": "https://www.meath.ie/council-meetings", "source_method": "crawl"},
        {"public_body_id": 1511, "municipal_district": "Navan",
         "minutes_page_url": "https://www.meath.ie/navan-meetings", "source_method": "crawl"},
    ],
}

CRAWL_ERRORS = [
    {"step": "find_meeting_minutes_pages", "error_type": "ValueError",
     "error_message": "no minutes page link above threshold on homepage",
     "context": {"url": "https://www.dlrcoco.ie/", "public_body_id": 1244,
                 "municipal_district": None}},
]

AUTHORITIES = {
    1244: {"public_body_id": 1244, "name": "Dun Laoghaire Rathdown County Council",
            "official_website_url": "https://www.dlrcoco.ie/", "municipal_districts": []},
}

QUERY = ("site:www.dlrcoco.ie Dun Laoghaire Rathdown County Council "
         "council meeting minutes")


def test_multi_record_body_passes_through_intact(tmp_path, make_writer):
    writer = make_writer(STEP, key_field="minutes_page_url")
    process(CRAWL_OUTPUT, tmp_path, writer)
    assert len(writer.results) == 2
    assert {r["minutes_page_url"] for r in writer.results} == {
        "https://www.meath.ie/council-meetings", "https://www.meath.ie/navan-meetings"}


def test_resume_skips_already_present_pages(tmp_path, make_writer):
    writer = make_writer(STEP, key_field="minutes_page_url")
    writer.results = [dict(CRAWL_OUTPUT["results"][0])]
    writer.processed_keys = {"https://www.meath.ie/council-meetings"}
    process(CRAWL_OUTPUT, tmp_path, writer)
    assert len(writer.results) == 2


def test_search_finds_minutes_url_for_failed_body(tmp_path, make_writer, monkeypatch):
    monkeypatch.setattr(
        "steps.find_meeting_minutes_pages_search.process.batch_search",
        lambda queries, api_token=None: {QUERY: [
            {"url": "https://www.dlrcoco.ie/about/", "link": "https://www.dlrcoco.ie/about/",
             "title": "About"},
            {"url": "https://www.dlrcoco.ie/council-minutes/",
             "link": "https://www.dlrcoco.ie/council-minutes/", "title": "Council Minutes"},
        ]},
    )
    monkeypatch.setattr(
        "steps.find_meeting_minutes_pages_search.process.fetch",
        lambda method, url, **kw: _resp_for(url))
    writer = make_writer(STEP, key_field="minutes_page_url")
    process({"metadata": CRAWL_OUTPUT["metadata"], "results": []}, tmp_path, writer,
            crawl_errors=CRAWL_ERRORS, authorities_by_id=AUTHORITIES)
    found = [r for r in writer.results if r["public_body_id"] == 1244]
    assert len(found) == 1
    assert found[0]["minutes_page_url"] == "https://www.dlrcoco.ie/council-minutes/"
    assert found[0]["source_method"] == "apify"
    assert found[0]["municipal_district"] is None


def test_body_already_in_output_is_not_searched(tmp_path, make_writer, monkeypatch):
    called = []
    def _boom(queries, api_token=None):
        called.append(queries)
        return {}
    monkeypatch.setattr(
        "steps.find_meeting_minutes_pages_search.process.batch_search", _boom)
    def _no_fetch(method, url, **kw):
        raise AssertionError("fetch must not be called")
    monkeypatch.setattr(
        "steps.find_meeting_minutes_pages_search.process.fetch", _no_fetch)
    writer = make_writer(STEP, key_field="minutes_page_url")
    writer.results = [{"public_body_id": 1244, "municipal_district": None,
                       "minutes_page_url": "https://www.dlrcoco.ie/known/",
                       "source_method": "crawl"}]
    writer.processed_keys = {"https://www.dlrcoco.ie/known/"}
    process({"metadata": CRAWL_OUTPUT["metadata"], "results": []}, tmp_path, writer,
            crawl_errors=CRAWL_ERRORS, authorities_by_id=AUTHORITIES)
    assert called == []
    assert len(writer.results) == 1


def test_not_found_goes_to_errors_json(tmp_path, make_writer, monkeypatch):
    monkeypatch.setattr(
        "steps.find_meeting_minutes_pages_search.process.batch_search",
        lambda queries, api_token=None: {QUERY: []},
    )
    writer = make_writer(STEP, key_field="minutes_page_url")
    process({"metadata": CRAWL_OUTPUT["metadata"], "results": []}, tmp_path, writer,
            crawl_errors=CRAWL_ERRORS, authorities_by_id=AUTHORITIES)
    assert all(r["public_body_id"] != 1244 for r in writer.results)
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert any(e["error_type"] == "MinutesPageNotFound"
               and e["context"]["public_body_id"] == 1244 for e in errors)


def test_null_website_skipped_without_search(tmp_path, make_writer, monkeypatch):
    def _boom(queries, api_token=None):
        raise AssertionError("batch_search must not be called")
    monkeypatch.setattr(
        "steps.find_meeting_minutes_pages_search.process.batch_search", _boom)
    null_errors = [dict(CRAWL_ERRORS[0])]
    null_errors[0] = dict(null_errors[0])
    null_errors[0]["context"] = {"url": None, "public_body_id": 1085,
                                 "municipal_district": None}
    null_authorities = {1085: {"public_body_id": 1085, "name": "Carlow County Council",
                               "official_website_url": None, "municipal_districts": []}}
    writer = make_writer(STEP, key_field="minutes_page_url")
    process({"metadata": CRAWL_OUTPUT["metadata"], "results": []}, tmp_path, writer,
            crawl_errors=null_errors, authorities_by_id=null_authorities)
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert any(e["error_type"] == "MissingWebsiteUrl"
               and e["context"]["public_body_id"] == 1085 for e in errors)


def test_override_record_is_preserved(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "steps.find_meeting_minutes_pages_search.process.batch_search",
        lambda queries, api_token=None: {},
    )
    override_path = tmp_path / "override.json"
    write_json(override_path, [{
        "public_body_id": 1244, "municipal_district": None,
        "minutes_page_url": "https://www.dlrcoco.ie/override-minutes/",
        "source_method": "manual", "overridden": True,
    }])
    writer = IncrementalWriter(tmp_path / "output.json", STEP,
                               key_field="minutes_page_url",
                               override_path=override_path)
    process({"metadata": CRAWL_OUTPUT["metadata"], "results": []}, tmp_path, writer,
            crawl_errors=[])
    r = next(r for r in writer.results if r["public_body_id"] == 1244)
    assert r["minutes_page_url"] == "https://www.dlrcoco.ie/override-minutes/"
    assert r["source_method"] == "manual"


def test_missing_apify_token_raises(tmp_path, make_writer, monkeypatch):
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    writer = make_writer(STEP, key_field="minutes_page_url")
    with pytest.raises(RuntimeError, match="APIFY_TOKEN"):
        process({"metadata": CRAWL_OUTPUT["metadata"], "results": []}, tmp_path, writer,
                crawl_errors=CRAWL_ERRORS, authorities_by_id=AUTHORITIES)
