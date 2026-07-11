import json

from steps.match_public_bodies.process import process, STEP_NAME
from lib.body_matching import normalise, MATCH_THRESHOLD
from lib.file_utils import IncrementalWriter


def _candidates(*pairs):
    return [(pid, name, normalise(name)) for pid, name in pairs]


def test_process_matches_known_name(tmp_path):
    candidates = _candidates((1106, "Central Statistics Office"))
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, STEP_NAME, key_field="datagovie_slug", force=True)

    input_data = {"datagovie_orgs": [
        {"datagovie_slug": "central-statistics-office",
         "datagovie_name": "Central Statistics Office",
         "datagovie_url": "https://data.gov.ie/organization/central-statistics-office",
         "datagovie_package_count": 5},
    ]}
    process(input_data, candidates, writer)
    writer.finalize()

    output = json.loads(output_path.read_text())
    assert output["results"][0]["public_body_id"] == 1106


def test_process_leaves_null_for_unmatched_organisation(tmp_path):
    candidates = _candidates((1106, "Central Statistics Office"))
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, STEP_NAME, key_field="datagovie_slug", force=True)

    input_data = {"datagovie_orgs": [
        {"datagovie_slug": "3d", "datagovie_name": "3d",
         "datagovie_url": "https://data.gov.ie/organization/3d",
         "datagovie_package_count": 1},
    ]}
    process(input_data, candidates, writer)
    writer.finalize()

    output = json.loads(output_path.read_text())
    assert output["results"][0]["public_body_id"] is None


def test_process_does_not_fail_on_unmatched_record(tmp_path):
    candidates = _candidates((1106, "Central Statistics Office"))
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, STEP_NAME, key_field="datagovie_slug", force=True)

    input_data = {"datagovie_orgs": [
        {"datagovie_slug": "3d", "datagovie_name": "3d",
         "datagovie_url": "https://data.gov.ie/organization/3d",
         "datagovie_package_count": 1},
    ]}
    log = process(input_data, candidates, writer)  # must not raise
    assert log[0]["matched_public_body_id"] is None


def test_process_writes_match_log_for_every_record_including_unmatched(tmp_path):
    candidates = _candidates((1106, "Central Statistics Office"))
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, STEP_NAME, key_field="datagovie_slug", force=True)

    input_data = {"datagovie_orgs": [
        {"datagovie_slug": "central-statistics-office", "datagovie_name": "Central Statistics Office",
         "datagovie_url": "https://data.gov.ie/organization/central-statistics-office",
         "datagovie_package_count": 5},
        {"datagovie_slug": "3d", "datagovie_name": "3d",
         "datagovie_url": "https://data.gov.ie/organization/3d",
         "datagovie_package_count": 1},
    ]}
    log = process(input_data, candidates, writer)

    assert len(log) == 2
    matched = next(l for l in log if l["datagovie_slug"] == "central-statistics-office")
    unmatched = next(l for l in log if l["datagovie_slug"] == "3d")
    assert matched["matched_public_body_id"] == 1106
    assert matched["match_score"] >= MATCH_THRESHOLD
    assert unmatched["matched_public_body_id"] is None
