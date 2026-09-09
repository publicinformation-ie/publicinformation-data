import json
from pathlib import Path
from unittest import mock

import pytest

from steps.extract_motions.process import (
    STEP_NAME,
    build_user_prompt,
    extract_one,
    process,
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
