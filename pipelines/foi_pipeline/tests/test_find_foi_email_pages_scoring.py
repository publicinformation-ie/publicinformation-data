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
