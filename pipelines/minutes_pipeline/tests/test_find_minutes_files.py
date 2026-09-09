import json
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from steps.find_minutes_files.process import (
    STEP_NAME,
    _looks_like_minutes,
    collect_minutes_links,
    parse_meeting_date,
    pending_sources,
    process,
)
from lib.file_utils import read_json


def test_parse_meeting_date_iso_from_link_text():
    assert parse_meeting_date("Meeting Minutes 08 July 2024", "https://x.ie/minutes") == "2024-07-08"
    assert parse_meeting_date("", "https://x.ie/meeting-2024-07-08.pdf") == "2024-07-08"


def test_parse_meeting_date_null_when_undeterminable():
    assert parse_meeting_date("Ordinary Meeting", "https://x.ie/minutes.pdf") is None


def test_collect_minutes_links_collects_pdfs_and_follows_year_links():
    page = (
        '<html><body>'
        '<a href="/minutes/2024">2024</a>'
        '<a href="/minutes/2025">2025</a>'
        '<a href="/documents/agenda.pdf">Agenda</a>'
        '</body></html>'
    )
    year_page = (
        '<html><body>'
        '<a href="/files/meeting-2024-07-08.pdf">Meeting 08 July 2024</a>'
        '<a href="/files/meeting-2024-08-12.pdf">Meeting 12 August 2024</a>'
        '<a href="/files/some-report.pdf">Annual Report</a>'
        '</body></html>'
    )
    html_by_url = {
        "https://www.meath.ie/minutes": page,
        "https://www.meath.ie/minutes/2024": year_page,
        "https://www.meath.ie/minutes/2025": "<html><body></body></html>",
    }

    def fake_fetch(method, url, allow_redirects=True):
        return SimpleNamespace(text=html_by_url[url], url=url)

    with mock.patch("steps.find_minutes_files.process.fetch", side_effect=fake_fetch):
        records = collect_minutes_links(
            {"public_body_id": 1511, "municipal_district": "Navan",
             "minutes_page_url": "https://www.meath.ie/minutes"},
            "https://www.meath.ie/minutes",
        )
    assert len(records) == 2
    assert records[0]["file_url"] == "https://www.meath.ie/files/meeting-2024-07-08.pdf"
    assert records[0]["meeting_date"] == "2024-07-08"
    assert records[0]["municipal_district"] == "Navan"


def test_collect_minutes_links_follows_descriptive_year_links():
    """Real Meath pages link year listings with descriptive text (e.g. '2024
    Navan Municipal District Meetings'), not bare years — these must be
    followed one level deep to reach the PDFs."""
    page = (
        '<html><body>'
        '<a href="/minutes/2024-navan">2024 Navan Municipal District Meetings</a>'
        '<a href="/agenda.pdf">Agenda</a>'
        '</body></html>'
    )
    year_page = (
        '<html><body>'
        '<a href="/files/06-2024 Minutes Navan MD.pdf">Minutes - June 2024</a>'
        '<a href="/files/07-2024 Public Notice Navan MD.pdf">Public Notice - July 2024</a>'
        '</body></html>'
    )
    html_by_url = {
        "https://www.meath.ie/minutes": page,
        "https://www.meath.ie/minutes/2024-navan": year_page,
    }

    def fake_fetch(method, url, allow_redirects=True):
        return SimpleNamespace(text=html_by_url[url], url=url)

    with mock.patch("steps.find_minutes_files.process.fetch", side_effect=fake_fetch):
        records = collect_minutes_links(
            {"public_body_id": 1511, "municipal_district": "Navan",
             "minutes_page_url": "https://www.meath.ie/minutes"},
            "https://www.meath.ie/minutes",
        )
    # The minutes PDF is kept; the public-notice PDF is excluded.
    assert len(records) == 1
    assert records[0]["file_url"] == "https://www.meath.ie/files/06-2024 Minutes Navan MD.pdf"


def test_looks_like_minutes_rejects_public_notices():
    assert _looks_like_minutes(
        "Public Notice - Navan Municipal District Meeting December 2024",
        "https://x.ie/12-2024%20Public%20Notice.pdf") is False
    assert _looks_like_minutes(
        "Minutes - Navan Municipal District Meeting December 2024",
        "https://x.ie/12-2024%20Minutes.pdf") is True


def test_pending_sources_skips_already_collected_pages(make_writer):
    writer = make_writer(STEP_NAME)
    writer.results = [
        {"public_body_id": 1511, "minutes_page_url": "https://x.ie/navan"},
    ]
    items = [
        {"public_body_id": 1511, "minutes_page_url": "https://x.ie/navan"},
        {"public_body_id": 1511, "minutes_page_url": "https://x.ie/trim"},
    ]
    assert pending_sources(writer, items) == [items[1]]