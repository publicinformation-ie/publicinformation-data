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
