import json

from steps.match_public_bodies.process import (
    normalise, best_match, load_candidates, process, STEP_NAME, MATCH_THRESHOLD,
)
from lib.file_utils import IncrementalWriter, write_json


def _candidates(*pairs):
    """Build a candidates list from (public_body_id, name) pairs."""
    return [(pid, name, normalise(name)) for pid, name in pairs]


# ── normalise (must match match_gov_urls's behaviour) ───────────────────────

def test_normalise_strips_clg_suffix():
    assert normalise("Adare Heritage Trust CLG") == "adare heritage trust"


def test_normalise_strips_parenthetical():
    assert normalise("Adoption Authority of Ireland (AAI)") == "adoption authority of ireland"


# ── best_match ────────────────────────────────────────────────────────────

def test_best_match_exact_name_clears_threshold():
    candidates = _candidates((1106, "Central Statistics Office"))
    body_id, score = best_match(normalise("Central Statistics Office"), candidates)
    assert body_id == 1106
    assert score >= MATCH_THRESHOLD


def test_best_match_publicjobs_does_not_clear_threshold():
    """publicjobs vs the real 883-candidate pool tops out well under 0.90 —
    this is exactly the mismatch apply_overrides (Task 3) exists to fix."""
    candidates = _candidates(
        (1594, "Office of Public Works"),
        (1651, "Public Appointments Service"),
    )
    body_id, score = best_match(normalise("publicjobs"), candidates)
    assert body_id is None
    assert score < MATCH_THRESHOLD


def test_best_match_empty_candidates_returns_none():
    body_id, score = best_match(normalise("Anything"), [])
    assert body_id is None
    assert score == 0.0


# ── load_candidates ──────────────────────────────────────────────────────

def test_load_candidates_reads_results_key(tmp_path):
    path = tmp_path / "candidates.json"
    write_json(path, {"results": [{"public_body_id": 1106, "name": "Central Statistics Office"}]})
    candidates = load_candidates(path)
    assert candidates == [(1106, "Central Statistics Office", "central statistics office")]


# ── process() ────────────────────────────────────────────────────────────

def test_process_matches_exact_name(tmp_path):
    candidates = _candidates((1106, "Central Statistics Office"))
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, STEP_NAME, key_field="wdw_slug", force=True)

    input_data = {"wdw_bodies": [
        {"wdw_name": "Central Statistics Office",
         "wdw_url": "https://www.gov.ie/en/central-statistics-office/organisation-information/central-statistics-office-who-does-what/",
         "wdw_slug": "central-statistics-office"},
    ]}
    process(input_data, candidates, writer)
    writer.finalize()

    output = json.loads(output_path.read_text())
    assert output["results"][0]["public_body_id"] == 1106


def test_process_leaves_null_for_below_threshold_match(tmp_path):
    candidates = _candidates((1594, "Office of Public Works"))
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, STEP_NAME, key_field="wdw_slug", force=True)

    input_data = {"wdw_bodies": [
        {"wdw_name": "publicjobs",
         "wdw_url": "https://www.gov.ie/en/publicjobs/organisation-information/publicjobs-who-does-what/",
         "wdw_slug": "publicjobs"},
    ]}
    process(input_data, candidates, writer)
    writer.finalize()

    output = json.loads(output_path.read_text())
    assert output["results"][0]["public_body_id"] is None


def test_process_writes_match_log_with_score(tmp_path):
    candidates = _candidates((1106, "Central Statistics Office"))
    output_path = tmp_path / "output.json"
    writer = IncrementalWriter(output_path, STEP_NAME, key_field="wdw_slug", force=True)

    input_data = {"wdw_bodies": [
        {"wdw_name": "Central Statistics Office",
         "wdw_url": "https://www.gov.ie/en/central-statistics-office/organisation-information/central-statistics-office-who-does-what/",
         "wdw_slug": "central-statistics-office"},
    ]}
    log = process(input_data, candidates, writer)

    assert log[0]["wdw_slug"] == "central-statistics-office"
    assert log[0]["matched_public_body_id"] == 1106
    assert log[0]["match_score"] >= MATCH_THRESHOLD
