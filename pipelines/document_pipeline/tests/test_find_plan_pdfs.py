import json

import pytest

from lib.file_utils import IncrementalWriter, write_json
from steps.find_plan_pdfs.process import (
    STEP_NAME, _build_query, _pick_pdf_url, _slugify,
)
# process imported in Part B

PLAN_A = {"department": "Department of Transport", "title": "Statement of Strategy",
          "time_horizon": "2025-2028", "focus": "x", "status": "Active"}


def test_slugify_lowercases_and_hyphenates():
    assert _slugify("Department of Transport") == "department-of-transport"
    assert _slugify("Statement of Strategy") == "statement-of-strategy"


def test_slugify_falls_back_to_ascii_on_unicode_punctuation():
    assert _slugify("Food Vision 2030 – Ireland") == "food-vision-2030-ireland"


def test_build_query_matches_the_gov_ie_pdf_pattern():
    assert _build_query("Statement of Strategy") == \
        'site:gov.ie "Statement of Strategy" filetype:pdf'


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
