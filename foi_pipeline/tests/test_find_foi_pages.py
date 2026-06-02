import json
import pytest
from scripts.file_utils import write_json, IncrementalWriter
from steps.find_foi_pages.process import process, retry, STEP_NAME, find_foi_link_on_page

INPUT = {
    "metadata": {"step": "validate_websites", "completed_at": "2026-05-04T00:00:00+00:00"},
    "results": [
        {"public_body_id": 1001, "name": "Dept A", "official_website_url": "https://dept-a.ie/",
         "is_reachable": True, "http_status": 200, "checked_at": "2026-05-04T00:00:00+00:00"},
        {"public_body_id": 1002, "name": "Dept B", "official_website_url": "https://dept-b.ie/",
         "is_reachable": False, "http_status": 404, "checked_at": "2026-05-04T00:00:00+00:00"},
    ],
}

HTML_WITH_FOI_LINK = '<html><body><a href="/freedom-of-information/">Freedom of Information</a></body></html>'
HTML_WITH_FOI_HREF = '<html><body><a href="/foi/">Contact</a></body></html>'
HTML_WITHOUT_FOI = '<html><body><a href="/contact/">Contact us</a></body></html>'


def test_crawl_finds_foi_link_by_text(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/", text=HTML_WITH_FOI_LINK)
    process(INPUT, tmp_path, writer)
    assert writer.results[0]["foi_page_url"] == "https://dept-a.ie/freedom-of-information/"
    assert writer.results[0]["source_method"] == "crawl"


def test_crawl_finds_foi_link_by_href(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/", text=HTML_WITH_FOI_HREF)
    process(INPUT, tmp_path, writer)
    assert writer.results[0]["foi_page_url"] == "https://dept-a.ie/foi/"
    assert writer.results[0]["source_method"] == "crawl"


def test_unreachable_body_excluded(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/", text=HTML_WITH_FOI_LINK)
    process(INPUT, tmp_path, writer)
    assert all(r["public_body_id"] != 1002 for r in writer.results)


def test_serper_fallback_when_crawl_finds_nothing(requests_mock, tmp_path, make_writer, monkeypatch):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/", text=HTML_WITHOUT_FOI)
    monkeypatch.setenv("SERPER_API_KEY", "a" * 32)
    requests_mock.post("https://google.serper.dev/search", json={"organic": [{"link": "https://dept-a.ie/foi/"}]})
    process(INPUT, tmp_path, writer)
    assert len(writer.results) == 1
    assert writer.results[0]["source_method"] == "serper"
    assert writer.results[0]["foi_page_url"] == "https://dept-a.ie/foi/"
    assert "Dept A" in requests_mock.last_request.json()["q"]


def test_body_excluded_when_no_foi_link_and_no_serper_key(requests_mock, tmp_path, make_writer, monkeypatch):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/", text=HTML_WITHOUT_FOI)
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    process(INPUT, tmp_path, writer)
    assert len(writer.results) == 0
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert len(errors) == 1
    assert "SERPER_API_KEY not set" in errors[0]["error_message"]


def test_connection_error_logs_and_skips_body(requests_mock, tmp_path, make_writer):
    import requests as req
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/", exc=req.exceptions.ConnectionError("refused"))
    process(INPUT, tmp_path, writer)
    assert len(writer.results) == 0
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert len(errors) == 1
    assert errors[0]["step"] == STEP_NAME


def test_output_has_required_fields(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/", text=HTML_WITH_FOI_LINK)
    process(INPUT, tmp_path, writer)
    r = writer.results[0]
    assert {"public_body_id", "name", "official_website_url", "foi_page_url", "source_method"} <= r.keys()


def test_find_foi_link_returns_none_when_no_match():
    html = '<html><body><a href="/about/">About</a></body></html>'
    assert find_foi_link_on_page(html, "https://example.ie/") is None


def test_find_foi_link_resolves_relative_urls():
    html = '<html><body><a href="/foi/">FOI</a></body></html>'
    result = find_foi_link_on_page(html, "https://example.ie/")
    assert result == "https://example.ie/foi/"


def test_mailto_link_not_returned_by_crawl(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    html = '<html><body><a href="mailto:foi@dept-a.ie">Email FOI</a></body></html>'
    requests_mock.get("https://dept-a.ie/", text=html)
    process(INPUT, tmp_path, writer)
    assert len(writer.results) == 0


def test_mailto_not_matched_by_find_foi_link_on_page():
    html = '<html><body><a href="mailto:foi@body.ie">FOI Contact</a></body></html>'
    assert find_foi_link_on_page(html, "https://body.ie/") is None


GOV_IE_INPUT = {
    "metadata": {"step": "validate_websites", "completed_at": "2026-05-04T00:00:00+00:00"},
    "results": [
        {"public_body_id": 2001, "name": "Courts Service",
         "official_website_url": "https://www.gov.ie/en/courts-service/",
         "is_reachable": True, "http_status": 200, "checked_at": "2026-05-04T00:00:00+00:00"},
    ],
}


def test_serper_gov_ie_filters_to_path_prefix(requests_mock, tmp_path, make_writer, monkeypatch):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://www.gov.ie/en/courts-service/", text=HTML_WITHOUT_FOI)
    monkeypatch.setenv("SERPER_API_KEY", "a" * 32)
    requests_mock.post("https://google.serper.dev/search", json={"organic": [
        {"link": "https://www.gov.ie/en/social-welfare-appeals/foi/"},
        {"link": "https://www.gov.ie/en/courts-service/foi/"},
    ]})
    process(GOV_IE_INPUT, tmp_path, writer)
    assert len(writer.results) == 1
    assert writer.results[0]["foi_page_url"] == "https://www.gov.ie/en/courts-service/foi/"


def test_serper_non_gov_ie_not_filtered(requests_mock, tmp_path, make_writer, monkeypatch):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/", text=HTML_WITHOUT_FOI)
    monkeypatch.setenv("SERPER_API_KEY", "a" * 32)
    requests_mock.post("https://google.serper.dev/search", json={"organic": [{"link": "https://dept-a.ie/foi/"}]})
    process(INPUT, tmp_path, writer)
    assert len(writer.results) == 1
    assert writer.results[0]["foi_page_url"] == "https://dept-a.ie/foi/"


def test_serper_gov_ie_no_matching_prefix_returns_nothing(requests_mock, tmp_path, make_writer, monkeypatch):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://www.gov.ie/en/courts-service/", text=HTML_WITHOUT_FOI)
    monkeypatch.setenv("SERPER_API_KEY", "a" * 32)
    requests_mock.post("https://google.serper.dev/search", json={"organic": [
        {"link": "https://www.gov.ie/en/social-welfare-appeals/foi/"}
    ]})
    process(GOV_IE_INPUT, tmp_path, writer)
    assert len(writer.results) == 0


BLOCKLIST_INPUT = {
    "metadata": {"step": "validate_websites", "completed_at": "2026-05-04T00:00:00+00:00"},
    "results": [
        {"public_body_id": 3001, "name": "Agency A", "official_website_url": "https://agency-a.ie/",
         "is_reachable": True, "http_status": 200, "checked_at": "2026-05-04T00:00:00+00:00"},
        {"public_body_id": 3002, "name": "Agency B", "official_website_url": "https://agency-b.ie/",
         "is_reachable": True, "http_status": 200, "checked_at": "2026-05-04T00:00:00+00:00"},
    ],
}

BLOCKED_URL_HTML = '<html><body><a href="https://www.gov.ie/en/topics/freedom-of-information">FOI</a></body></html>'
BLOCKED_URL_TRAILING_SLASH_HTML = '<html><body><a href="https://www.gov.ie/en/topics/freedom-of-information/">FOI</a></body></html>'
DUPLICATE_FOI_HTML = '<html><body><a href="https://shared-foi.ie/foi/">FOI</a></body></html>'


def test_no_foi_found_logs_error(requests_mock, tmp_path, make_writer, monkeypatch):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/", text=HTML_WITHOUT_FOI)
    monkeypatch.setenv("SERPER_API_KEY", "a" * 32)
    requests_mock.post("https://google.serper.dev/search", json={"organic": []})
    process(INPUT, tmp_path, writer)
    assert len(writer.results) == 0
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert len(errors) == 1
    assert errors[0]["error_type"] == "FoiPageNotFound"
    assert errors[0]["context"]["public_body_id"] == 1001


def test_blocklisted_url_logs_error(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://agency-a.ie/", text=BLOCKED_URL_HTML)
    requests_mock.get("https://agency-b.ie/", text=HTML_WITH_FOI_LINK)
    process(BLOCKLIST_INPUT, tmp_path, writer)
    errors = json.loads((tmp_path / "errors.json").read_text())
    blocklist_errors = [e for e in errors if e["error_type"] == "BlocklistedFoiPageUrl"]
    assert len(blocklist_errors) == 1
    assert blocklist_errors[0]["context"]["public_body_id"] == 3001


def test_blocklisted_url_excluded_from_results(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://agency-a.ie/", text=BLOCKED_URL_HTML)
    requests_mock.get("https://agency-b.ie/", text=HTML_WITH_FOI_LINK)
    process(BLOCKLIST_INPUT, tmp_path, writer)
    assert all(r["public_body_id"] != 3001 for r in writer.results)
    assert any(r["public_body_id"] == 3002 for r in writer.results)


def test_blocklisted_url_with_trailing_slash_excluded(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://agency-a.ie/", text=BLOCKED_URL_TRAILING_SLASH_HTML)
    requests_mock.get("https://agency-b.ie/", text=HTML_WITH_FOI_LINK)
    process(BLOCKLIST_INPUT, tmp_path, writer)
    assert all(r["public_body_id"] != 3001 for r in writer.results)


def test_duplicate_foi_urls_removed_from_output(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://agency-a.ie/", text=DUPLICATE_FOI_HTML)
    requests_mock.get("https://agency-b.ie/", text=DUPLICATE_FOI_HTML)
    process(BLOCKLIST_INPUT, tmp_path, writer)
    assert len(writer.results) == 0


def test_duplicate_foi_urls_logged_to_errors(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://agency-a.ie/", text=DUPLICATE_FOI_HTML)
    requests_mock.get("https://agency-b.ie/", text=DUPLICATE_FOI_HTML)
    process(BLOCKLIST_INPUT, tmp_path, writer)
    errors = json.loads((tmp_path / "errors.json").read_text())
    duplicate_errors = [e for e in errors if e.get("error_type") == "DuplicateFoiPageUrl"]
    assert len(duplicate_errors) == 2
    assert {e["context"]["public_body_id"] for e in duplicate_errors} == {3001, 3002}


def test_non_duplicate_urls_not_affected_by_uniqueness_pass(requests_mock, tmp_path, make_writer):
    writer = make_writer(STEP_NAME)
    requests_mock.get("https://dept-a.ie/", text=HTML_WITH_FOI_LINK)
    process(INPUT, tmp_path, writer)
    assert len(writer.results) == 1
    assert writer.results[0]["foi_page_url"] == "https://dept-a.ie/freedom-of-information/"


def test_resume_skips_already_processed_body(requests_mock, tmp_path):
    from scripts.file_utils import IncrementalWriter
    partial = {
        "metadata": {"step": STEP_NAME},
        "results": [{"public_body_id": 1001, "name": "Dept A",
                     "official_website_url": "https://dept-a.ie/",
                     "foi_page_url": "https://dept-a.ie/foi/", "source_method": "crawl"}],
    }
    write_json(tmp_path / "output.json", partial)
    writer = IncrementalWriter(tmp_path / "output.json", STEP_NAME, force=False)
    process(INPUT, tmp_path, writer)
    dept_a_calls = [r for r in requests_mock.request_history if "dept-a.ie" in r.url]
    assert len(dept_a_calls) == 0


# --- Retry tests ---

RETRY_INPUT = {
    "metadata": {"step": "validate_websites", "completed_at": "2026-05-04T00:00:00+00:00"},
    "results": [
        {"public_body_id": 1001, "name": "Dept A", "official_website_url": "https://dept-a.ie/",
         "is_reachable": True, "http_status": 200, "checked_at": "2026-05-04T00:00:00+00:00"},
        {"public_body_id": 1002, "name": "Dept B", "official_website_url": "https://dept-b.ie/",
         "is_reachable": True, "http_status": 200, "checked_at": "2026-05-04T00:00:00+00:00"},
    ],
}

EXISTING_RESULT = {
    "public_body_id": 1001, "name": "Dept A",
    "official_website_url": "https://dept-a.ie/",
    "foi_page_url": "https://dept-a.ie/foi/", "source_method": "crawl",
}

SERPER_ERROR = {
    "step": STEP_NAME, "timestamp": "2026-05-06T14:00:00+00:00",
    "error_type": "ValueError",
    "error_message": "SERPER_API_KEY not set and FOI page not found via crawl for Dept B",
    "context": {"url": "https://dept-b.ie/", "public_body_id": 1002, "name": "Dept B"},
}


def test_retry_with_no_errors_file_does_not_modify_output(tmp_path):
    output_path = tmp_path / "output.json"
    write_json(output_path, {"metadata": {}, "results": [EXISTING_RESULT]})
    input_path = tmp_path / "input.json"
    write_json(input_path, RETRY_INPUT)
    retry(str(input_path), output_path, tmp_path)
    result = json.loads(output_path.read_text())
    assert result["results"] == [EXISTING_RESULT]


def test_retry_processes_only_failed_bodies(requests_mock, tmp_path):
    output_path = tmp_path / "output.json"
    write_json(output_path, {"metadata": {}, "results": [EXISTING_RESULT]})
    write_json(tmp_path / "errors.json", [SERPER_ERROR])
    input_path = tmp_path / "input.json"
    write_json(input_path, RETRY_INPUT)
    requests_mock.get("https://dept-b.ie/", text=HTML_WITH_FOI_LINK)
    retry(str(input_path), output_path, tmp_path)
    result = json.loads(output_path.read_text())
    ids = {r["public_body_id"] for r in result["results"]}
    assert 1001 in ids
    assert 1002 in ids


def test_tel_link_with_foi_text_is_rejected():
    html = '<html><body><a href="tel:+35312345678">FOI Contact</a></body></html>'
    assert find_foi_link_on_page(html, "https://example.ie/") is None


def test_javascript_link_with_foi_text_is_rejected():
    html = '<html><body><a href="javascript:void(0)">Freedom of Information</a></body></html>'
    assert find_foi_link_on_page(html, "https://example.ie/") is None


def test_page_with_foi_text_but_no_foi_url_keyword_returns_none():
    """FOI text alone is not enough — the URL must also contain an FOI keyword."""
    html = '<html><body><h1>Freedom of Information</h1><p>Request FOI here</p></body></html>'
    assert find_foi_link_on_page(html, "https://example.ie/") is None


def test_page_with_foi_text_in_body_returns_base_url():
    html = '<html><body><p>This is our freedom of information page</p></body></html>'
    assert find_foi_link_on_page(html, "https://example.ie/foi") == "https://example.ie/foi"


def test_find_foi_link_skips_irish_language_links():
    html = '<html><body><a href="/ga/freedom-of-information/">Saoráil Faisnéise</a></body></html>'
    assert find_foi_link_on_page(html, "https://www.gov.ie/en/some-body/") is None


def test_page_with_foi_text_and_foi_link_returns_the_link():
    """When the URL has no FOI keyword, link discovery runs and finds the specific FOI page."""
    html = '<html><body><h1>Freedom of Information</h1><a href="/foi-page/">FOI Page</a></body></html>'
    assert find_foi_link_on_page(html, "https://example.ie/") == "https://example.ie/foi-page/"


def test_about_page_with_embedded_foi_section_does_not_return_itself():
    """An about/general page that mentions FOI in body text is not the FOI page."""
    html = (
        '<html><body>'
        '<h1>About the Council</h1>'
        '<p>General info.</p>'
        '<h2>Freedom of Information</h2>'
        '<p>We are a prescribed body under the FOI Acts.</p>'
        '</body></html>'
    )
    result = find_foi_link_on_page(html, "https://example.ie/about-the-council/")
    assert result is None


def test_fragment_anchor_with_foi_text_not_returned():
    """A bare fragment like #FOI is an in-page anchor, not an FOI page URL."""
    html = '<html><body><a href="#FOI">Freedom of Information</a></body></html>'
    result = find_foi_link_on_page(html, "https://example.ie/about/")
    assert result is None


def test_dedicated_foi_page_with_foi_url_keyword_returns_itself():
    """A dedicated FOI page (FOI keyword in URL) with FOI body text is correctly recognised."""
    html = '<html><body><h1>Freedom of Information</h1><p>Request FOI here.</p></body></html>'
    result = find_foi_link_on_page(html, "https://example.ie/freedom-of-information/")
    assert result == "https://example.ie/freedom-of-information/"


def test_override_body_not_fetched(requests_mock, tmp_path):
    """Override record in processed_keys — process() must not make any HTTP call for it."""
    override_path = tmp_path / "override.json"
    write_json(override_path, [{
        "public_body_id": 1001,
        "name": "Dept A",
        "official_website_url": "https://dept-a.ie/",
        "foi_page_url": "https://dept-a.ie/foi/",
        "source_method": "manual",
        "overridden": True,
    }])
    # Writer pre-loads override; body 1001 is in processed_keys before process() runs
    writer = IncrementalWriter(tmp_path / "output.json", STEP_NAME, override_path=override_path)

    # No HTTP mock for dept-a.ie — requests_mock raises ConnectionError if called
    process(INPUT, tmp_path, writer)

    result = next(r for r in writer.results if r["public_body_id"] == 1001)
    assert result["foi_page_url"] == "https://dept-a.ie/foi/"
    assert result["source_method"] == "manual"
    assert result["overridden"] is True


def test_override_body_survives_force_writer(tmp_path):
    """force=True clears automated results; override records are still loaded."""
    override_path = tmp_path / "override.json"
    write_json(override_path, [{
        "public_body_id": 1001,
        "name": "Dept A",
        "official_website_url": "https://dept-a.ie/",
        "foi_page_url": "https://dept-a.ie/foi/",
        "source_method": "manual",
        "overridden": True,
    }])
    writer = IncrementalWriter(tmp_path / "output.json", STEP_NAME,
                               force=True, override_path=override_path)
    assert 1001 in writer.processed_keys
    assert writer.results[0]["foi_page_url"] == "https://dept-a.ie/foi/"


def test_uniqueness_pass_keeps_override_drops_automated_duplicate(requests_mock, tmp_path):
    """When override and automated result share foi_page_url, automated is dropped."""
    shared_url = "https://shared-foi.ie/foi/"
    override_path = tmp_path / "override.json"
    write_json(override_path, [{
        "public_body_id": 1001,
        "name": "Dept A",
        "official_website_url": "https://dept-a.ie/",
        "foi_page_url": shared_url,
        "source_method": "manual",
        "overridden": True,
    }])

    extra_input = {
        "metadata": INPUT["metadata"],
        "results": [
            # 1001 is overridden — will be skipped by process()
            INPUT["results"][0],
            # 1003 is new; crawl will find the same foi_page_url
            {
                "public_body_id": 1003,
                "name": "Dept C",
                "official_website_url": "https://dept-c.ie/",
                "is_reachable": True,
                "http_status": 200,
                "checked_at": "2026-05-04T00:00:00+00:00",
            },
        ],
    }
    requests_mock.get(
        "https://dept-c.ie/",
        text=f'<html><body><a href="{shared_url}">FOI</a></body></html>',
    )

    writer = IncrementalWriter(tmp_path / "output.json", STEP_NAME, override_path=override_path)
    process(extra_input, tmp_path, writer)

    body_ids = [r["public_body_id"] for r in writer.results]
    assert 1001 in body_ids   # override survives
    assert 1003 not in body_ids  # automated duplicate dropped


import sys as _sys
from scripts.file_utils import read_json as _read_json, write_json as _write_json
import steps.find_foi_pages.process as _proc


def test_public_body_scoped_leaves_others_untouched(requests_mock, tmp_path, monkeypatch):
    out = tmp_path / "output.json"
    # Seed realistic find_foi_pages records (need foi_page_url for uniqueness pass)
    seeded = [
        {"public_body_id": 1001, "foi_page_url": "https://a.ie/foi/", "marker": "keep-1001"},
        {"public_body_id": 1002, "foi_page_url": "https://b.ie/foi/", "marker": "old-1002"},
        {"public_body_id": 1003, "foi_page_url": "https://c.ie/foi/", "marker": "keep-1003"},
    ]
    _write_json(out, {"metadata": {"step": "find_foi_pages"}, "results": seeded})

    inp = tmp_path / "input.json"
    _write_json(inp, {"results": [
        {"public_body_id": 1001, "official_website_url": "https://a.ie/", "is_reachable": True},
        {"public_body_id": 1002, "official_website_url": "https://b.ie/", "is_reachable": True},
        {"public_body_id": 1003, "official_website_url": "https://c.ie/", "is_reachable": True},
    ]})
    requests_mock.get("https://b.ie/", text=HTML_WITH_FOI_LINK)

    monkeypatch.setattr(_proc, "__file__", str(tmp_path / "process.py"))
    _sys.argv = ["process.py", "--input", str(inp), "--output", str(out),
                 "--public-body", "1002"]
    _proc.main()

    results = {r["public_body_id"]: r for r in _read_json(out)["results"]}
    assert results[1001]["marker"] == "keep-1001"
    assert results[1003]["marker"] == "keep-1003"
    assert "marker" not in results[1002] or results[1002]["marker"] != "old-1002"
    assert _read_json(tmp_path / "dirty_ids.json") == [1002]
