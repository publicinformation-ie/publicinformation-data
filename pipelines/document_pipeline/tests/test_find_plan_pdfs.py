import json

import pytest

from lib.file_utils import IncrementalWriter, write_json
from steps.find_plan_pdfs.process import (
    STEP_NAME, _build_query, _pick_pdf_url, _slugify, process,
)

PLAN_A = {"department": "Department of Transport", "title": "Statement of Strategy",
          "time_horizon": "2025-2028", "focus": "x", "status": "Active"}


def test_slugify_lowercases_and_hyphenates():
    assert _slugify("Department of Transport") == "department-of-transport"
    assert _slugify("Statement of Strategy") == "statement-of-strategy"


def test_slugify_falls_back_to_ascii_on_unicode_punctuation():
    assert _slugify("Food Vision 2030 – Ireland") == "food-vision-2030-ireland"


def test_build_query_matches_the_gov_ie_pdf_pattern():
    assert _build_query("Department of Transport", "Statement of Strategy") == \
        'site:gov.ie "Department of Transport" "Statement of Strategy" filetype:pdf'


def test_pick_pdf_url_returns_the_first_gov_ie_pdf_result():
    results = [
        {"link": "https://example.com/not-gov.pdf"},
        {"link": "https://www.gov.ie/en/publications/not-a-pdf/"},
        {"link": "https://www.gov.ie/en/publications/strategy.pdf"},
        {"link": "https://www.gov.ie/en/publications/other.pdf"},
    ]
    assert _pick_pdf_url(results) == "https://www.gov.ie/en/publications/strategy.pdf"


def test_pick_pdf_url_accepts_any_gov_ie_subdomain():
    results = [{"link": "https://assets.gov.ie/documents/strategy.pdf"}]
    assert _pick_pdf_url(results) == "https://assets.gov.ie/documents/strategy.pdf"


def test_pick_pdf_url_is_case_insensitive_on_the_pdf_extension():
    results = [{"link": "https://www.gov.ie/en/publications/strategy.PDF"}]
    assert _pick_pdf_url(results) == "https://www.gov.ie/en/publications/strategy.PDF"


def test_pick_pdf_url_skips_an_unsafe_url():
    results = [{"link": "javascript:alert(1)"},
               {"link": "https://www.gov.ie/en/publications/strategy.pdf"}]
    assert _pick_pdf_url(results) == "https://www.gov.ie/en/publications/strategy.pdf"


def test_pick_pdf_url_returns_none_when_no_result_is_a_gov_ie_pdf():
    assert _pick_pdf_url([{"link": "https://example.com/strategy.pdf"}]) is None


def test_process_writes_a_record_from_the_first_matching_search_result(tmp_path, monkeypatch):
    def fake_batch_search(queries, api_token=None):
        return {_build_query("Department of Transport", "Statement of Strategy"):
                [{"link": "https://www.gov.ie/en/publications/dot-strategy.pdf"}]}
    monkeypatch.setattr("steps.find_plan_pdfs.process.batch_search", fake_batch_search)
    writer = IncrementalWriter(tmp_path / "output.json", STEP_NAME, key_field="doc_slug")

    process([PLAN_A], set(), tmp_path, writer)

    (record,) = writer.results
    assert record["doc_slug"] == "department-of-transport-statement-of-strategy"
    assert record["title"] == "Statement of Strategy"
    assert record["department"] == "Department of Transport"
    assert record["url"] == "https://www.gov.ie/en/publications/dot-strategy.pdf"
    assert record["publisher"] is None
    assert record["public_body_id"] is None
    assert record["published_date"] is None
    assert record["source_method"] == "apify"


def test_process_logs_plan_pdf_not_found_when_no_result_matches(tmp_path, monkeypatch):
    monkeypatch.setattr("steps.find_plan_pdfs.process.batch_search",
                        lambda queries, api_token=None: {})
    writer = IncrementalWriter(tmp_path / "output.json", STEP_NAME, key_field="doc_slug")

    process([PLAN_A], set(), tmp_path, writer)

    assert writer.results == []
    (error,) = json.loads((tmp_path / "errors.json").read_text())
    assert error["error_type"] == "PlanPdfNotFound"
    assert error["context"]["doc_slug"] == "department-of-transport-statement-of-strategy"


def test_process_skips_a_plan_whose_doc_slug_is_already_in_documents_yml(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr("steps.find_plan_pdfs.process.batch_search",
                        lambda queries, api_token=None: called.append(queries) or {})
    writer = IncrementalWriter(tmp_path / "output.json", STEP_NAME, key_field="doc_slug")

    process([PLAN_A], {"department-of-transport-statement-of-strategy"}, tmp_path, writer)

    assert writer.results == []
    assert called == []  # no search attempted for an already-curated doc_slug


def test_process_logs_duplicate_doc_slug_and_keeps_the_first_plan(tmp_path, monkeypatch):
    def fake_batch_search(queries, api_token=None):
        return {_build_query("Department of Transport", "Statement of Strategy"):
                [{"link": "https://www.gov.ie/en/publications/dept-a-strategy.pdf"}]}
    monkeypatch.setattr("steps.find_plan_pdfs.process.batch_search", fake_batch_search)
    writer = IncrementalWriter(tmp_path / "output.json", STEP_NAME, key_field="doc_slug")

    colliding = {"department": "Department of Transport", "title": "Statement of Strategy",
                 "time_horizon": "x", "focus": "x", "status": "Active"}
    process([PLAN_A, colliding], set(), tmp_path, writer)

    assert len(writer.results) == 1
    (error,) = json.loads((tmp_path / "errors.json").read_text())
    assert error["error_type"] == "DuplicateDocSlug"


def test_override_record_is_preserved(tmp_path, monkeypatch):
    monkeypatch.setattr("steps.find_plan_pdfs.process.batch_search",
                        lambda queries, api_token=None: {})
    override_path = tmp_path / "override.json"
    write_json(override_path, [{
        "doc_slug": "department-of-transport-statement-of-strategy",
        "title": "Statement of Strategy",
        "department": "Department of Transport",
        "url": "https://www.gov.ie/en/publications/manual-strategy.pdf",
        "publisher": None,
        "public_body_id": 1213,
        "published_date": None,
        "source_method": "manual",
    }])
    writer = IncrementalWriter(tmp_path / "output.json", STEP_NAME, key_field="doc_slug",
                               override_path=override_path)

    process([PLAN_A], set(), tmp_path, writer)

    (record,) = writer.results
    assert record["url"] == "https://www.gov.ie/en/publications/manual-strategy.pdf"
    assert record["source_method"] == "manual"


def test_missing_apify_token_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    writer = IncrementalWriter(tmp_path / "output.json", STEP_NAME, key_field="doc_slug")
    with pytest.raises(RuntimeError, match="APIFY_TOKEN"):
        process([PLAN_A], set(), tmp_path, writer)
