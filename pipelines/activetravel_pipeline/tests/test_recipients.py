"""Recipient attribution from the section heading and the project-code prefix."""
import pytest

from allocations import load_code_prefixes, load_recipient_aliases
from conftest import rows_from_pages
from steps.classify_grant_rows.process import run as classify_run
from steps.normalize_grant_amounts.process import run as normalize_run
from steps.segment_funding_streams.process import run as segment_run
from steps.resolve_recipients.process import (
    load_public_body_register, load_slug_seed, resolve, run as resolve_run,
)


def test_heading_and_prefix_agree():
    aliases, prefixes = load_recipient_aliases(), load_code_prefixes()
    recipient, error, detail = resolve("Wicklow County Council", "WCC/25/0003", aliases, prefixes)
    assert error is None
    assert recipient["canonical"] == "Wicklow County Council"
    assert detail == "heading+prefix"


def test_a_heading_that_disagrees_with_the_prefix_is_a_conflict():
    aliases, prefixes = load_recipient_aliases(), load_code_prefixes()
    recipient, error, detail = resolve("Carlow County Council", "DCC/25/0001", aliases, prefixes)
    assert recipient is None
    assert error == "RecipientConflict"
    assert "Carlow" in detail and "DCC" in detail


def test_a_2022_row_with_no_heading_is_attributed_from_its_prefix():
    "A row that arrives before its heading is attributed by code prefix, never by position."
    aliases, prefixes = load_recipient_aliases(), load_code_prefixes()
    recipient, error, detail = resolve(None, "CW/21/0001", aliases, prefixes)
    assert error is None
    assert recipient["canonical"] == "Carlow County Council"
    assert detail == "prefix_only"


def test_an_ambiguous_prefix_cannot_attribute_a_heading_less_row():
    aliases, prefixes = load_recipient_aliases(), load_code_prefixes()
    recipient, error, detail = resolve(None, "LCC/22/xxxx", aliases, prefixes)
    assert recipient is None
    assert error == "RecipientUnresolved"
    assert "2 recipients" in detail


def test_lcc_on_a_louth_row_is_not_a_conflict():
    "The committed map records that Louth's provisional 2022 codes are printed LCC."
    aliases, prefixes = load_recipient_aliases(), load_code_prefixes()
    recipient, error, _ = resolve("Louth County Council", "LCC/22/xxxx", aliases, prefixes)
    assert error is None
    assert recipient["canonical"] == "Louth County Council"


def test_an_undeclared_prefix_withholds_the_row():
    aliases, prefixes = load_recipient_aliases(), load_code_prefixes()
    recipient, error, detail = resolve("Carlow County Council", "ZZ/25/0001", aliases, prefixes)
    assert recipient is None
    assert error == "RecipientUnresolved"
    assert "ZZ" in detail


def test_an_invented_authority_withholds_the_row():
    aliases, prefixes = load_recipient_aliases(), load_code_prefixes()
    recipient, error, _ = resolve("Atlantis City Council", "AAA/25/0001", aliases, prefixes)
    assert recipient is None
    assert error == "RecipientUnresolved"


def _run_chain(real_pages, document_id: str, year: int, pages: list[int]):
    rows, _ = rows_from_pages(real_pages, document_id, year, pages)
    classified, _ = classify_run({"rows": rows})
    normalized, _ = normalize_run({"rows": classified["rows"]}, repairs=[])
    segmented, _ = segment_run({"rows": normalized["rows"]})
    return segmented


def test_a_heading_less_section_is_attributed_from_the_registry_prefix(real_pages):
    "2024 Fingal's table has no title and no heading anywhere in the PDF."
    segmented = _run_chain(real_pages, "nta-active-travel-2024", 2024, [6, 7])
    output, errors = resolve_run({**segmented, "documents": []})
    assert errors == []
    section = output["sections"][0]
    assert section["recipient_name"] == "Fingal County Council"
    assert section["resolution"] == "prefix_only"
    assert section["public_body_id"] == load_public_body_register()["fingal county council"]
    assert {row["recipient_name"] for row in output["rows"]
            if row.get("section_id") == section["section_id"]} == {"Fingal County Council"}


def test_a_local_authority_record_carries_its_public_body(real_pages):
    segmented = _run_chain(real_pages, "nta-active-travel-2026", 2026, [21, 22, 23])
    output, _ = resolve_run({**segmented, "documents": []})
    row = next(row for row in output["rows"] if row.get("section_id"))
    assert row["public_body"] == "https://data.publicinformation.ie/body/wicklow-county-council"
    assert row["public_body_id"] == load_public_body_register()["wicklow county council"]


def test_the_non_local_authority_block_has_no_body_and_is_all_active_travel(real_pages):
    segmented = _run_chain(real_pages, "nta-active-travel-2026", 2026, [78, 79])
    output, errors = resolve_run({**segmented, "documents": []})
    section = output["sections"][0]
    assert section["recipient_kind"] == "other"
    assert section["public_body_id"] is None
    assert section["stream_rule"] == "non_local_authority_section"
    rows = [row for row in output["rows"] if row.get("section_id") == section["section_id"]]
    assert rows and {row["funding_stream"] for row in rows} == {"active_travel"}
    assert {row["public_body"] for row in rows} == {None}


def test_an_unresolvable_local_authority_aborts_publication(real_pages):
    segmented = _run_chain(real_pages, "nta-active-travel-2026", 2026, [21, 22, 23])
    with pytest.raises(ValueError) as excinfo:
        resolve_run({**segmented, "documents": []}, register={})
    assert "Wicklow County Council" in str(excinfo.value)
    assert "public bodies" in str(excinfo.value).lower()


def test_the_permanent_slug_machinery_is_used_not_a_fresh_slug():
    seed = load_slug_seed()
    register = load_public_body_register()
    body_id = register["dun laoghaire rathdown county council"]
    assert seed[body_id] == "dun-laoghaire-rathdown-county-council"
