import json
from pathlib import Path

import pytest

from steps.canonicalize_motions.process import (
    STEP_NAME,
    CANONICAL_STATUSES,
    canonicalize_records,
    map_status,
)
from lib.file_utils import read_json


def _motion_record(status_label="carried", meeting_date="2024-07-08",
                   district="Navan", text="That the council…"):
    return {
        "public_body_id": 1511, "municipal_district": district,
        "meeting_date": meeting_date, "file_url": "https://x.ie/m.pdf",
        "motions": [{"motion_text": text, "proposer": "Cllr A",
                     "seconder": "Cllr B", "status_label": status_label}],
    }


def test_map_status_known():
    assert map_status("carried") == "carried"


def test_map_status_unknown_to_not_recorded():
    assert map_status("passed overwhelmingly") == "not_recorded"


def test_canonicalize_assigns_composite_id_and_status():
    authorities = {"1511": {"slug": "meath", "name": "Meath County Council"}}
    records = [_motion_record()]
    canonical, errors = canonicalize_records(records, authorities, "1511")
    assert len(canonical) == 1
    m = canonical[0]
    assert m["motion_id"] == "meath/2024-07-08/m001"
    assert m["public_body_id"] == 1511
    assert m["public_body_slug"] == "meath"
    assert m["public_body_name"] == "Meath County Council"
    assert m["municipal_district"] == "Navan"
    assert m["meeting_type"] == "municipal_district"
    assert m["source_file_url"] == "https://x.ie/m.pdf"
    assert m["status"] == "carried"
    assert errors == []


def test_canonicalize_unknown_status_errors_and_not_recorded():
    authorities = {"1511": {"slug": "meath", "name": "Meath County Council"}}
    records = [_motion_record(status_label="weird label")]
    canonical, errors = canonicalize_records(records, authorities, "1511")
    assert canonical[0]["status"] == "not_recorded"
    assert any(e["error_type"] == "UnknownStatusLabel" for e in errors)


def test_canonicalize_missing_date_excludes_and_errors():
    authorities = {"1511": {"slug": "meath", "name": "Meath County Council"}}
    records = [_motion_record(meeting_date=None)]
    canonical, errors = canonicalize_records(records, authorities, "1511")
    assert canonical == []
    assert any(e["error_type"] == "MissingMeetingDate" for e in errors)


def test_canonicalize_deduplicates_adjacent_duplicate_text():
    authorities = {"1511": {"slug": "meath", "name": "Meath County Council"}}
    records = [
        _motion_record(text="That the council adopt A"),
        _motion_record(text="That the council adopt A"),
        _motion_record(text="That the council adopt B"),
    ]
    canonical, errors = canonicalize_records(records, authorities, "1511")
    assert [m["motion_text"] for m in canonical] == [
        "That the council adopt A", "That the council adopt B"]
    assert canonical[1]["motion_id"] == "meath/2024-07-08/m002"


def test_canonicalize_sequences_ids_across_documents_same_meeting():
    authorities = {"1511": {"slug": "meath", "name": "Meath County Council"}}
    # Two documents, same (district, date): ids continue across them.
    a = _motion_record(text="Motion one")
    b = _motion_record(text="Motion two")
    canonical, _ = canonicalize_records([a, b], authorities, "1511")
    assert [m["motion_id"] for m in canonical] == [
        "meath/2024-07-08/m001", "meath/2024-07-08/m002"]


def test_canonicalize_meeting_type_council_when_district_null():
    authorities = {"1511": {"slug": "meath", "name": "Meath County Council"}}
    records = [_motion_record(district=None)]
    canonical, _ = canonicalize_records(records, authorities, "1511")
    assert canonical[0]["municipal_district"] is None
    assert canonical[0]["meeting_type"] == "council"
