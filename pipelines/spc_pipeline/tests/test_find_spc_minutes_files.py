from pathlib import Path

import pytest

from steps.find_spc_minutes_files.discovery import (
    CommitteeConfigError,
    discover_committee,
    extract_pdf_links,
    load_committees,
    validate_committees,
)
from steps.find_spc_minutes_files.process import run

PIPELINE = Path(__file__).resolve().parents[1]
COMMITTEES = PIPELINE / "steps" / "find_spc_minutes_files" / "committees.json"
PAGE_FIXTURE = Path(__file__).parent / "fixtures" / "meath-spc-page.html"


@pytest.fixture(scope="module")
def committee():
    return load_committees(COMMITTEES)[0]


@pytest.fixture(scope="module")
def page_html():
    return PAGE_FIXTURE.read_text(encoding="utf-8")


def test_committed_page_yields_exactly_six_minutes_links(committee, page_html):
    records = discover_committee(committee, page_html)
    assert len(records) == 6
    assert not [r for r in records if "agenda" in r["file_url"].lower()]
    assert not [r for r in records if "agenda" in r["link_text"].lower()]


def test_discovered_links_are_absolute_and_carry_link_text(committee, page_html):
    for record in discover_committee(committee, page_html):
        assert record["file_url"].startswith("https://www.meath.ie/")
        assert record["link_text"]
        assert record["committee_id"] == "meath/transportation-urban-regeneration"
        assert record["public_body_id"] == 1511


def test_same_file_linked_twice_is_collected_once(committee):
    url = "https://www.meath.ie/system/files/media/file-uploads/2025-10/February%202025%20Minutes.pdf"
    html = (
        f'<a href="{url}">February 2025 - Minutes - SPC</a>'
        f'<a href="{url}">February 2025 - Minutes - SPC (again)</a>'
    )
    records = discover_committee(committee, html)
    assert len(records) == 1


def test_agenda_link_is_ignored(committee):
    html = (
        '<a href="/files/February%202026%20-%20Agenda%20-%20SPC.pdf">'
        "February 2026 - Agenda - SPC</a>"
    )
    assert discover_committee(committee, html) == []


def test_pdf_links_report_link_text(committee):
    html = (
        '<a href="/a/b/May%202026%20-%20Minutes.pdf">'
        'May 2026 - Minutes - <strong>SPC</strong></a>'
    )
    links = extract_pdf_links(html, "https://www.meath.ie/page")
    assert links == [{
        "url": "https://www.meath.ie/a/b/May%202026%20-%20Minutes.pdf",
        "link_text": "May 2026 - Minutes - SPC",
    }]


def test_committees_are_unique_and_each_body_is_a_local_authority():
    committees = load_committees(COMMITTEES)
    body_output = (
        Path(__file__).resolve().parents[2]
        / "minutes_pipeline/steps/find_local_authorities/output.json"
    )
    assert len({c["committee_id"] for c in committees}) == len(committees)
    if not body_output.exists():
        pytest.skip("local-authority list is generated, not committed")
    import json

    bodies = json.loads(body_output.read_text())["results"]
    validate_committees(committees, {b["public_body_id"] for b in bodies})


def test_unknown_public_body_is_fatal(committee):
    with pytest.raises(CommitteeConfigError, match="not in the local-authority list"):
        validate_committees([committee], {9999})


def test_duplicate_committee_id_is_fatal(committee):
    with pytest.raises(CommitteeConfigError, match="duplicate committee_id"):
        validate_committees([committee, dict(committee)], {1511})


def test_missing_field_is_fatal(committee):
    broken = dict(committee)
    del broken["page_url"]
    with pytest.raises(CommitteeConfigError, match="missing 'page_url'"):
        validate_committees([broken], {1511})


def test_run_records_errors_without_records_when_page_fails(committee):
    def failing_fetcher(url):
        raise RuntimeError("certificate verify failed")

    records, errors = run({"results": [{"public_body_id": 1511}]}, COMMITTEES,
                          Path("."), fetcher=failing_fetcher)
    assert records == []
    assert len(errors) == 1
    assert errors[0]["error_type"] == "PageFetchFailed"
    assert "do not disable" not in errors[0]["error_message"]


def test_run_reports_no_minutes_found(page_html):
    def empty_fetcher(url):
        return "<html><body>nothing</body></html>"

    records, errors = run({"results": [{"public_body_id": 1511}]}, COMMITTEES,
                          Path("."), fetcher=empty_fetcher)
    assert records == []
    assert [e["error_type"] for e in errors] == ["NoMinutesFound"]
