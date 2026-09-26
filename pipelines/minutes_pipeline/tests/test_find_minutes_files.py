import json
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from steps.find_minutes_files.process import (
    STEP_NAME,
    _exclusion_reason,
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
        return SimpleNamespace(text=html_by_url[url], url=url, headers={})

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
        return SimpleNamespace(text=html_by_url[url], url=url, headers={})

    with mock.patch("steps.find_minutes_files.process.fetch", side_effect=fake_fetch):
        records = collect_minutes_links(
            {"public_body_id": 1511, "municipal_district": "Navan",
             "minutes_page_url": "https://www.meath.ie/minutes"},
            "https://www.meath.ie/minutes",
        )
    # The minutes PDF is kept; the public-notice PDF is excluded.
    assert len(records) == 1
    assert records[0]["file_url"] == "https://www.meath.ie/files/06-2024 Minutes Navan MD.pdf"


def test_collect_minutes_links_follows_year_suffix_descriptive_links():
    """Some councils (e.g. Kildare) link year listings with the year after the
    descriptor ('Minutes 2021'), not leading ('2024 Navan Municipal District
    Meetings'). These must be followed one level deep too."""
    page = (
        '<html><body>'
        '<a href="/minutes/2021">Minutes 2021</a>'
        '<a href="/agenda.pdf">Agenda</a>'
        '</body></html>'
    )
    year_page = (
        '<html><body>'
        '<a href="/files/2021-12-20-minutes.pdf">Minutes for Kildare County Council '
        'Meeting held on 20 December 2021</a>'
        '</body></html>'
    )
    html_by_url = {
        "https://www.kildarecoco.ie/minutes": page,
        "https://www.kildarecoco.ie/minutes/2021": year_page,
    }

    def fake_fetch(method, url, allow_redirects=True):
        return SimpleNamespace(text=html_by_url[url], url=url, headers={})

    with mock.patch("steps.find_minutes_files.process.fetch", side_effect=fake_fetch):
        records = collect_minutes_links(
            {"public_body_id": 1456, "municipal_district": None,
             "minutes_page_url": "https://www.kildarecoco.ie/minutes"},
            "https://www.kildarecoco.ie/minutes",
        )
    assert len(records) == 1
    assert records[0]["file_url"] == "https://www.kildarecoco.ie/files/2021-12-20-minutes.pdf"
    assert records[0]["meeting_date"] == "2021-12-20"
    assert records[0]["public_body_id"] == 1456


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


ARCHIVE_URL = ("https://www.wicklow.ie/Portals/0/Documents/Arts Heritage & Archives/Archives/"
               "Collections/Digitised Collections/Arklow-Town-Commissioners-Urban-District-"
               "Council-Minute-Books-1878-1947/1889 - 1894.pdf")


def test_exclusion_reason_archive_path():
    kind, _ = _exclusion_reason("1889 - 1894File type .pdf", ARCHIVE_URL)
    assert kind == "ArchivedDocument"


def test_exclusion_reason_historical_year():
    kind, _ = _exclusion_reason("1878 - 1889File type .pdf",
                                "https://www.x.ie/files/1878-1889-minutes.pdf")
    assert kind == "HistoricalDocument"


def test_exclusion_reason_year_rule_fails_open():
    """DDMM-YYYY ('1909-2021' = 19 Sep 2021) and filesize fragments
    ('1016KB' next to 2019) contain old-looking numbers alongside a modern
    year — a modern year anywhere keeps the link."""
    assert _exclusion_reason("council meeting",
                             "https://x.ie/media/xx/cork-city-lcdc-minutes-of-meeting-1909-2021.pdf") is None
    assert _exclusion_reason("Minutes_LCDC_Meeting_December_2019.pdf(PDF,1016.89KB)",
                             "https://x.ie/files/2023-06/Minutes_LCDC_Meeting_December_2019.pdf") is None


def test_exclusion_reason_keeps_modern_minutes():
    assert _exclusion_reason("Minutes - June 2024",
                             "https://x.ie/files/06-2024 Minutes.pdf") is None
    assert _exclusion_reason("Ordinary Meeting", "https://x.ie/minutes.pdf") is None


def test_exclusion_reason_keeps_archived_meetings_folders():
    """Kildare/Longford file current minutes under 'ArchivedMeetings' /
    'meetings archive' folders — 'archiv*' alone must not exclude them."""
    assert _exclusion_reason(
        "Minutes December Monthly Meeting Full Council",
        "https://kildarecoco.ie/YourCouncil/FullCouncil/ArchivedMeetings/2025/Minutes/15122025 Minutes.pdf",
    ) is None
    assert _exclusion_reason(
        "Minutes December meeting",
        "https://www.longfordcoco.ie/your-council/council-meetings/council%20meetings%20archive/2025/minutes-december-meeting.pdf",
    ) is None


def test_collect_minutes_links_excludes_archive_and_historical():
    page = (
        '<html><body>'
        '<a href="/files/06-2024 Minutes.pdf">Minutes - June 2024</a>'
        f'<a href="{ARCHIVE_URL}">1889 - 1894File type .pdf</a>'
        '<a href="/files/1878-1889-minutes.pdf">1878 - 1889File type .pdf</a>'
        '</body></html>'
    )

    def fake_fetch(method, url, allow_redirects=True):
        return SimpleNamespace(text=page, url=url, headers={})

    excluded = []
    with mock.patch("steps.find_minutes_files.process.fetch", side_effect=fake_fetch):
        records = collect_minutes_links(
            {"public_body_id": 1876, "municipal_district": None,
             "minutes_page_url": "https://www.wicklow.ie/minutes"},
            "https://www.wicklow.ie/minutes",
            excluded_out=excluded,
        )
    assert [r["file_url"] for r in records] == ["https://www.wicklow.ie/files/06-2024 Minutes.pdf"]
    assert sorted(e["error_type"] for e in excluded) == ["ArchivedDocument", "HistoricalDocument"]
    assert all(e["context"]["public_body_id"] == 1876 for e in excluded)


def test_process_logs_exclusions_to_errors_json(tmp_path, make_writer):
    page = (
        '<html><body>'
        f'<a href="{ARCHIVE_URL}">1889 - 1894File type .pdf</a>'
        '</body></html>'
    )

    def fake_fetch(method, url, allow_redirects=True):
        return SimpleNamespace(text=page, url=url, headers={})

    with mock.patch("steps.find_minutes_files.process.fetch", side_effect=fake_fetch):
        writer = make_writer(STEP_NAME)
        process({"results": [{
            "public_body_id": 1876, "municipal_district": None,
            "minutes_page_url": "https://www.wicklow.ie/minutes",
            "source_method": "crawl"}]}, tmp_path, writer)
    assert writer.results == []
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert len(errors) == 1
    assert errors[0]["error_type"] == "ArchivedDocument"
    assert errors[0]["context"]["file_url"] == ARCHIVE_URL

def _b64(s):
    import base64
    return base64.b64encode(s.encode()).decode()


def test_collect_minutes_links_skips_non_html_responses():
    # A year-looking link that serves a binary file (no .pdf suffix) must not
    # be parsed as HTML — html.parser raises ValueError on binary charrefs.
    page = ('<html><body>'
            '<a href="/download?id=7">Council Meetings 2024</a>'
            '</body></html>')
    responses = {
        "https://www.example.ie/minutes": SimpleNamespace(
            text=page, url="https://www.example.ie/minutes",
            headers={"Content-Type": "text/html; charset=utf-8"}),
        "https://www.example.ie/download?id=7": SimpleNamespace(
            text="&#0C\x00\xff binary", url="https://www.example.ie/download?id=7",
            headers={"Content-Type": "application/pdf"}),
    }

    def fake_fetch(method, url, allow_redirects=True):
        return responses[url]

    with mock.patch("steps.find_minutes_files.process.fetch", side_effect=fake_fetch):
        records = collect_minutes_links(
            {"public_body_id": 1, "minutes_page_url": "https://www.example.ie/minutes"},
            "https://www.example.ie/minutes",
        )
    assert records == []


def test_collect_minutes_links_pdf_name_in_base64_query_param():
    # Galway City's file manager: ?r=/download&path=<base64 of the file path>.
    # The URL path has no .pdf suffix; the filename lives in the query.
    minutes = _b64("/2025/6. June/Adopted Minutes June Plenary Meeting 9 June 2025.pdf")
    agenda = _b64("/2025/6. June/Agenda June Plenary Meeting 9th June 2025.pdf")
    base = "https://files.example.ie/gccfiles/?r=/download&path="
    page = ('<html><body>'
            f'<a href="{base}{minutes}">09-06-2025 Adopted Minutes June Meeting</a>'
            f'<a href="{base}{agenda}">09-06-2025 Agenda - Plenary Meeting June Meeting</a>'
            '</body></html>')

    def fake_fetch(method, url, allow_redirects=True):
        assert url == "https://www.example.ie/minutes", f"should not fetch {url}"
        return SimpleNamespace(text=page, url=url, headers={})

    with mock.patch("steps.find_minutes_files.process.fetch", side_effect=fake_fetch):
        records = collect_minutes_links(
            {"public_body_id": 1340, "minutes_page_url": "https://www.example.ie/minutes"},
            "https://www.example.ie/minutes",
        )
    assert [r["file_url"] for r in records] == [base + minutes]
    assert records[0]["meeting_date"] == "2025-06-09"


def test_collect_minutes_links_pdf_name_in_plain_query_param():
    page = ('<html><body>'
            '<a href="/getfile.aspx?file=Minutes%20of%20Meeting%2012%20May%202025.pdf">'
            'May meeting</a>'
            '</body></html>')

    def fake_fetch(method, url, allow_redirects=True):
        return SimpleNamespace(text=page, url=url, headers={})

    with mock.patch("steps.find_minutes_files.process.fetch", side_effect=fake_fetch):
        records = collect_minutes_links(
            {"public_body_id": 1, "minutes_page_url": "https://www.example.ie/minutes"},
            "https://www.example.ie/minutes",
        )
    assert len(records) == 1
    assert records[0]["meeting_date"] == "2025-05-12"
