# foi_pipeline/tests/test_find_disclosure_pages_domains.py
import pytest
from steps.find_disclosure_pages.domains import find_disclosure_page


VALID_GOV_IE_LINK = "https://www.gov.ie/en/dept/collections/foi-disclosure-log/"


def _serper_result(link):
    return [{"link": link}]


def test_returns_first_valid_gov_ie_result(monkeypatch):
    monkeypatch.setattr(
        "steps.find_disclosure_pages.domains.search_serper",
        lambda q: _serper_result(VALID_GOV_IE_LINK),
    )
    result = find_disclosure_page(
        "Department of Agriculture",
        "https://www.gov.ie/en/department-of-agriculture-food-and-the-marine/",
    )
    assert result == VALID_GOV_IE_LINK


def test_skips_invalid_first_result_returns_second(monkeypatch):
    results = [
        {"link": "javascript:void(0)"},
        {"link": VALID_GOV_IE_LINK},
    ]
    monkeypatch.setattr(
        "steps.find_disclosure_pages.domains.search_serper",
        lambda q: results,
    )
    result = find_disclosure_page(
        "Department of Agriculture",
        "https://www.gov.ie/en/department-of-agriculture-food-and-the-marine/",
    )
    assert result == VALID_GOV_IE_LINK


def test_returns_none_when_all_results_invalid(monkeypatch):
    monkeypatch.setattr(
        "steps.find_disclosure_pages.domains.search_serper",
        lambda q: [{"link": "javascript:void(0)"}, {"link": "ftp://bad.ie/"}],
    )
    result = find_disclosure_page(
        "Department of Agriculture",
        "https://www.gov.ie/en/department-of-agriculture-food-and-the-marine/",
    )
    assert result is None


def test_returns_none_on_empty_serper_response(monkeypatch):
    monkeypatch.setattr(
        "steps.find_disclosure_pages.domains.search_serper",
        lambda q: [],
    )
    result = find_disclosure_page(
        "Department of Agriculture",
        "https://www.gov.ie/en/department-of-agriculture-food-and-the-marine/",
    )
    assert result is None


def test_returns_none_for_non_gov_ie_domain(monkeypatch):
    called = []
    monkeypatch.setattr(
        "steps.find_disclosure_pages.domains.search_serper",
        lambda q: called.append(q) or [],
    )
    result = find_disclosure_page("Dept B", "https://dept-b.ie/foi/")
    assert result is None
    assert called == [], "search_serper must not be called for non-gov.ie domains"


def test_query_contains_name_and_disclosure_log_terms(monkeypatch):
    queries = []
    monkeypatch.setattr(
        "steps.find_disclosure_pages.domains.search_serper",
        lambda q: queries.append(q) or [],
    )
    find_disclosure_page(
        "Department of Agriculture",
        "https://www.gov.ie/en/department-of-agriculture-food-and-the-marine/",
    )
    assert len(queries) == 1
    assert '"Department of Agriculture"' in queries[0]
    assert "foi disclosure log" in queries[0]
    assert "site:gov.ie" in queries[0]
