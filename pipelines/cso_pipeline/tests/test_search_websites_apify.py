import pytest

from steps.search_websites_apify.process import (
    build_query,
    score_confidence,
    process,
    STEP_NAME,
)
from lib.file_utils import IncrementalWriter, read_json


def _make_body(id, name, gov_dept=None, llm_confidence="low", llm_url=None):
    return {
        "public_body_id": id,
        "name": name,
        "government_department": gov_dept,
        "llm_website_url": llm_url,
        "llm_url_type": None,
        "llm_confidence": llm_confidence,
        "llm_notes": None,
        "official_website_url": None,
    }


def _input_data(*bodies):
    return {"public_bodies": list(bodies)}


# ── build_query ──────────────────────────────────────────────────────────────

def test_build_query_with_government_department():
    body = _make_body(1, "Abbey Theatre", gov_dept="Department of Tourism")
    query = build_query(body)
    assert '"Abbey Theatre"' in query
    assert "Ireland official website" in query


def test_build_query_without_government_department():
    body = _make_body(1, "Abbey Theatre")
    query = build_query(body)
    assert '"Abbey Theatre"' in query
    assert "Ireland official website" in query


# ── score_confidence ─────────────────────────────────────────────────────────

def test_score_high_when_domain_contains_meaningful_name_token():
    # "abbey" is 5 chars, not a stop word
    assert score_confidence("abbeytheatre.ie", "Abbey Theatre") == "high"


def test_score_low_when_no_name_token_in_domain():
    assert score_confidence("example.com", "Abbey Theatre") == "low"


def test_score_ignores_stop_words():
    # "ireland", "board" are stop words — no meaningful token remains
    assert score_confidence("ireland.ie", "Ireland Board") == "low"


def test_score_ignores_short_tokens():
    # "an" (2 chars), "post" (4 chars) — neither > 4 chars
    assert score_confidence("anpost.ie", "An Post") == "low"


def test_score_high_for_longer_token():
    # "council" is 7 chars, not a stop word
    assert score_confidence("artscouncil.ie", "Arts Council Ireland") == "high"


# ── process() ─────────────────────────────────────────────────────────────────

def test_passthrough_high_llm_confidence_without_calling_batch_search(tmp_path, monkeypatch):
    called = [False]

    def _mock_batch_search(queries, api_token=None):
        called[0] = True
        return {}

    monkeypatch.setattr("steps.search_websites_apify.process.batch_search", _mock_batch_search)
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, STEP_NAME, force=True)

    body = _make_body(1, "Abbey Theatre", llm_confidence="high", llm_url="https://abbeytheatre.ie")
    process(_input_data(body), tmp_path, writer)
    writer.finalize()

    assert not called[0]
    record = read_json(output_path)["results"][0]
    assert record["apify_website_url"] is None
    assert record["apify_confidence"] is None


def test_logs_website_not_found_when_apify_returns_no_results(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "steps.search_websites_apify.process.batch_search",
        lambda queries, api_token=None: {q: [] for q in queries},
    )
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, STEP_NAME, force=True)

    process(_input_data(_make_body(1, "Unknown Entity XYZ")), tmp_path, writer)
    writer.finalize()

    errors = read_json(tmp_path / "errors.json")
    assert len(errors) == 1
    assert errors[0]["error_type"] == "WebsiteNotFound"

    record = read_json(output_path)["results"][0]
    assert record["apify_website_url"] is None
    assert record["apify_confidence"] == "not_found"


def test_scores_high_confidence_when_domain_matches_name(tmp_path, monkeypatch):
    def _mock_batch_search(queries, api_token=None):
        return {queries[0]: [{"link": "https://abbeytheatre.ie", "url": "https://abbeytheatre.ie"}]}

    monkeypatch.setattr("steps.search_websites_apify.process.batch_search", _mock_batch_search)
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, STEP_NAME, force=True)

    process(_input_data(_make_body(1, "Abbey Theatre")), tmp_path, writer)
    writer.finalize()

    record = read_json(output_path)["results"][0]
    assert record["apify_website_url"] == "https://abbeytheatre.ie/"
    assert record["apify_confidence"] == "high"


def test_scores_low_confidence_when_domain_does_not_match(tmp_path, monkeypatch):
    def _mock_batch_search(queries, api_token=None):
        return {queries[0]: [{"link": "https://example.com", "url": "https://example.com"}]}

    monkeypatch.setattr("steps.search_websites_apify.process.batch_search", _mock_batch_search)
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, STEP_NAME, force=True)

    process(_input_data(_make_body(1, "Abbey Theatre")), tmp_path, writer)
    writer.finalize()

    record = read_json(output_path)["results"][0]
    assert record["apify_confidence"] == "low_discarded"
