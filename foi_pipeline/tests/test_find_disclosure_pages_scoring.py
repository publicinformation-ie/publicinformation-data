from steps.find_disclosure_pages.process import _tokenize


def test_tokenize_splits_on_non_alphanumeric():
    assert _tokenize("/en/foi-disclosure-log/") == {"en", "foi", "disclosure", "log"}


def test_tokenize_combines_multiple_strings():
    assert _tokenize("/foi/", "Disclosure Log") == {"foi", "disclosure", "log"}


def test_tokenize_login_does_not_yield_log():
    assert "log" not in _tokenize("/account/Login.aspx")


def test_tokenize_blog_geology_logo_do_not_yield_log():
    assert "log" not in _tokenize("/blog")
    assert "log" not in _tokenize("/services/geology")
    assert "log" not in _tokenize("/img/purple_flag_logo.jpg")


def test_tokenize_handles_empty_and_none():
    assert _tokenize("") == set()
    assert _tokenize(None) == set()
    assert _tokenize("", None, "") == set()


def test_tokenize_handles_multiple_spaces():
    assert _tokenize("foi    disclosure") == {"foi", "disclosure"}


def test_tokenize_preserves_alphanumeric_runs():
    assert _tokenize("foi2024") == {"foi2024"}
    assert _tokenize("foi-2024-log") == {"foi", "2024", "log"}


def test_tokenize_case_insensitive():
    assert _tokenize("DISCLOSURE") == {"disclosure"}
    assert _tokenize("DisclOsureLog") == {"disclosurelog"}


from steps.find_disclosure_pages.process import _score_link


def test_disclosure_plus_log_is_strongest():
    assert _score_link({"foi", "disclosure", "log"}) == 100


def test_foi_plus_log():
    assert _score_link({"foi", "logs"}) == 90


def test_foi_plus_decisions():
    assert _score_link({"foi", "decisions"}) == 80


def test_published_plus_foi():
    assert _score_link({"published", "foi"}) == 70


def test_disclosure_alone_is_medium():
    assert _score_link({"disclosure"}) == 40


def test_foi_request_alone_is_weak():
    assert _score_link({"foi", "request"}) == 10


def test_noise_tokens_score_zero():
    assert _score_link({"login"}) == 0
    assert _score_link({"blog"}) == 0
    assert _score_link({"geology"}) == 0
    assert _score_link({"purple", "flag", "logo", "jpg"}) == 0


def test_protected_disclosures_disqualified():
    assert _score_link({"protected", "disclosures"}) == 0


def test_how_to_make_a_request_disqualified():
    assert _score_link({"how", "to", "make", "an", "foi", "request"}) == 0


def test_publication_scheme_disqualified():
    assert _score_link({"freedom", "information", "publication", "scheme"}) == 0
    assert _score_link({"model", "publication", "scheme"}) == 0


def test_guide_and_guidance_disqualified():
    assert _score_link({"guide", "foi"}) == 0
    assert _score_link({"guidance", "foi"}) == 0


from steps.find_disclosure_pages.process import find_disclosure_link


def test_find_link_picks_highest_scoring_not_first():
    html = """<html><body>
      <a href="/account/login">Login</a>
      <a href="/blog">Blog</a>
      <a href="/foi/foi-disclosure-log/">FOI Disclosure Log</a>
    </body></html>"""
    url, sc = find_disclosure_link(html, "https://x.ie/foi/")
    assert url == "https://x.ie/foi/foi-disclosure-log/"
    assert sc == 100


def test_find_link_returns_none_when_only_noise():
    html = '<html><body><a href="/login">Login</a><a href="/blog">Blog</a></body></html>'
    assert find_disclosure_link(html, "https://x.ie/foi/") is None


def test_find_link_skips_irish_language_ga_path():
    html = '<html><body><a href="/ga/foi-disclosure-log/">Nochtadh</a></body></html>'
    assert find_disclosure_link(html, "https://x.ie/foi/") is None


def test_find_link_rejects_how_to_request_form():
    html = '<html><body><a href="/how-to-make-an-foi-request/">How to make an FOI request</a></body></html>'
    assert find_disclosure_link(html, "https://x.ie/foi/") is None


def test_find_link_skips_fragment_anchor_same_page():
    # #foi-logs is a same-page anchor — the crawl must skip it and find the real collections link
    html = """<html><body>
        <a href="#foi-logs">FOI Logs</a>
        <a href="/collections/foi-logs/">FOI Disclosure Logs</a>
    </body></html>"""
    base = "https://www.gov.ie/en/department-of-housing-local-government-and-heritage/organisation-information/freedom-of-information-foi/"
    result = find_disclosure_link(html, base)
    assert result is not None
    url, _ = result
    assert "#foi-logs" not in url
    assert "collections/foi-logs" in url


def test_find_link_fragment_only_returns_none():
    # If the only matching link is a same-page anchor, return None (no genuine disclosure page found)
    html = """<html><body>
        <a href="#foi-logs">FOI Logs</a>
    </body></html>"""
    base = "https://www.gov.ie/en/organisation/foi/"
    assert find_disclosure_link(html, base) is None
