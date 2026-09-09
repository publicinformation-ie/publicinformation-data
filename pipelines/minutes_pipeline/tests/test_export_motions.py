import json
from pathlib import Path

import pytest

from steps.export_motions.process import (
    STEP_NAME,
    group_by_authority,
    build_index,
    write_per_authority,
)
from lib.file_utils import read_json


def _motion(slug="meath", bid=1511):
    return {
        "motion_id": f"{slug}/2024-07-08/m001",
        "public_body_id": bid, "public_body_slug": slug,
        "public_body_name": "Meath County Council",
        "municipal_district": "Navan", "meeting_date": "2024-07-08",
        "meeting_type": "municipal_district",
        "source_file_url": "https://x.ie/m.pdf",
        "motion_text": "That the council…", "proposer": "Cllr A",
        "seconder": "Cllr B", "status": "carried",
    }


def test_group_by_authority():
    motions = [_motion("meath"), _motion("carlow", 1002), _motion("meath")]
    grouped = group_by_authority(motions)
    assert set(grouped) == {"meath", "carlow"}
    assert len(grouped["meath"]) == 2
    assert len(grouped["carlow"]) == 1


def test_write_per_authority(tmp_path):
    grouped = {"meath": [_motion("meath")]}
    write_per_authority(grouped, tmp_path)
    out = read_json(tmp_path / "meath.json")
    assert out["public_body_slug"] == "meath"
    assert len(out["motions"]) == 1


def test_build_index():
    idx = build_index({"meath": ["meath/2024-07-08/m001"]})
    assert idx == {"authorities": ["meath"]}
