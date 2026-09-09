import json
from pathlib import Path
from unittest import mock

import pytest

from steps.extract_motions.process import (
    STEP_NAME,
    build_user_prompt,
    extract_one,
    process,
    resolve_meeting_date,
)
from lib.file_utils import read_json


def _doc(motions=None, text="…minutes text…"):
    d = {
        "public_body_id": 1511, "municipal_district": "Navan",
        "file_url": "https://x.ie/m.pdf", "meeting_date": "2024-07-08",
        "text": text,
    }
    if motions is not None:
        d["motions"] = motions
    return d


def test_extract_one_parses_motions():
    payload = {"motions": [
        {"motion_text": "That the council…", "proposer": "Cllr A",
         "seconder": "Cllr B", "status_label": "carried"}
    ]}
    with mock.patch("steps.extract_motions.process.extract_json",
                    return_value=payload):
        record = extract_one(_doc())
    assert record["motions"] == payload["motions"]


def test_extract_one_none_on_bad_json():
    with mock.patch("steps.extract_motions.process.extract_json",
                    return_value=None):
        record = extract_one(_doc())
    assert record["motions"] is None


def test_resolve_meeting_date_keeps_link_derived_when_present():
    assert resolve_meeting_date("2024-07-08", None) == "2024-07-08"


def test_resolve_meeting_date_falls_back_to_content_when_link_missing():
    assert resolve_meeting_date(None, "2025-06-10") == "2025-06-10"


def test_resolve_meeting_date_parses_day_month_year_content():
    assert resolve_meeting_date(None, "10 June 2025") == "2025-06-10"


def test_resolve_meeting_date_null_when_undeterminable():
    assert resolve_meeting_date(None, None) is None
    # Month-only content does not give a stable meeting day.
    assert resolve_meeting_date(None, "June 2025") is None
    # Link date wins over a conflicting content date (deterministic > LLM).
    assert resolve_meeting_date("2024-07-08", "2025-06-10") == "2024-07-08"


def test_extract_one_resolves_meeting_date_from_content():
    payload = {"meeting_date": "2025-06-10", "motions": [
        {"motion_text": "That the council…", "proposer": "Cllr A",
         "seconder": "Cllr B", "status_label": "carried"}
    ]}
    doc = _doc()
    doc["meeting_date"] = None
    with mock.patch("steps.extract_motions.process.extract_json",
                    return_value=payload):
        record = extract_one(doc)
    assert record["meeting_date"] == "2025-06-10"
    assert record["motions"] == payload["motions"]


def test_extract_one_keeps_link_date_even_when_content_conflicts():
    payload = {"meeting_date": "2025-06-10", "motions": []}
    with mock.patch("steps.extract_motions.process.extract_json",
                    return_value=payload):
        record = extract_one(_doc())  # link date 2024-07-08
    assert record["meeting_date"] == "2024-07-08"
