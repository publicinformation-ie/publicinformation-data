import json
from pathlib import Path
from unittest import mock

import pytest

import steps.find_meeting_minutes_pages.process as process_mod
from steps.find_meeting_minutes_pages.process import (
    STEP_NAME,
    _score_link,
    _tokenize,
    child_page_urls,
    expand_child_pages,
    find_minutes_link,
    override_sources,
    process,
    unemitted_sources,
)
from lib.file_utils import read_json, IncrementalWriter


def _authority(bid=1511, name="Meath County Council", slug="meath",
               districts=("Navan", "Trim"), url="https://www.meath.ie/"):
    return {
        "public_body_id": bid, "name": name, "slug": slug,
        "official_website_url": url, "municipal_districts": list(districts),
    }


def test_find_minutes_link_scores_tiered_vocabulary():
    html = (
        '<a href="/minutes">Council Minutes</a>'
        '<a href="/agenda">Agenda</a>'
        '<a href="/annual-report">Annual Report</a>'
        '<a href="/login">Login</a>'
    )
    best, score = find_minutes_link(html, "https://www.meath.ie/")
    assert best == "https://www.meath.ie/minutes"
    assert score >= 70


def test_find_minutes_link_rejects_negative_tokens():
    html = '<a href="/annual-report">Annual Report</a><a href="/login">Login</a>'
    assert find_minutes_link(html, "https://www.meath.ie/") is None


def test_find_minutes_link_threshold():
    html = '<a href="/meeting">Meeting stuff</a>'  # below threshold
    assert find_minutes_link(html, "https://www.meath.ie/") is None


def test_score_link_accepts_minutes_and_agendas_combined():
    """Combined 'Minutes & Agendas' listings are valid minutes sources
    (Wicklow's minutes page was invisible until this carve-out)."""
    assert _score_link(_tokenize("/Minutes-Agendas", "Minutes & Agendas")) >= 60


def test_score_link_still_rejects_agenda_without_minutes():
    assert _score_link(_tokenize("/agendas", "Agendas")) == 0
    assert _score_link(_tokenize("/meeting-agendas", "Meeting Agendas")) < 60


def test_score_link_other_negatives_still_win_over_minutes():
    assert _score_link(_tokenize("/minutes-annual-report", "Minutes Annual Report")) == 0


def test_find_minutes_link_prefers_minutes_agendas_page():
    html = (
        '<a href="/Council-Meetings">Council Meetings</a>'
        '<a href="/Minutes-Agendas">Minutes & Agendas</a>'
    )
    best, score = find_minutes_link(html, "https://www.wicklow.ie/")
    assert best == "https://www.wicklow.ie/Minutes-Agendas"
    assert score >= 60


def test_override_sources_produces_district_and_council_records():
    authorities = [_authority()]
    overrides = [
        {"public_body_id": 1511, "municipal_district": None,
         "minutes_page_url": "https://www.meath.ie/council/minutes",
         "source_method": "manual", "overridden": True},
        {"public_body_id": 1511, "municipal_district": "Navan",
         "minutes_page_url": "https://www.meath.ie/navan/minutes",
         "source_method": "manual", "overridden": True},
    ]
    records = override_sources(authorities, overrides)
    assert len(records) == 2
    council = next(r for r in records if r["municipal_district"] is None)
    assert council["minutes_page_url"] == "https://www.meath.ie/council/minutes"
    assert council["source_method"] == "override"
    assert council["overridden"] is True


def test_override_sources_passes_walk_config_through():
    walk = {"detail_url": "/whats-on/", "detail_text": "Meeting of",
            "paginate": "prev", "max_listing_pages": 36}
    overrides = [
        {"public_body_id": 1486, "municipal_district": None,
         "minutes_page_url": "https://www.limerick.ie/council/your-council/meetings",
         "source_method": "manual", "overridden": True, "walk": walk},
        {"public_body_id": 1511, "municipal_district": None,
         "minutes_page_url": "https://www.meath.ie/council/minutes",
         "source_method": "manual", "overridden": True},
    ]
    limerick, meath = override_sources([], overrides)
    assert limerick["walk"] == walk
    assert "walk" not in meath


def test_process_override_plus_writer_does_not_duplicate(tmp_path, make_writer):
    """The step's committed override.json uses source_method 'manual' (repo
    convention), while output records normalize it to 'override'. The writer
    must not validate override.json against the output schema (its enum is
    override/crawl) nor double-emit records: process() is the single source
    of truth and the writer only persists."""
    overrides = [
        {"public_body_id": 1511, "municipal_district": None,
         "minutes_page_url": "https://www.meath.ie/council/minutes",
         "source_method": "manual", "overridden": True},
    ]
    (tmp_path / "override.json").write_text(json.dumps(overrides))
    writer = make_writer(STEP_NAME)
    process({"results": [_authority()]}, tmp_path, writer)
    writer.finalize()
    out = read_json(tmp_path / "output.json")
    assert len(out["results"]) == 1
    assert out["results"][0]["source_method"] == "override"
    assert out["results"][0]["overridden"] is True


def test_unemitted_sources_skips_already_present_pages(make_writer):
    writer = make_writer(STEP_NAME)
    writer.results = [
        {"public_body_id": 1511, "municipal_district": "Navan",
         "minutes_page_url": "https://x.ie/navan"},
    ]
    records = [
        {"public_body_id": 1511, "municipal_district": "Navan",
         "minutes_page_url": "https://x.ie/navan"},
        {"public_body_id": 1511, "municipal_district": "Trim",
         "minutes_page_url": "https://x.ie/trim"},
    ]
    assert unemitted_sources(writer, records) == [records[1]]


def _resp(html):
    m = mock.Mock()
    m.text = html
    return m


def test_one_hop_follows_best_hub_on_homepage_miss(monkeypatch):
    home = '<a href="/meetings">Meetings</a>'  # scores 50: below 60, above 0
    hub = ('<a href="/council-minutes">Council Minutes</a>'
           '<a href="/files/minutes-jan.pdf">Council Minutes January</a>')
    pages = {"https://www.meath.ie/": home,
             "https://www.meath.ie/meetings": hub}
    monkeypatch.setattr(
        "steps.find_meeting_minutes_pages.process.fetch",
        lambda method, url, **kw: _resp(pages[url]))
    from steps.find_meeting_minutes_pages.process import _try_one_hop
    url, method = _try_one_hop(home, "https://www.meath.ie/", 1511, None, None)
    assert url == "https://www.meath.ie/council-minutes"
    assert method == "crawl"


def test_one_hop_rejects_yield_negative_hub(monkeypatch):
    home = '<a href="/meetings">Meetings</a>'
    hub = '<a href="/council-minutes">Council Minutes</a><a href="/files/agenda-jan.pdf">Council Agenda January</a>'
    pages = {"https://www.meath.ie/": home,
             "https://www.meath.ie/meetings": hub}
    monkeypatch.setattr(
        "steps.find_meeting_minutes_pages.process.fetch",
        lambda method, url, **kw: _resp(pages[url]))
    from steps.find_meeting_minutes_pages.process import _try_one_hop
    url, _ = _try_one_hop(home, "https://www.meath.ie/", 1511, None, None)
    assert url is None


def test_one_hop_hub_fetch_failure_returns_none(monkeypatch):
    def _boom(method, url, **kw):
        raise ConnectionError("down")
    monkeypatch.setattr(
        "steps.find_meeting_minutes_pages.process.fetch", _boom)
    from steps.find_meeting_minutes_pages.process import _try_one_hop
    url, _ = _try_one_hop('<a href="/meetings">Meetings</a>',
                          "https://www.meath.ie/", 1511, None, None)
    assert url is None


def test_child_page_urls_keeps_year_pages_and_skips_parent():
    parent = "https://www.sligococo.ie/YourCouncil/CountyCouncil/Minutes/"
    html = (
        '<a href="/YourCouncil/CountyCouncil/Minutes/">Minutes</a>'
        '<a href="/YourCouncil/CountyCouncil/Minutes/Minutes2026/">2026</a>'
        '<a href="/YourCouncil/CountyCouncil/Minutes/Minutes2025/">2025</a>'
        '<a href="/YourCouncil/CountyCouncil/Minutes/Minutes2025/">2025 again</a>'
        '<a href="/YourCouncil/CountyCouncil/Minutes/Minutes2025/MeetingMainBody,1,en.html">detail</a>'
    )
    assert child_page_urls(html, parent, r"/Minutes/Minutes\d{4}/$") == [
        "https://www.sligococo.ie/YourCouncil/CountyCouncil/Minutes/Minutes2026/",
        "https://www.sligococo.ie/YourCouncil/CountyCouncil/Minutes/Minutes2025/",
    ]


def test_expand_child_pages_emits_one_override_per_child(tmp_path, monkeypatch):
    parent = "https://www.sligococo.ie/YourCouncil/CountyCouncil/Minutes/"
    html = (
        '<a href="/YourCouncil/CountyCouncil/Minutes/Minutes2025/">2025</a>'
        '<a href="/YourCouncil/CountyCouncil/Minutes/Minutes2026/">2026</a>'
    )
    monkeypatch.setattr(process_mod, "fetch", lambda *a, **k: mock.Mock(text=html))
    overrides = [{
        "public_body_id": 1716, "municipal_district": None,
        "minutes_page_url": parent, "child_pages": r"/Minutes/Minutes\d{4}/$",
        "source_method": "manual", "overridden": True,
        "walk": {"detail_url": r"/Minutes\d{4}/MeetingMainBody,\d+,en\.html",
                 "detail_text": ".", "paginate": "next", "max_listing_pages": 1},
    }]
    expanded = expand_child_pages(overrides, tmp_path)
    assert [r["minutes_page_url"] for r in expanded] == [
        "https://www.sligococo.ie/YourCouncil/CountyCouncil/Minutes/Minutes2025/",
        "https://www.sligococo.ie/YourCouncil/CountyCouncil/Minutes/Minutes2026/",
    ]
    assert all("child_pages" not in r for r in expanded)
    assert all(r["walk"] == overrides[0]["walk"] for r in expanded)


def test_expand_child_pages_fetch_failure_logs_error_and_emits_nothing(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("down")
    monkeypatch.setattr(process_mod, "fetch", boom)
    overrides = [{
        "public_body_id": 1716, "municipal_district": None,
        "minutes_page_url": "https://www.sligococo.ie/YourCouncil/CountyCouncil/Minutes/",
        "child_pages": r"/Minutes/Minutes\d{4}/$",
    }]
    assert expand_child_pages(overrides, tmp_path) == []
    errors = read_json(tmp_path / "errors.json")
    assert errors[0]["error_type"] == "ConnectionError"
