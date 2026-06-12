import json
from unittest.mock import patch

import pytest

from steps.match_gov_urls.process import (
    normalise, best_match, scrape_gov_ie, process,
    MATCH_THRESHOLD, SOURCE_URL, STEP_NAME,
)
from lib.file_utils import IncrementalWriter


# ── normalise ─────────────────────────────────────────────────────────────

def test_normalise_lowercases():
    assert normalise("An Post") == "an post"

def test_normalise_strips_clg_suffix():
    assert normalise("Adare Heritage Trust CLG") == "adare heritage trust"

def test_normalise_strips_ltd_suffix():
    assert normalise("Abargrove Ltd") == "abargrove"

def test_normalise_strips_dac_suffix():
    assert normalise("An Post GeoDirectory DAC") == "an post geodirectory"

def test_normalise_strips_parenthetical():
    assert normalise("Adoption Authority of Ireland (AAI)") == "adoption authority of ireland"

def test_normalise_collapses_whitespace():
    assert normalise("  Health  Service   Executive  ") == "health service executive"

def test_normalise_combined():
    assert normalise("Some Body CLG  (SB)") == "some body"


# ── best_match ─────────────────────────────────────────────────────────────

def _candidates(*pairs):
    """Build a candidates list from (name, url) pairs using normalise."""
    return [(name, normalise(name), url) for name, url in pairs]


def test_best_match_exact_returns_url():
    candidates = _candidates(("An Post", "https://www.gov.ie/anpost/"))
    url, score = best_match("an post", candidates)
    assert url == "https://www.gov.ie/anpost/"
    assert score >= MATCH_THRESHOLD


def test_best_match_below_threshold_returns_none():
    candidates = _candidates(("Department of Finance", "https://gov.ie/finance/"))
    url, score = best_match("totally unrelated xyz body", candidates)
    assert url is None


def test_best_match_picks_best_candidate():
    candidates = _candidates(
        ("An Post National Lottery", "https://gov.ie/lottery/"),
        ("An Post", "https://gov.ie/anpost/"),
    )
    url, score = best_match("an post", candidates)
    assert url == "https://gov.ie/anpost/"
    assert score >= MATCH_THRESHOLD


def test_best_match_empty_candidates_returns_none():
    url, score = best_match("an post", [])
    assert url is None
    assert score == 0.0


# ── scrape_gov_ie ─────────────────────────────────────────────────────────

_GOV_IE_HTML = """
<html><body>
  <section id="departments">
    <a href="/en/organisation/dept-finance/">Department of Finance</a>
  </section>
  <section id="agencies">
    <a href="/en/organisation/an-post/">An Post</a>
    <a href="/en/organisation/rte/">RTÉ</a>
  </section>
  <section id="local-authorities">
    <a href="/en/organisation/dublin-cc/">Dublin City Council</a>
  </section>
</body></html>
"""


class _MockResponse:
    def __init__(self, text, url=SOURCE_URL):
        self.text = text
        self.url = url
        self.status_code = 200

    def raise_for_status(self):
        pass


def test_scrape_extracts_names_from_all_sections(monkeypatch):
    monkeypatch.setattr(
        "steps.match_gov_urls.process.fetch",
        lambda *a, **kw: _MockResponse(_GOV_IE_HTML),
    )
    result = scrape_gov_ie()
    names = [name for name, _ in result]
    assert "Department of Finance" in names
    assert "An Post" in names
    assert "RTÉ" in names
    assert "Dublin City Council" in names


def test_scrape_returns_absolute_urls(monkeypatch):
    monkeypatch.setattr(
        "steps.match_gov_urls.process.fetch",
        lambda *a, **kw: _MockResponse(_GOV_IE_HTML),
    )
    result = scrape_gov_ie()
    for _, url in result:
        assert url.startswith("https://")


def test_scrape_deduplicates_by_url(monkeypatch):
    html_dup = """
    <html><body>
      <section id="departments">
        <a href="/en/org/an-post/">An Post</a>
        <a href="/en/org/an-post/">An Post Again</a>
      </section>
      <section id="agencies"></section>
      <section id="local-authorities"></section>
    </body></html>
    """
    monkeypatch.setattr(
        "steps.match_gov_urls.process.fetch",
        lambda *a, **kw: _MockResponse(html_dup),
    )
    result = scrape_gov_ie()
    urls = [url for _, url in result]
    assert len(urls) == len(set(urls))


def test_scrape_skips_missing_section(monkeypatch):
    html_no_local = """
    <html><body>
      <section id="departments"><a href="/en/org/d/">Dept A</a></section>
    </body></html>
    """
    monkeypatch.setattr(
        "steps.match_gov_urls.process.fetch",
        lambda *a, **kw: _MockResponse(html_no_local),
    )
    result = scrape_gov_ie()
    assert len(result) == 1
    assert result[0][0] == "Dept A"


# ── process() ─────────────────────────────────────────────────────────────

def _make_body(id, name, url=None):
    return {
        "public_body_id": id,
        "name": name,
        "official_website_url": url,
        "sector": "S13",
        "legal_status": "State Body",
        "government_department": None,
        "nace_code": None,
        "cro": None,
        "data_vintage": 2025,
        "parent_name": None,
        "parent_id": None,
    }


def _input_data(*bodies):
    return {"public_bodies": list(bodies)}


_SIMPLE_GOV_HTML = """
<html><body>
  <section id="agencies">
    <a href="/en/organisation/an-post/">An Post</a>
    <a href="/en/organisation/rte/">RTÉ</a>
  </section>
  <section id="departments"></section>
  <section id="local-authorities"></section>
</body></html>
"""


def test_process_populates_url_for_matched_body(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "steps.match_gov_urls.process.fetch",
        lambda *a, **kw: _MockResponse(_SIMPLE_GOV_HTML),
    )
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, STEP_NAME, force=True)

    process(_input_data(_make_body(1, "An Post")), tmp_path, writer)
    writer.finalize()

    output = json.loads(output_path.read_text())
    assert output["results"][0]["official_website_url"] == "https://www.gov.ie/en/organisation/an-post/"


def test_process_leaves_null_for_unmatched_body(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "steps.match_gov_urls.process.fetch",
        lambda *a, **kw: _MockResponse(_SIMPLE_GOV_HTML),
    )
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, STEP_NAME, force=True)

    process(_input_data(_make_body(99, "Completely Unknown Agency XYZ")), tmp_path, writer)
    writer.finalize()

    output = json.loads(output_path.read_text())
    assert output["results"][0]["official_website_url"] is None


def test_process_writes_match_log(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "steps.match_gov_urls.process.fetch",
        lambda *a, **kw: _MockResponse(_SIMPLE_GOV_HTML),
    )
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, STEP_NAME, force=True)

    process(
        _input_data(_make_body(1, "An Post"), _make_body(2, "Completely Unknown XYZ")),
        tmp_path,
        writer,
    )

    log = json.loads((tmp_path / "match_log.json").read_text())
    assert len(log) == 2

    matched = next(e for e in log if e["public_body_id"] == 1)
    unmatched = next(e for e in log if e["public_body_id"] == 2)

    assert matched["matched_url"] == "https://www.gov.ie/en/organisation/an-post/"
    assert matched["match_score"] >= MATCH_THRESHOLD
    assert unmatched["matched_url"] is None


def test_process_exits_if_gov_ie_returns_no_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "steps.match_gov_urls.process.fetch",
        lambda *a, **kw: _MockResponse("<html><body></body></html>"),
    )
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, STEP_NAME, force=True)

    with pytest.raises(SystemExit) as exc:
        process(_input_data(_make_body(1, "An Post")), tmp_path, writer)
    assert exc.value.code != 0
