import json
import pytest
from pathlib import Path
from lib.file_utils import write_json, IncrementalWriter
from steps.find_foi_pages_search.process import process, STEP_NAME

STEP = "find_foi_pages_search"

CRAWL_OUTPUT = {
    "metadata": {"step": "find_foi_pages", "completed_at": "2026-06-01T00:00:00+00:00"},
    "results": [
        {
            "public_body_id": 1001,
            "name": "Dept A",
            "official_website_url": "https://dept-a.ie/",
            "foi_page_url": "https://dept-a.ie/foi/",
            "source_method": "crawl",
        }
    ],
}

CRAWL_ERRORS = [
    {
        "step": "find_foi_pages",
        "error_type": "FoiPageNotFound",
        "error_message": "No FOI page found via crawl for Dept B",
        "context": {"url": "https://dept-b.ie/", "public_body_id": 1002, "name": "Dept B"},
    }
]


def test_crawl_success_is_passed_through(tmp_path, make_writer, monkeypatch):
    monkeypatch.setattr(
        "steps.find_foi_pages_search.process.batch_search",
        lambda queries, api_token=None: {},
    )
    writer = make_writer(STEP)
    process(CRAWL_OUTPUT, tmp_path, writer, crawl_errors=[])
    assert len(writer.results) == 1
    assert writer.results[0]["public_body_id"] == 1001
    assert writer.results[0]["source_method"] == "crawl"
    assert writer.results[0]["foi_page_url"] == "https://dept-a.ie/foi/"


def test_search_finds_foi_url_for_failed_crawl_body(tmp_path, make_writer, monkeypatch):
    monkeypatch.setattr(
        "steps.find_foi_pages_search.process.batch_search",
        lambda queries, api_token=None: {
            "site:dept-b.ie Dept B freedom of information": [
                {"url": "https://dept-b.ie/foi/", "link": "https://dept-b.ie/foi/"}
            ]
        },
    )
    writer = make_writer(STEP)
    process(CRAWL_OUTPUT, tmp_path, writer, crawl_errors=CRAWL_ERRORS)
    ids = {r["public_body_id"] for r in writer.results}
    assert 1002 in ids
    b = next(r for r in writer.results if r["public_body_id"] == 1002)
    assert b["foi_page_url"] == "https://dept-b.ie/foi/"
    assert b["source_method"] == "apify"


def test_body_not_found_goes_to_errors_json(tmp_path, make_writer, monkeypatch):
    monkeypatch.setattr(
        "steps.find_foi_pages_search.process.batch_search",
        lambda queries, api_token=None: {
            "site:dept-b.ie Dept B freedom of information": []
        },
    )
    writer = make_writer(STEP)
    process(CRAWL_OUTPUT, tmp_path, writer, crawl_errors=CRAWL_ERRORS)
    assert all(r["public_body_id"] != 1002 for r in writer.results)
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert any(e["context"]["public_body_id"] == 1002 for e in errors)


def test_result_url_must_contain_foi_keyword(tmp_path, make_writer, monkeypatch):
    monkeypatch.setattr(
        "steps.find_foi_pages_search.process.batch_search",
        lambda queries, api_token=None: {
            "site:dept-b.ie Dept B freedom of information": [
                {"url": "https://dept-b.ie/about/", "link": "https://dept-b.ie/about/"},
                {"url": "https://dept-b.ie/foi/", "link": "https://dept-b.ie/foi/"},
            ]
        },
    )
    writer = make_writer(STEP)
    process(CRAWL_OUTPUT, tmp_path, writer, crawl_errors=CRAWL_ERRORS)
    b = next(r for r in writer.results if r["public_body_id"] == 1002)
    assert b["foi_page_url"] == "https://dept-b.ie/foi/"


def test_gov_ie_results_filtered_to_path_prefix(tmp_path, make_writer, monkeypatch):
    gov_ie_errors = [
        {
            "step": "find_foi_pages",
            "error_type": "FoiPageNotFound",
            "error_message": "No FOI page found",
            "context": {
                "url": "https://www.gov.ie/en/courts-service/",
                "public_body_id": 2001,
                "name": "Courts Service",
            },
        }
    ]
    gov_ie_input = {
        "metadata": CRAWL_OUTPUT["metadata"],
        "results": [],
    }
    monkeypatch.setattr(
        "steps.find_foi_pages_search.process.batch_search",
        lambda queries, api_token=None: {
            "site:www.gov.ie Courts Service freedom of information": [
                {"url": "https://www.gov.ie/en/social-welfare/foi/", "link": "https://www.gov.ie/en/social-welfare/foi/"},
                {"url": "https://www.gov.ie/en/courts-service/foi/", "link": "https://www.gov.ie/en/courts-service/foi/"},
            ]
        },
    )
    writer = make_writer(STEP)
    process(gov_ie_input, tmp_path, writer, crawl_errors=gov_ie_errors)
    assert len(writer.results) == 1
    assert writer.results[0]["foi_page_url"] == "https://www.gov.ie/en/courts-service/foi/"


def test_unsafe_url_in_results_is_skipped(tmp_path, make_writer, monkeypatch):
    monkeypatch.setattr(
        "steps.find_foi_pages_search.process.batch_search",
        lambda queries, api_token=None: {
            "site:dept-b.ie Dept B freedom of information": [
                {"url": "javascript:void(0)", "link": "javascript:void(0)"},
                {"url": "https://dept-b.ie/foi/", "link": "https://dept-b.ie/foi/"},
            ]
        },
    )
    writer = make_writer(STEP)
    process(CRAWL_OUTPUT, tmp_path, writer, crawl_errors=CRAWL_ERRORS)
    b = next(r for r in writer.results if r["public_body_id"] == 1002)
    assert b["foi_page_url"] == "https://dept-b.ie/foi/"


def test_override_record_is_preserved(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "steps.find_foi_pages_search.process.batch_search",
        lambda queries, api_token=None: {},
    )
    override_path = tmp_path / "override.json"
    write_json(override_path, [{
        "public_body_id": 1001,
        "name": "Dept A",
        "official_website_url": "https://dept-a.ie/",
        "foi_page_url": "https://dept-a.ie/override-foi/",
        "source_method": "manual",
        "overridden": True,
    }])
    writer = IncrementalWriter(tmp_path / "output.json", STEP, override_path=override_path)
    process(CRAWL_OUTPUT, tmp_path, writer, crawl_errors=[])
    r = next(r for r in writer.results if r["public_body_id"] == 1001)
    assert r["foi_page_url"] == "https://dept-a.ie/override-foi/"
    assert r["source_method"] == "manual"


def test_missing_apify_token_raises(tmp_path, make_writer, monkeypatch):
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    writer = make_writer(STEP)
    with pytest.raises(RuntimeError, match="APIFY_TOKEN"):
        process(CRAWL_OUTPUT, tmp_path, writer, crawl_errors=CRAWL_ERRORS)
