"""Tests for the disclosure-page-discovery experiment approaches."""
import importlib.util
from pathlib import Path

_APPROACHES = (
    Path(__file__).parents[1]
    / "experiments"
    / "2026-06-09-disclosure-page-discovery"
    / "approaches"
)


def _load(name):
    path = _APPROACHES / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"Cannot load {path}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_sf = _load("scoring_fix")
_tokenize = _sf._tokenize
_score_link = _sf._score_link
NEGATIVE_TOKENS = _sf.NEGATIVE_TOKENS
ACCEPT_THRESHOLD = _sf.ACCEPT_THRESHOLD
find_disclosure_link = _sf.find_disclosure_link


# ── Approach A: publication token fix ──────────────────────────────────────

def test_publication_alone_not_suppressed():
    """'publication' without 'scheme' should no longer zero the score."""
    tokens = _tokenize("freedom-of-information-disclosure-log-publication")
    assert _score_link(tokens) >= ACCEPT_THRESHOLD


def test_publication_scheme_still_suppressed():
    """'publication' + 'scheme' together should still zero the score."""
    tokens = _tokenize("model-publication-scheme")
    assert _score_link(tokens) == 0


def test_scheme_alone_still_suppressed():
    """'scheme' alone is still in NEGATIVE_TOKENS."""
    tokens = _tokenize("some-scheme-page")
    assert _score_link(tokens) == 0


def test_offaly_url_scores_positive():
    """Offaly URL: freedom-of-information-disclosure-log-publication."""
    tokens = _tokenize("https://www.offaly.ie/freedom-of-information-disclosure-log-publication/")
    assert _score_link(tokens) >= ACCEPT_THRESHOLD


def test_tipperary_url_scores_positive():
    tokens = _tokenize(
        "https://www.tipperarycoco.ie/governance-and-administration/freedom-information-disclosure-log-publication"
    )
    assert _score_link(tokens) >= ACCEPT_THRESHOLD


def test_foi_responses_scores_medium():
    """foi + responses should score 60."""
    tokens = _tokenize("https://example.ie/foi-responses")
    assert _score_link(tokens) == 60


def test_responses_alone_scores_low():
    """responses alone should score 20."""
    tokens = _tokenize("https://example.ie/responses")
    assert _score_link(tokens) == 20


def test_foi_released_scores_medium():
    """foi + released should score 60."""
    tokens = _tokenize("https://example.ie/foi-released")
    assert _score_link(tokens) == 60


def test_disclosure_log_still_scores_100():
    """Regression: existing top-scoring pattern unchanged."""
    tokens = _tokenize("foi-disclosure-log")
    assert _score_link(tokens) == 100


def test_publications_still_suppressed():
    """'publications' (plural) stays in NEGATIVE_TOKENS."""
    tokens = _tokenize("https://example.ie/publications")
    assert _score_link(tokens) == 0


# ── find_disclosure_link integration ───────────────────────────────────────

def test_find_disclosure_link_finds_publication_url():
    """A page containing a 'disclosure-log-publication' link should now match."""
    html = """<html><body>
    <a href="/freedom-of-information-disclosure-log-publication">FOI Disclosure Log</a>
    </body></html>"""
    result = find_disclosure_link(html, "https://www.example.ie/")
    assert result is not None
    url, score = result
    assert "disclosure-log-publication" in url
    assert score >= ACCEPT_THRESHOLD


def test_find_disclosure_link_ignores_publication_scheme():
    """A page with only a publication-scheme link should return None."""
    html = """<html><body>
    <a href="/model-publication-scheme">Publication Scheme</a>
    </body></html>"""
    result = find_disclosure_link(html, "https://www.example.ie/")
    assert result is None


# ── Approach C1: two-hop crawl ─────────────────────────────────────────────

_th = _load("two_hop_crawl")
_is_foi_section_link = _th._is_foi_section_link
_section_score = _th._section_score
find_disclosure_link_two_hop = _th.find_disclosure_link_two_hop


def test_foi_section_link_detected():
    """A link to /freedom-of-information should be identified as a section candidate."""
    tokens = _tokenize("https://example.ie/freedom-of-information")
    assert _is_foi_section_link(tokens) is True


def test_disclosure_link_not_a_section_candidate():
    """A link that already contains 'disclosure' is not a section candidate."""
    tokens = _tokenize("https://example.ie/foi-disclosure-log")
    assert _is_foi_section_link(tokens) is False


def test_unrelated_link_not_a_section_candidate():
    """A link with no FOI tokens is not a section candidate."""
    tokens = _tokenize("https://example.ie/contact-us")
    assert _is_foi_section_link(tokens) is False


def test_section_score_prefers_foi_token():
    """Links with 'foi' in href rank higher than 'freedom+information' only."""
    tokens_foi = _tokenize("https://example.ie/foi-section")
    tokens_long = _tokenize("https://example.ie/freedom-of-information")
    assert _section_score(tokens_foi) > _section_score(tokens_long)


def test_two_hop_finds_disclosure_on_second_page():
    """When FOI page has no direct link, follow a section link to find the log."""
    foi_html = """<html><body>
    <a href="/freedom-of-information">Freedom of Information</a>
    </body></html>"""

    section_html = """<html><body>
    <a href="/foi-disclosure-log">FOI Disclosure Log</a>
    </body></html>"""

    pages = {
        "https://example.ie/freedom-of-information": section_html,
    }

    def mock_fetcher(url):
        return pages[url]

    result = find_disclosure_link_two_hop(foi_html, "https://example.ie/foi", fetcher=mock_fetcher)
    assert result is not None
    url, _, method = result
    assert "disclosure-log" in url
    assert method == "crawl_2hop"


def test_two_hop_returns_direct_match_on_first_page():
    """If the first page already has a disclosure link, return it directly."""
    foi_html = """<html><body>
    <a href="/foi-disclosure-log">Disclosure Log</a>
    </body></html>"""

    result = find_disclosure_link_two_hop(foi_html, "https://example.ie/foi", fetcher=None)
    assert result is not None
    _, _, method = result
    assert method == "crawl"


def test_two_hop_returns_none_when_no_match():
    """Returns None when neither the FOI page nor any section page has a log."""
    foi_html = """<html><body>
    <a href="/freedom-of-information">Freedom of Information</a>
    </body></html>"""

    section_html = """<html><body>
    <a href="/contact">Contact</a>
    </body></html>"""

    def mock_fetcher(_):
        return section_html

    result = find_disclosure_link_two_hop(foi_html, "https://example.ie/foi", fetcher=mock_fetcher)
    assert result is None
