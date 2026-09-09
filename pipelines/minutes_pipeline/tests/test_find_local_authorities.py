import json
from pathlib import Path
from unittest import mock

import pytest

from steps.find_local_authorities.process import (
    STEP_NAME,
    load_committed_authorities,
    join_with_cso,
    process,
)
from lib.file_utils import read_json


def _cso_output(records):
    return {"metadata": {}, "public_bodies": records}


def _cso_record(bid, name, url):
    return {
        "public_body_id": bid, "name": name, "official_website_url": url,
        "legal_entity_type": "Agency", "sector": "S13",
    }


def test_load_committed_authorities_reads_local_authorities_json(tmp_path):
    auth_path = tmp_path / "local_authorities.json"
    auth_path.write_text(json.dumps([
        {"name": "Meath County Council", "slug": "meath",
         "municipal_districts": ["Navan"]},
        {"name": "Carlow County Council", "slug": "carlow", "municipal_districts": []},
    ]))
    loaded = load_committed_authorities(auth_path)
    assert loaded[0]["slug"] == "meath"
    assert loaded[1]["municipal_districts"] == []


def test_join_with_cso_matches_by_name():
    authorities = [
        {"name": "Meath County Council", "slug": "meath", "municipal_districts": ["Navan"]},
        {"name": "Carlow County Council", "slug": "carlow", "municipal_districts": []},
    ]
    cso = _cso_output([
        _cso_record(1511, "Meath County Council", "https://www.meath.ie/"),
        _cso_record(1002, "Carlow County Council", "https://www.carlow.ie/"),
        _cso_record(9999, "Dublin City Council Culture Company CLG", "https://www.example.ie/"),
    ])
    records, unmatched = join_with_cso(authorities, cso)
    assert [r["public_body_id"] for r in records] == [1511, 1002]
    assert records[0]["slug"] == "meath"
    assert records[0]["official_website_url"] == "https://www.meath.ie/"
    assert records[0]["municipal_districts"] == ["Navan"]
    # The near-miss "council" name is NOT selected — name-list drives selection.
    assert unmatched == []


def test_join_with_cso_reports_unmatched_committed_name():
    authorities = [
        {"name": "Meath County Council", "slug": "meath", "municipal_districts": []},
        {"name": "Nonexistent County Council", "slug": "ghost", "municipal_districts": []},
    ]
    cso = _cso_output([_cso_record(1511, "Meath County Council", "https://www.meath.ie/")])
    records, unmatched = join_with_cso(authorities, cso)
    assert len(records) == 1
    assert unmatched == ["Nonexistent County Council"]


def test_process_fatal_on_unmatched_committed_name(tmp_path, make_writer):
    authorities = [
        {"name": "Meath County Council", "slug": "meath", "municipal_districts": []},
        {"name": "Ghost County Council", "slug": "ghost", "municipal_districts": []},
    ]
    auth_path = tmp_path / "local_authorities.json"
    auth_path.write_text(json.dumps(authorities))
    cso = _cso_output([_cso_record(1511, "Meath County Council", "https://www.meath.ie/")])
    writer = make_writer(STEP_NAME)

    with pytest.raises(SystemExit) as exc:
        process(cso, auth_path, writer, step_dir=tmp_path)
    assert exc.value.code != 0
    errors = read_json(tmp_path / "errors.json")
    assert any("Ghost County Council" in e["error_message"] for e in errors)


def test_process_writes_all_authorities(tmp_path, make_writer):
    authorities = [
        {"name": "Meath County Council", "slug": "meath", "municipal_districts": ["Navan"]},
        {"name": "Carlow County Council", "slug": "carlow", "municipal_districts": []},
    ]
    auth_path = tmp_path / "local_authorities.json"
    auth_path.write_text(json.dumps(authorities))
    cso = _cso_output([
        _cso_record(1511, "Meath County Council", "https://www.meath.ie/"),
        _cso_record(1002, "Carlow County Council", "https://www.carlow.ie/"),
    ])
    writer = make_writer(STEP_NAME)
    process(cso, auth_path, writer, step_dir=tmp_path)
    writer.finalize()
    results = read_json(tmp_path / "output.json")["results"]
    assert len(results) == 2
    assert {r["public_body_id"] for r in results} == {1511, 1002}
