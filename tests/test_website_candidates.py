from lib.website_candidates import candidates_from_apify_item


def test_apify_item_splits_candidates_and_directory_hits():
    item = {"organicResults": [
        {"url": "https://www.solocheck.ie/Irish-Company/Orliven-Limited", "title": "Orliven Limited",
         "description": "Status: Dissolved", "position": 1},
        {"url": "https://ie.linkedin.com/company/orliven", "title": "Orliven | LinkedIn",
         "description": "", "position": 2},
        {"url": "https://www.orliven.ie/about", "title": "About", "description": "wind", "position": 3},
        {"url": "https://orliven.ie/contact", "title": "Contact", "description": "", "position": 4},
    ]}
    cands, hits = candidates_from_apify_item(item)
    assert [c["url"] for c in cands] == ["https://www.orliven.ie/about"]
    assert cands[0]["origin"] == "apify_search" and cands[0]["rank"] == 3
    assert {h["domain"] for h in hits} == {"solocheck.ie", "linkedin.com"}
    assert next(h for h in hits if h["domain"] == "solocheck.ie")["snippet"] == "Status: Dissolved"
    assert next(h for h in hits if h["domain"] == "linkedin.com")["kind"] == "social"


def test_apify_none_item():
    assert candidates_from_apify_item(None) == ([], [])


def test_distinct_gov_ie_organisation_pages_both_kept():
    # regression: registrable_domain alone collapses every gov.ie org page to "gov.ie",
    # so a press release ranked first would silently hide the body's own gov.ie page.
    item = {"organicResults": [
        {"url": "https://www.gov.ie/en/press-release/x/", "title": "Press release",
         "description": "", "position": 1},
        {"url": "https://www.gov.ie/en/organisation/dept-a/", "title": "Dept A",
         "description": "", "position": 2},
    ]}
    cands, _ = candidates_from_apify_item(item)
    assert [c["url"] for c in cands] == ["https://www.gov.ie/en/press-release/x/",
                                         "https://www.gov.ie/en/organisation/dept-a/"]
