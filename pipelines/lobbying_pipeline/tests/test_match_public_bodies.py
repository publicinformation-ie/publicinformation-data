import json

from steps.match_public_bodies.process import process, STEP_NAME
from lib.body_matching import normalise, MATCH_THRESHOLD
from lib.file_utils import IncrementalWriter


def _candidates(*pairs):
    return [(pid, name, normalise(name)) for pid, name in pairs]


def test_process_matches_known_name(tmp_path):
    candidates = _candidates((1600, "Adoption Authority of Ireland"))
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, STEP_NAME, key_field="lobbyingie_id", force=True)

    input_data = {"lobbyingie_bodies": [
        {"lobbyingie_id": 1600, "lobbyingie_name": "Adoption Authority of Ireland",
         "lobbyingie_url": "https://www.lobbying.ie/app/home/search?publicBodys=1600",
         "lobbyingie_returns_count": 12},
    ]}
    process(input_data, candidates, writer)
    writer.finalize()

    output = json.loads(output_path.read_text())
    assert output["results"][0]["public_body_id"] == 1600


def test_process_leaves_null_for_unmatched_body(tmp_path):
    candidates = _candidates((1600, "Adoption Authority of Ireland"))
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, STEP_NAME, key_field="lobbyingie_id", force=True)

    input_data = {"lobbyingie_bodies": [
        {"lobbyingie_id": 9999, "lobbyingie_name": "Totally Unrelated Entity Ltd",
         "lobbyingie_url": "https://www.lobbying.ie/app/home/search?publicBodys=9999",
         "lobbyingie_returns_count": 1},
    ]}
    process(input_data, candidates, writer)
    writer.finalize()

    output = json.loads(output_path.read_text())
    assert output["results"][0]["public_body_id"] is None


def test_process_does_not_fail_on_unmatched_record(tmp_path):
    candidates = _candidates((1600, "Adoption Authority of Ireland"))
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, STEP_NAME, key_field="lobbyingie_id", force=True)

    input_data = {"lobbyingie_bodies": [
        {"lobbyingie_id": 9999, "lobbyingie_name": "Totally Unrelated Entity Ltd",
         "lobbyingie_url": "https://www.lobbying.ie/app/home/search?publicBodys=9999",
         "lobbyingie_returns_count": 1},
    ]}
    log = process(input_data, candidates, writer)  # must not raise
    assert log[0]["matched_public_body_id"] is None


def test_process_writes_match_log_for_every_record_including_unmatched(tmp_path):
    candidates = _candidates((1600, "Adoption Authority of Ireland"))
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, STEP_NAME, key_field="lobbyingie_id", force=True)

    input_data = {"lobbyingie_bodies": [
        {"lobbyingie_id": 1600, "lobbyingie_name": "Adoption Authority of Ireland",
         "lobbyingie_url": "https://www.lobbying.ie/app/home/search?publicBodys=1600",
         "lobbyingie_returns_count": 12},
        {"lobbyingie_id": 9999, "lobbyingie_name": "Totally Unrelated Entity Ltd",
         "lobbyingie_url": "https://www.lobbying.ie/app/home/search?publicBodys=9999",
         "lobbyingie_returns_count": 1},
    ]}
    log = process(input_data, candidates, writer)

    assert len(log) == 2
    matched = next(l for l in log if l["lobbyingie_id"] == 1600)
    unmatched = next(l for l in log if l["lobbyingie_id"] == 9999)
    assert matched["matched_public_body_id"] == 1600
    assert matched["match_score"] >= MATCH_THRESHOLD
    assert unmatched["matched_public_body_id"] is None
