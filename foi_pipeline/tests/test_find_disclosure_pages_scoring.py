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
