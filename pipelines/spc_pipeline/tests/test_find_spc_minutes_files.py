from pathlib import Path

import pytest

from steps.find_spc_minutes_files.discovery import (
    CommitteeConfigError,
    discover_page,
    extract_pdf_links,
    KNOWN_LAYOUTS,
    committee_pages,
    encode_url,
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


def _committee(committee_id):
    return next(c for c in load_committees(COMMITTEES) if c["committee_id"] == committee_id)


def _page(name):
    return (Path(__file__).parent / "fixtures" / name).read_text(encoding="utf-8")


KILDARE = "kildare/transport-mobility-open-spaces"
WESTMETH = "westmeath/planning-regeneration-transportation"


@pytest.fixture(scope="module")
def page_html():
    return PAGE_FIXTURE.read_text(encoding="utf-8")


def test_committed_page_yields_exactly_six_minutes_links(committee, page_html):
    records = discover_page(committee, page_html)[0]
    assert len(records) == 6
    assert not [r for r in records if "agenda" in r["file_url"].lower()]
    assert not [r for r in records if "agenda" in r["link_text"].lower()]


def test_discovered_links_are_absolute_and_carry_link_text(committee, page_html):
    for record in discover_page(committee, page_html)[0]:
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
    records = discover_page(committee, html)[0]
    assert len(records) == 1


def test_agenda_link_is_ignored(committee):
    html = (
        '<a href="/files/February%202026%20-%20Agenda%20-%20SPC.pdf">'
        "February 2026 - Agenda - SPC</a>"
    )
    assert discover_page(committee, html)[0] == []


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
                          Path("."), fetcher=failing_fetcher, public_body=1511)
    assert records == []
    assert len(errors) == 1
    assert errors[0]["error_type"] == "PageFetchFailed"
    assert "do not disable" not in errors[0]["error_message"]


def test_run_reports_no_minutes_found(page_html):
    def empty_fetcher(url):
        return "<html><body>nothing</body></html>"

    records, errors = run({"results": [{"public_body_id": 1511}]}, COMMITTEES,
                          Path("."), fetcher=empty_fetcher, public_body=1511)
    assert records == []
    assert [e["error_type"] for e in errors] == ["NoMinutesFound"]


def test_shipped_committees_are_exactly_the_three_declared():
    assert [c["committee_id"] for c in load_committees(COMMITTEES)] == [
        "meath/transportation-urban-regeneration", KILDARE, WESTMETH]


def test_every_shipped_committee_names_a_known_layout():
    assert {c["layout"] for c in load_committees(COMMITTEES)} <= KNOWN_LAYOUTS


def test_meath_keeps_its_single_page_url(committee):
    assert isinstance(committee["page_url"], str)
    assert committee_pages(committee) == [committee["page_url"]]


def test_published_name_is_the_one_printed_on_the_minutes_not_the_web_page_name():
    kildare = _committee(KILDARE)
    assert kildare["name"] == "Transport, Mobility and Open Spaces Strategic Policy Committee"
    assert kildare["site_name"] == "Transportation, Safety and Emergency Services"


def test_minutes_spread_over_several_pages_are_all_collected_with_their_page():
    kildare = _committee(KILDARE)
    pages = committee_pages(kildare)
    assert len(pages) == 2
    seen: set[str] = set()
    found = []
    for url, fixture in zip(pages, ("kildare-spc-page-2025.html", "kildare-spc-page-2026.html")):
        records, errors = discover_page(kildare, _page(fixture), url, seen)
        assert errors == []
        found.extend(records)
    assert len(found) == 6
    assert {r["page_url"] for r in found} == set(pages)
    assert [r["page_url"] for r in found][:4] == [pages[0]] * 4


def test_file_name_with_spaces_is_percent_encoded_once():
    kildare = _committee(KILDARE)
    records, _ = discover_page(
        kildare, _page("kildare-spc-page-2026.html"), committee_pages(kildare)[1])
    urls = [r["file_url"] for r in records]
    assert ("https://kildarecoco.ie/YourCouncil/YourElectedCouncil/Committees/"
            "StrategicPolicyCommittees/TransportationSafetyandEmergencyServices/2026/Minutes/"
            "Minutes%20Transport%20Mobility%20and%20Open%20Spaces%20SPC%20050226.pdf") in urls
    assert not any(" " in u or "%2520" in u for u in urls)


def test_encode_url_leaves_an_encoded_url_unchanged():
    url = "https://x.ie/a/File%20Name.pdf"
    assert encode_url(url) == url
    assert encode_url("https://x.ie/a/File Name.pdf") == url


def test_year_window_skips_older_westmeath_minutes():
    westmeath = _committee(WESTMETH)
    records, errors = discover_page(westmeath, _page("westmeath-spc-page.html"))
    assert errors == []
    assert [r["link_text"] for r in records] == [
        "Minutes of SPC Meeting 6th March 2026",
        "Minutes of SPC Meeting 28th Nov 2025",
        "Minutes of SPC Meeting 19th Sept 2025",
        "Minutes of SPC Meeting 13th February 2025",
        "Minutes of SPC Meeting 23rd May 2025",
    ]


def test_without_a_year_window_every_minutes_link_is_collected():
    westmeath = {k: v for k, v in _committee(WESTMETH).items() if k != "years"}
    records, _ = discover_page(westmeath, _page("westmeath-spc-page.html"))
    assert len(records) == 36


def test_undated_link_under_a_year_window_is_an_error_and_not_collected():
    westmeath = _committee(WESTMETH)
    html = (
        '<a href="/en/media/a.pdf">Minutes of SPC Meeting 6th March 2026</a>'
        '<a href="/en/media/MinutesSPC2026.pdf">Minutes of the latest SPC Meeting</a>'
    )
    records, errors = discover_page(westmeath, html)
    assert [r["link_text"] for r in records] == ["Minutes of SPC Meeting 6th March 2026"]
    assert [e["error_type"] for e in errors] == ["UndatedMinutesLink"]
    assert "MinutesSPC2026.pdf" in errors[0]["error_message"]


def test_a_link_text_with_two_different_years_is_not_dated():
    westmeath = _committee(WESTMETH)
    html = '<a href="/en/media/a.pdf">Minutes of SPC Meeting 2025 held in 2026</a>'
    records, errors = discover_page(westmeath, html)
    assert records == []
    assert [e["error_type"] for e in errors] == ["UndatedMinutesLink"]


def test_unknown_layout_is_fatal(committee):
    with pytest.raises(CommitteeConfigError, match="unknown layout 'made-up'"):
        validate_committees([{**committee, "layout": "made-up"}], {1511})


def test_a_committee_must_declare_a_layout(committee):
    broken = {k: v for k, v in committee.items() if k != "layout"}
    with pytest.raises(CommitteeConfigError, match="missing 'layout'"):
        validate_committees([broken], {1511})


def test_page_url_and_page_urls_together_are_fatal(committee):
    with pytest.raises(CommitteeConfigError, match="both page_url and page_urls"):
        validate_committees([{**committee, "page_urls": ["https://x.ie/"]}], {1511})


def test_bad_years_are_fatal(committee):
    for years in ([], ["2025"], 2025):
        with pytest.raises(CommitteeConfigError, match="years"):
            validate_committees([{**committee, "years": years}], {1511})


def test_run_collects_every_declared_committee_with_the_shipped_list():
    pages = {
        **{u: _page(f) for u, f in zip(
            committee_pages(_committee(KILDARE)),
            ("kildare-spc-page-2025.html", "kildare-spc-page-2026.html"))},
        committee_pages(_committee(WESTMETH))[0]: _page("westmeath-spc-page.html"),
        committee_pages(_committee("meath/transportation-urban-regeneration"))[0]:
            PAGE_FIXTURE.read_text(encoding="utf-8"),
    }
    records, errors = run({"results": [{"public_body_id": i} for i in (1511, 1456, 1870)]},
                          COMMITTEES, Path("."), fetcher=pages.__getitem__)
    assert errors == []
    assert len(records) == 6 + 6 + 5
    assert {r["committee_id"] for r in records} == {c["committee_id"] for c in load_committees(COMMITTEES)}


@pytest.mark.parametrize("body", [
    "<html><script>sucuri_cloudproxy_js=''</script></html>",
    "<html><title>Just a moment...</title><script src='/cdn-cgi/challenge-platform/h/b'></script></html>",
])
def test_a_challenge_page_is_a_fetch_failure_with_no_bypass(body):
    calls = []

    def fetcher(url):
        calls.append(url)
        return body

    records, errors = run({"results": [{"public_body_id": 1456}]}, COMMITTEES, Path("."),
                          fetcher=fetcher, public_body=1456)
    assert records == []
    assert [e["error_type"] for e in errors] == ["PageFetchFailed", "PageFetchFailed"]
    assert all("does not solve or bypass" in e["error_message"] for e in errors)
    assert len(calls) == 2                      # one plain request per page, no retries


def test_an_http_403_is_a_fetch_failure():
    def fetcher(url):
        raise RuntimeError("403 Client Error: Forbidden")

    records, errors = run({"results": [{"public_body_id": 1870}]}, COMMITTEES, Path("."),
                          fetcher=fetcher, public_body=1870)
    assert records == []
    assert [e["error_type"] for e in errors] == ["PageFetchFailed"]
    assert "403" in errors[0]["error_message"]
