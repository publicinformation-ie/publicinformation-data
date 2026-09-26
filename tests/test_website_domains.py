from lib.website_domains import (
    registrable_domain, root_url, listing_kind, has_dissolution_marker, site_key,
)


def test_registrable_domain_strips_www_and_path():
    assert registrable_domain("https://www.hsa.ie/eng/About_Us/") == "hsa.ie"


def test_registrable_domain_keeps_gov_ie_as_site():
    assert registrable_domain("https://www.gov.ie/en/organisation/x/") == "gov.ie"


def test_registrable_domain_handles_co_uk():
    assert registrable_domain("https://shop.example.co.uk/a") == "example.co.uk"


def test_registrable_domain_bad_input():
    assert registrable_domain("not a url") == ""
    assert registrable_domain("") == ""


def test_root_url():
    assert root_url("https://www.meathartscentre.ie/whats-on?x=1") == "https://www.meathartscentre.ie/"


def test_listing_kind_directory_and_social():
    assert listing_kind("https://www.solocheck.ie/Irish-Company/Orliven-Limited-123") == "directory"
    assert listing_kind("https://www.vision-net.ie/Company-Info/X") == "directory"
    assert listing_kind("https://ie.linkedin.com/company/x") == "social"
    assert listing_kind("https://en.wikipedia.org/wiki/ESB") == "social"
    assert listing_kind("https://www.esb.ie/") is None


def test_site_key_distinguishes_gov_ie_organisations():
    # gov.ie hosts hundreds of unrelated bodies; registrable_domain alone collapses
    # every org page to "gov.ie", which corrupts dedup/matching across the pipeline.
    a = site_key("https://www.gov.ie/en/organisation/department-a/")
    b = site_key("https://www.gov.ie/en/organisation/department-b/")
    assert a != b
    assert site_key("https://www.gov.ie/en/organisation/department-a/about") == a


def test_site_key_is_plain_domain_for_non_gov_ie():
    assert site_key("https://www.hsa.ie/eng/About_Us/") == "hsa.ie"


def test_dissolution_markers():
    assert has_dissolution_marker("Status: Dissolved on 12 May 2019")
    assert has_dissolution_marker("company was STRUCK OFF the register")
    assert has_dissolution_marker("Strike-off listed")
    assert has_dissolution_marker("in liquidation since 2020")
    assert not has_dissolution_marker("Status: Normal. Incorporated 1998.")
