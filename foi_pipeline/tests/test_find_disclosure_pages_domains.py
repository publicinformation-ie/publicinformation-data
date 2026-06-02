from steps.find_disclosure_pages.domains import find_disclosure_page, _gov_ie_query

VALID_GOV_IE_LINK = "https://www.gov.ie/en/dept/collections/foi-disclosure-log/"
GOV_IE_FOI_URL = "https://www.gov.ie/en/department-of-agriculture-food-and-the-marine/"
NAME = "Department of Agriculture"
QUERY = _gov_ie_query(NAME)


def test_returns_first_valid_gov_ie_result():
    batch = {QUERY: [{"link": VALID_GOV_IE_LINK}]}
    result = find_disclosure_page(NAME, GOV_IE_FOI_URL, batch_results=batch)
    assert result == VALID_GOV_IE_LINK


def test_skips_invalid_first_result_returns_second():
    batch = {QUERY: [{"link": "javascript:void(0)"}, {"link": VALID_GOV_IE_LINK}]}
    result = find_disclosure_page(NAME, GOV_IE_FOI_URL, batch_results=batch)
    assert result == VALID_GOV_IE_LINK


def test_returns_none_when_all_results_invalid():
    batch = {QUERY: [{"link": "javascript:void(0)"}, {"link": "ftp://bad.ie/"}]}
    result = find_disclosure_page(NAME, GOV_IE_FOI_URL, batch_results=batch)
    assert result is None


def test_returns_none_on_empty_results():
    batch = {QUERY: []}
    result = find_disclosure_page(NAME, GOV_IE_FOI_URL, batch_results=batch)
    assert result is None


def test_returns_none_for_non_gov_ie_domain():
    result = find_disclosure_page("Dept B", "https://dept-b.ie/foi/", batch_results={})
    assert result is None


def test_query_contains_name_and_disclosure_log_terms():
    q = _gov_ie_query("Department of Agriculture")
    assert '"Department of Agriculture"' in q
    assert "foi disclosure log" in q
    assert "site:gov.ie" in q


def test_returns_none_when_batch_results_missing_query():
    result = find_disclosure_page(NAME, GOV_IE_FOI_URL, batch_results={})
    assert result is None
