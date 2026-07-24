from steps.find_foi_email_pages.process import _score_link


def test_foi_plus_contact_scores_100():
    assert _score_link({"foi", "contact"}) == 100


def test_foi_plus_officer_scores_100():
    assert _score_link({"foi", "officer"}) == 100


def test_freedom_plus_unit_scores_100():
    assert _score_link({"freedom", "of", "information", "unit"}) == 100


def test_contact_plus_officer_without_foi_scores_80():
    assert _score_link({"contact", "officer"}) == 80


def test_contact_alone_scores_50():
    assert _score_link({"contact", "us"}) == 50
    assert _score_link({"contacts"}) == 50


def test_officer_alone_scores_40():
    assert _score_link({"officer"}) == 40
    assert _score_link({"unit"}) == 40
    assert _score_link({"team"}) == 40
    assert _score_link({"staff"}) == 40
    assert _score_link({"directory"}) == 40


def test_no_matching_tokens_scores_0():
    assert _score_link({"privacy", "policy"}) == 0


def test_negative_token_disqualifies_even_with_foi_contact():
    assert _score_link({"foi", "contact", "login"}) == 0
    assert _score_link({"contact", "officer", "blog"}) == 0
    assert _score_link({"contact", "publication", "scheme"}) == 0


def test_negative_tokens_are_token_matched_not_substring():
    # 'log' inside 'catalogue'/'blogger' must not disqualify — verified via
    # the shared _tokenize (token split), not _score_link directly.
    from steps.find_disclosure_pages.process import _tokenize
    assert "blog" not in _tokenize("catalogue")
    assert _score_link({"contact", "catalogue"}) == 50


from steps.find_foi_email_pages.process import find_candidate_links


def test_finds_highest_scoring_link_first():
    html = """<html><body>
      <a href="/contact">Contact Us</a>
      <a href="/foi-officer">FOI Officer</a>
    </body></html>"""
    candidates = find_candidate_links(html, "https://x.ie/foi/")
    assert candidates[0] == ("https://x.ie/foi-officer", 100)
    assert candidates[1] == ("https://x.ie/contact", 50)


def test_caps_at_three_candidates():
    html = """<html><body>
      <a href="/foi-officer">FOI Officer</a>
      <a href="/foi-unit">FOI Unit</a>
      <a href="/foi-contact">FOI Contact</a>
      <a href="/foi-team">FOI Team</a>
    </body></html>"""
    candidates = find_candidate_links(html, "https://x.ie/foi/")
    assert len(candidates) == 3


def test_rejects_zero_score_links():
    html = '<html><body><a href="/privacy">Privacy Policy</a></body></html>'
    assert find_candidate_links(html, "https://x.ie/foi/") == []


def test_rejects_negative_token_links():
    html = '<html><body><a href="/login">Login</a></body></html>'
    assert find_candidate_links(html, "https://x.ie/foi/") == []


def test_rejects_document_extensions():
    html = '<html><body><a href="/contact-officer.pdf">Contact Officer</a></body></html>'
    assert find_candidate_links(html, "https://x.ie/foi/") == []


def test_rejects_same_page_anchor():
    html = '<html><body><a href="#contact">Contact</a></body></html>'
    assert find_candidate_links(html, "https://x.ie/foi/") == []


def test_rejects_unsafe_url():
    html = '<html><body><a href="http://localhost/contact-officer">Contact Officer</a></body></html>'
    assert find_candidate_links(html, "https://x.ie/foi/") == []


def test_deduplicates_same_resolved_url():
    html = """<html><body>
      <a href="/contact-officer">Contact the FOI Officer</a>
      <a href="/contact-officer">FOI Officer Contact</a>
    </body></html>"""
    candidates = find_candidate_links(html, "https://x.ie/foi/")
    assert len(candidates) == 1
