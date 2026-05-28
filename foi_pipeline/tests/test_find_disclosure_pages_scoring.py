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
    assert _score_link({"published", "foi", "requests"}) == 70


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
