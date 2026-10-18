import json
from unittest.mock import patch

import pytest

from steps.resolve_website_urls.process import process
from lib.file_utils import IncrementalWriter


def _make_body(id, name, url=None):
    return {"public_body_id": id, "name": name, "official_website_url": url, "sector": "S13"}


def test_null_url_passes_through_without_fetch(tmp_path):
    """Bodies with null official_website_url must be written through; no HTTP call, no error."""
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, "resolve_website_urls", force=True)

    with patch("steps.resolve_website_urls.process.fetch") as mock_fetch:
        process({"public_bodies": [_make_body(1, "Some Body CLG")]}, tmp_path, writer)

    mock_fetch.assert_not_called()

    errors = json.loads((tmp_path / "errors.json").read_text())
    assert errors == []

    writer.finalize()
    output = json.loads(output_path.read_text())
    results = output.get("results", output.get("public_bodies", []))
    assert len(results) == 1
    assert results[0]["official_website_url"] is None


def test_no_failed_ids_file_created(tmp_path):
    """process() must not create failed_ids.json; failures are tracked via errors.json."""
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, "resolve_website_urls", force=True)

    with patch("steps.resolve_website_urls.process.fetch"):
        process({"public_bodies": [_make_body(42, "Ghost Body")]}, tmp_path, writer)

    assert not (tmp_path / "failed_ids.json").exists()


def test_fetch_failure_id_appears_in_errors(tmp_path):
    """When a fetch fails, the body's ID must appear in errors.json context."""
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, "resolve_website_urls", force=True)

    with patch("steps.resolve_website_urls.process.fetch", side_effect=Exception("timeout")):
        process({"public_bodies": [_make_body(99, "Failing Body", url="http://example.com")]}, tmp_path, writer)

    errors = json.loads((tmp_path / "errors.json").read_text())
    assert len(errors) == 1
    assert errors[0]["context"]["public_body_id"] == 99


def test_results_key_accepted_as_input(tmp_path):
    """process() must work when input uses 'results' key (IncrementalWriter output format)."""
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, "resolve_website_urls", force=True)

    with patch("steps.resolve_website_urls.process.fetch"):
        process({"results": [_make_body(7, "Body A")]}, tmp_path, writer)

    writer.finalize()
    output = json.loads(output_path.read_text())
    results = output.get("results", [])
    assert len(results) == 1


# ---------------------------------------------------------------------------
# a failed candidate must never destroy or shadow a lower-priority one
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, url, text=""):
        self.url = url
        self.text = text

    def raise_for_status(self):
        pass


def _fetch_failing_on(*bad_urls):
    """fetch() stub that raises for bad_urls and 200s everything else."""
    def _fetch(method, url, **kwargs):
        if url in bad_urls:
            raise Exception(f"boom: {url}")
        return _FakeResponse(url)
    return _fetch


def _body_with_candidates(**extra):
    body = {"public_body_id": 1, "name": "Some Body", "sector": "S13"}
    body.update(extra)
    return body


def _run(tmp_path, body, fetch_impl):
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, "resolve_website_urls", force=True)
    with patch("steps.resolve_website_urls.process.fetch", side_effect=fetch_impl):
        process({"public_bodies": [body]}, tmp_path, writer)
    writer.finalize()
    return json.loads(output_path.read_text())["results"][0], \
        json.loads((tmp_path / "errors.json").read_text())


def test_failed_candidate_falls_back_to_next_candidate(tmp_path):
    """When the higher-priority candidate fails to fetch, the step must fall
    back to the next candidate instead of giving up and losing the value."""
    body = _body_with_candidates(
        official_website_url="https://www.gov.ie/en/some-body/",
        llm_website_url="https://www.some-body.ie",
        llm_url_type="direct",
        llm_confidence="high",
    )
    result, errors = _run(tmp_path, body, _fetch_failing_on("https://www.some-body.ie"))

    assert result["official_website_url"] == "https://www.gov.ie/en/some-body/"


def test_recovered_candidate_is_not_logged_as_an_error(tmp_path):
    """A body that resolved via fallback is not a failed body. Logging it as an
    error would make the next run evict and re-fetch it forever (errors.json is
    the step's retry list)."""
    body = _body_with_candidates(
        official_website_url="https://www.gov.ie/en/some-body/",
        llm_website_url="https://www.some-body.ie",
        llm_url_type="direct",
        llm_confidence="high",
    )
    result, errors = _run(tmp_path, body, _fetch_failing_on("https://www.some-body.ie"))

    assert errors == []
    assert result["official_website_url"] == "https://www.gov.ie/en/some-body/"


def test_failed_candidate_does_not_null_existing_official_url(tmp_path):
    """A failed fetch proves nothing about the URL's validity, so the value the
    source already carried must survive rather than being nulled."""
    body = _body_with_candidates(official_website_url="https://www.gov.ie/en/some-body/")
    result, _ = _run(tmp_path, body, _fetch_failing_on("https://www.gov.ie/en/some-body/"))

    assert result["official_website_url"] == "https://www.gov.ie/en/some-body/"


def test_all_candidates_failing_preserves_source_value(tmp_path):
    """With no candidate left to try, the record must pass through untouched."""
    body = _body_with_candidates(official_website_url="https://www.gov.ie/en/some-body/")
    result, errors = _run(
        tmp_path, body, _fetch_failing_on("https://www.gov.ie/en/some-body/"))

    assert result["official_website_url"] == "https://www.gov.ie/en/some-body/"
    assert len(errors) == 1
    assert errors[0]["context"]["public_body_id"] == 1
    assert errors[0]["context"]["attempts"][0]["url"] == "https://www.gov.ie/en/some-body/"


def test_candidate_order_is_apify_then_llm_then_official(tmp_path):
    """The highest-priority candidate that fetches wins; the rest are not tried."""
    body = _body_with_candidates(
        official_website_url="https://www.gov.ie/en/some-body/",
        llm_website_url="https://www.some-body.ie",
        llm_url_type="direct",
        llm_confidence="high",
        apify_website_url="https://some-body.ie/",
    )
    tried = []

    def _fetch(method, url, **kwargs):
        tried.append(url)
        return _FakeResponse(url)

    result, _ = _run(tmp_path, body, _fetch)

    assert result["official_website_url"] == "https://some-body.ie/"
    assert tried == ["https://some-body.ie/"]


def test_bot_challenge_does_not_drop_a_lower_priority_candidate(tmp_path):
    """A WAF/bot-blocked site is alive, not invalid: the failure must not erase
    the value the source already had."""
    from lib.http_utils import BotChallengeError

    def _fetch(method, url, **kwargs):
        raise BotChallengeError("Cloudflare WAF block (HTTP 403) at " + url)

    body = _body_with_candidates(official_website_url="https://www.hsa.ie/")
    result, errors = _run(tmp_path, body, _fetch)

    assert result["official_website_url"] == "https://www.hsa.ie/"
    assert len(errors) == 1
