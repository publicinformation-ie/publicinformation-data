import json
from pathlib import Path
from unittest import mock

import pytest

from steps.find_meeting_minutes_pages.process import (
    STEP_NAME,
    find_minutes_link,
    override_sources,
    process,
)
from lib.file_utils import read_json


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
