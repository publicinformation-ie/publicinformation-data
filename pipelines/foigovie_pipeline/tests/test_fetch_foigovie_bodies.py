import pytest

from steps.fetch_foigovie_bodies.process import (
    DIRECTORY_URL, slug_from_url, parse_directory, parse_detail, fetch_directory,
)


DIRECTORY_HTML = """
<html><body><ul>
  <li><a href="https://foi.gov.ie/foi_units/adoption-authority-of-ireland/">Adoption Authority Of Ireland</a></li>
  <li><a href="https://foi.gov.ie/foi_units/an-garda-siochana/">An Garda Siochana</a></li>
  <li><a href="https://foi.gov.ie/about/">About FOI</a></li>
  <li><a href="https://foi.gov.ie/foi_units/adoption-authority-of-ireland/">Adoption Authority Of Ireland</a></li>
</ul></body></html>
"""

DETAIL_HTML_FULL = """
<html><body><table><tbody>
  <tr><td width="90px"><strong>Organisation:</strong></td><td>Adoption Authority Of Ireland</td></tr>
  <tr><td><strong>Address:</strong></td><td>Shelbourne House, Shelbourne Road, Ballsbridge, Dublin ,4</td></tr>
  <tr><td><strong>Name:</strong></td><td>Eamon Conlon</td></tr>
  <tr><td><strong>Telephone:</strong></td><td>01 2309319</td></tr>
  <tr><td><strong>Email:</strong></td><td><a href="mailto:corporate@aai.gov.ie">corporate@aai.gov.ie</a></td></tr>
  <tr><td><strong>Web Address:</strong></td><td><a href="http://www.aai.gov.ie" target="_blank">www.aai.gov.ie</a></td></tr>
  <tr><td><strong>Network:</strong></td><td>n/a</td></tr>
</tbody></table></body></html>
"""

# Real shape of An Garda Siochana's page: unpublished fields are the literal
# string "n/a", not an omitted row.
DETAIL_HTML_NA = """
<html><body><table><tbody>
  <tr><td><strong>Organisation:</strong></td><td>An Garda Siochana</td></tr>
  <tr><td><strong>Address:</strong></td><td>Athlumney House, Navan, Co. Meath</td></tr>
  <tr><td><strong>Name:</strong></td><td>Paul Bassett</td></tr>
  <tr><td><strong>Telephone:</strong></td><td>n/a</td></tr>
  <tr><td><strong>Email:</strong></td><td><a href="mailto:FOI@garda.ie">FOI@garda.ie</a></td></tr>
  <tr><td><strong>Web Address:</strong></td><td>n/a</td></tr>
  <tr><td><strong>Network:</strong></td><td>n/a</td></tr>
</tbody></table></body></html>
"""


# ── slug_from_url ────────────────────────────────────────────────────────

def test_slug_from_url_takes_the_detail_path_segment():
    assert slug_from_url("https://foi.gov.ie/foi_units/adoption-authority-of-ireland/") \
        == "adoption-authority-of-ireland"


def test_slug_from_url_tolerates_missing_trailing_slash():
    assert slug_from_url("https://foi.gov.ie/foi_units/an-garda-siochana") == "an-garda-siochana"


def test_slug_from_url_returns_none_for_a_non_detail_url():
    assert slug_from_url("https://foi.gov.ie/about/") is None


# ── parse_directory ──────────────────────────────────────────────────────

def test_parse_directory_extracts_slug_name_and_url():
    entries = parse_directory(DIRECTORY_HTML)
    assert entries[0] == {
        "foigovie_slug": "adoption-authority-of-ireland",
        "foigovie_name": "Adoption Authority Of Ireland",
        "foigovie_url": "https://foi.gov.ie/foi_units/adoption-authority-of-ireland/",
    }


def test_parse_directory_ignores_non_detail_links():
    slugs = [e["foigovie_slug"] for e in parse_directory(DIRECTORY_HTML)]
    assert "about" not in slugs


def test_parse_directory_deduplicates_repeated_slugs():
    slugs = [e["foigovie_slug"] for e in parse_directory(DIRECTORY_HTML)]
    assert slugs == ["adoption-authority-of-ireland", "an-garda-siochana"]


# ── parse_detail ─────────────────────────────────────────────────────────

def test_parse_detail_extracts_every_field():
    assert parse_detail(DETAIL_HTML_FULL) == {
        "foigovie_address": "Shelbourne House, Shelbourne Road, Ballsbridge, Dublin ,4",
        "foigovie_officer_name": "Eamon Conlon",
        "foigovie_phone": "01 2309319",
        "foigovie_email": "corporate@aai.gov.ie",
        "foigovie_website": "www.aai.gov.ie",
    }


def test_parse_detail_maps_the_na_sentinel_to_none():
    """foi.gov.ie writes a literal "n/a" rather than omitting the row. Publishing
    that string as a phone number would be a silent data-quality defect."""
    fields = parse_detail(DETAIL_HTML_NA)
    assert fields["foigovie_phone"] is None
    assert fields["foigovie_website"] is None
    assert fields["foigovie_email"] == "FOI@garda.ie"


def test_parse_detail_ignores_the_network_and_organisation_labels():
    fields = parse_detail(DETAIL_HTML_FULL)
    assert set(fields) == {
        "foigovie_address", "foigovie_officer_name", "foigovie_phone",
        "foigovie_email", "foigovie_website",
    }


def test_parse_detail_returns_all_none_for_a_table_less_page():
    assert parse_detail("<html><body><p>Nothing here</p></body></html>") == {
        "foigovie_address": None,
        "foigovie_officer_name": None,
        "foigovie_phone": None,
        "foigovie_email": None,
        "foigovie_website": None,
    }


# ── fetch_directory ──────────────────────────────────────────────────────

def test_fetch_directory_returns_entries_on_success(requests_mock):
    requests_mock.get(DIRECTORY_URL, text=DIRECTORY_HTML)
    entries = fetch_directory()
    assert {e["foigovie_slug"] for e in entries} == {
        "adoption-authority-of-ireland", "an-garda-siochana",
    }


def test_fetch_directory_fatal_exits_on_zero_parsed_bodies(requests_mock):
    requests_mock.get(DIRECTORY_URL, text="<html><body>no links</body></html>")
    with pytest.raises(SystemExit) as exc:
        fetch_directory()
    assert exc.value.code != 0


def test_fetch_directory_fatal_exits_on_http_error(requests_mock):
    requests_mock.get(DIRECTORY_URL, status_code=500, text="server error")
    with pytest.raises(SystemExit):
        fetch_directory()


def test_fetch_directory_fatal_exits_on_request_failure(requests_mock):
    import requests as req
    requests_mock.get(DIRECTORY_URL, exc=req.exceptions.ConnectionError("refused"))
    with pytest.raises(SystemExit):
        fetch_directory()


# ── process (resumability + per-page error isolation) ────────────────────

def test_process_writes_one_merged_record_per_entry(tmp_path, make_writer, requests_mock):
    from steps.fetch_foigovie_bodies.process import process
    requests_mock.get(
        "https://foi.gov.ie/foi_units/adoption-authority-of-ireland/", text=DETAIL_HTML_FULL)
    writer = make_writer("fetch_foigovie_bodies")
    entries = [{
        "foigovie_slug": "adoption-authority-of-ireland",
        "foigovie_name": "Adoption Authority Of Ireland",
        "foigovie_url": "https://foi.gov.ie/foi_units/adoption-authority-of-ireland/",
    }]
    process(entries, tmp_path, writer)
    writer.finalize()
    import json
    results = json.loads((tmp_path / "output.json").read_text())["results"]
    assert len(results) == 1
    assert results[0]["foigovie_name"] == "Adoption Authority Of Ireland"
    assert results[0]["foigovie_email"] == "corporate@aai.gov.ie"


def test_process_skips_already_processed_slugs(tmp_path, make_writer, requests_mock):
    from steps.fetch_foigovie_bodies.process import process
    adapter = requests_mock.get(
        "https://foi.gov.ie/foi_units/adoption-authority-of-ireland/", text=DETAIL_HTML_FULL)
    writer = make_writer("fetch_foigovie_bodies")
    writer.append([{"foigovie_slug": "adoption-authority-of-ireland"}])
    entries = [{
        "foigovie_slug": "adoption-authority-of-ireland",
        "foigovie_name": "Adoption Authority Of Ireland",
        "foigovie_url": "https://foi.gov.ie/foi_units/adoption-authority-of-ireland/",
    }]
    process(entries, tmp_path, writer)
    assert adapter.call_count == 0


def test_process_logs_an_error_and_continues_when_one_detail_page_fails(
        tmp_path, make_writer, requests_mock):
    import json
    from steps.fetch_foigovie_bodies.process import process
    requests_mock.get("https://foi.gov.ie/foi_units/broken/", status_code=500, text="boom")
    requests_mock.get(
        "https://foi.gov.ie/foi_units/adoption-authority-of-ireland/", text=DETAIL_HTML_FULL)
    writer = make_writer("fetch_foigovie_bodies")
    entries = [
        {"foigovie_slug": "broken", "foigovie_name": "Broken",
         "foigovie_url": "https://foi.gov.ie/foi_units/broken/"},
        {"foigovie_slug": "adoption-authority-of-ireland",
         "foigovie_name": "Adoption Authority Of Ireland",
         "foigovie_url": "https://foi.gov.ie/foi_units/adoption-authority-of-ireland/"},
    ]
    process(entries, tmp_path, writer)
    writer.finalize()
    results = json.loads((tmp_path / "output.json").read_text())["results"]
    assert [r["foigovie_slug"] for r in results] == ["adoption-authority-of-ireland"]
    errors = json.loads((tmp_path / "errors.json").read_text())
    assert len(errors) == 1
    assert errors[0]["context"]["foigovie_slug"] == "broken"
