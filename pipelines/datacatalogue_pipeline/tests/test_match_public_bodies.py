import json

from steps.match_public_bodies.process import process, STEP_NAME
from lib.body_matching import normalise, MATCH_THRESHOLD
from lib.file_utils import IncrementalWriter


def _candidates(*pairs):
    return [(pid, name, normalise(name)) for pid, name in pairs]


def test_process_matches_known_name(tmp_path):
    candidates = _candidates((1106, "Central Statistics Office"))
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, STEP_NAME, key_field="datacatalogue_slug", force=True)

    input_data = {"datacatalogue_orgs": [
        {"datacatalogue_slug": "central-statistics-office",
         "datacatalogue_name": "Central Statistics Office",
         "datacatalogue_url": "https://datacatalogue.gov.ie/organization/central-statistics-office",
         "datacatalogue_package_count": 5},
    ]}
    process(input_data, candidates, writer)
    writer.finalize()

    output = json.loads(output_path.read_text())
    assert output["results"][0]["public_body_id"] == 1106


def test_process_leaves_null_for_unmatched_organisation(tmp_path):
    candidates = _candidates((1106, "Central Statistics Office"))
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, STEP_NAME, key_field="datacatalogue_slug", force=True)

    input_data = {"datacatalogue_orgs": [
        {"datacatalogue_slug": "3d", "datacatalogue_name": "3d",
         "datacatalogue_url": "https://datacatalogue.gov.ie/organization/3d",
         "datacatalogue_package_count": 1},
    ]}
    process(input_data, candidates, writer)
    writer.finalize()

    output = json.loads(output_path.read_text())
    assert output["results"][0]["public_body_id"] is None


def test_process_does_not_fail_on_unmatched_record(tmp_path):
    candidates = _candidates((1106, "Central Statistics Office"))
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, STEP_NAME, key_field="datacatalogue_slug", force=True)

    input_data = {"datacatalogue_orgs": [
        {"datacatalogue_slug": "3d", "datacatalogue_name": "3d",
         "datacatalogue_url": "https://datacatalogue.gov.ie/organization/3d",
         "datacatalogue_package_count": 1},
    ]}
    log = process(input_data, candidates, writer)  # must not raise
    assert log[0]["matched_public_body_id"] is None


def test_process_writes_match_log_for_every_record_including_unmatched(tmp_path):
    candidates = _candidates((1106, "Central Statistics Office"))
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, STEP_NAME, key_field="datacatalogue_slug", force=True)

    input_data = {"datacatalogue_orgs": [
        {"datacatalogue_slug": "central-statistics-office", "datacatalogue_name": "Central Statistics Office",
         "datacatalogue_url": "https://datacatalogue.gov.ie/organization/central-statistics-office",
         "datacatalogue_package_count": 5},
        {"datacatalogue_slug": "3d", "datacatalogue_name": "3d",
         "datacatalogue_url": "https://datacatalogue.gov.ie/organization/3d",
         "datacatalogue_package_count": 1},
    ]}
    log = process(input_data, candidates, writer)

    assert len(log) == 2
    matched = next(l for l in log if l["datacatalogue_slug"] == "central-statistics-office")
    unmatched = next(l for l in log if l["datacatalogue_slug"] == "3d")
    assert matched["matched_public_body_id"] == 1106
    assert matched["match_score"] >= MATCH_THRESHOLD
    assert unmatched["matched_public_body_id"] is None


def _org_rec(slug, name):
    return {"datacatalogue_slug": slug, "datacatalogue_name": name,
            "datacatalogue_url": f"https://datacatalogue.gov.ie/organization/{slug}"}


def test_process_leaves_null_for_near_miss_below_threshold(tmp_path):
    candidates = _candidates((1106, "Central Statistics Office"))
    writer = IncrementalWriter(tmp_path / "output.json", STEP_NAME,
                               key_field="datacatalogue_slug", force=True)
    log = process({"datacatalogue_orgs": [_org_rec("cso-ireland", "Central Statistics Bureau of Ireland")]},
                  candidates, writer)
    assert log[0]["matched_public_body_id"] is None
    assert 0 < log[0]["match_score"] < MATCH_THRESHOLD


def test_process_resumes_and_skips_already_processed_slugs(tmp_path):
    candidates = _candidates((1106, "Central Statistics Office"), (1608, "Revenue Commissioners"))
    output_path = tmp_path / "output.json"
    input_data = {"datacatalogue_orgs": [
        _org_rec("central-statistics-office", "Central Statistics Office"),
        _org_rec("revenue-commissioners", "Revenue Commissioners"),
    ]}

    first = IncrementalWriter(output_path, STEP_NAME, key_field="datacatalogue_slug", force=True)
    process({"datacatalogue_orgs": input_data["datacatalogue_orgs"][:1]}, candidates, first)
    first.finalize()

    second = IncrementalWriter(output_path, STEP_NAME, key_field="datacatalogue_slug", force=False)
    assert second.processed_keys == {"central-statistics-office"}
    log = process(input_data, candidates, second)
    second.finalize()

    assert [l["datacatalogue_slug"] for l in log] == ["revenue-commissioners"]
    slugs = [r["datacatalogue_slug"] for r in json.loads(output_path.read_text())["results"]]
    assert sorted(slugs) == ["central-statistics-office", "revenue-commissioners"]
