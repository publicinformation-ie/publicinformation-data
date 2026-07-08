from pathlib import Path

import pytest

from steps.parse_wdw_bodies.process import extract_wdw_slug, parse_html, STEP_NAME

PIPELINE_DIR = Path(__file__).parent.parent
HTML_PATH = PIPELINE_DIR / "data" / "who-does-what.html"


# ── extract_wdw_slug ────────────────────────────────────────────────────────

def test_extract_wdw_slug_plain():
    assert extract_wdw_slug(
        "https://www.gov.ie/en/office-of-the-revenue-commissioners/"
        "organisation-information/revenue-commissioners-who-does-what/"
    ) == "office-of-the-revenue-commissioners"


def test_extract_wdw_slug_percent_decodes():
    assert extract_wdw_slug(
        "https://www.gov.ie/en/tailte-%C3%A9ireann/organisation-information/"
        "tailte-%C3%A9ireann-who-does-what/"
    ) == "tailte-éireann"


def test_extract_wdw_slug_publicjobs():
    assert extract_wdw_slug(
        "https://www.gov.ie/en/publicjobs/organisation-information/publicjobs-who-does-what/"
    ) == "publicjobs"


# ── parse_html ───────────────────────────────────────────────────────────────

def test_parse_html_returns_27_records():
    html = HTML_PATH.read_text(encoding="utf-8")
    records = parse_html(html)
    assert len(records) == 27


def test_parse_html_excludes_campaign_self_link():
    html = HTML_PATH.read_text(encoding="utf-8")
    records = parse_html(html)
    names = [r["wdw_name"] for r in records]
    assert "Who Does What" not in names


def test_parse_html_revenue_commissioners():
    html = HTML_PATH.read_text(encoding="utf-8")
    records = parse_html(html)
    revenue = next(r for r in records if r["wdw_name"] == "Revenue Commissioners")
    assert revenue["wdw_slug"] == "office-of-the-revenue-commissioners"
    assert revenue["wdw_url"] == (
        "https://www.gov.ie/en/office-of-the-revenue-commissioners/"
        "organisation-information/revenue-commissioners-who-does-what/"
    )


def test_parse_html_publicjobs():
    html = HTML_PATH.read_text(encoding="utf-8")
    records = parse_html(html)
    pj = next(r for r in records if r["wdw_slug"] == "publicjobs")
    assert pj["wdw_name"] == "publicjobs"


def test_parse_html_slugs_are_unique():
    html = HTML_PATH.read_text(encoding="utf-8")
    records = parse_html(html)
    slugs = [r["wdw_slug"] for r in records]
    assert len(slugs) == len(set(slugs))


def test_parse_html_no_campaign_body_div_exits(tmp_path):
    with pytest.raises(SystemExit) as exc:
        parse_html("<html><body><p>no campaign body here</p></body></html>")
    assert exc.value.code != 0
