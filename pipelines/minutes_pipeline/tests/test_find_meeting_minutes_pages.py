import json
from pathlib import Path
from unittest import mock

import pytest

from steps.find_meeting_minutes_pages.process import (
    STEP_NAME,
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
