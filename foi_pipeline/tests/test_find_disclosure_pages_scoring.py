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
