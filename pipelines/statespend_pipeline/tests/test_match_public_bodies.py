from steps.match_public_bodies.process import (
    entity_type_flag, process,
)


def cand(pid, name):
    from lib.body_matching import normalise
    return (pid, name, normalise(name))


def test_entity_type_flag_local_authority():
    assert entity_type_flag("local_authority", "Dublin City Council") is None
    assert "Council" in entity_type_flag("local_authority", "HSE")


def test_entity_type_flag_department():
    assert entity_type_flag("department", "Department of Health") is None
    flag = entity_type_flag("department", "Office of Public Works")
    assert "Department" in flag


def test_entity_type_flag_etb():
    assert entity_type_flag("etb", "Cork Education and Training Board") is None
    flag = entity_type_flag("etb", "Cork ETB Ltd")
    assert "Education and Training Board" in flag


def test_entity_type_flag_passes_unknown_types_through():
    # agency / section_38 have no rule yet; None entity_type is fine too
    assert entity_type_flag("agency", "Anything At All") is None
    assert entity_type_flag("section_38", "Beaumont Hospital") is None
    assert entity_type_flag(None, "Whatever") is None


def test_process_matches_writes_log_and_enriches_canonical_name(make_writer):
    candidates = [cand(1, "Health Service Executive"), cand(2, "Dublin City Council")]
    attrs = {1: "Health Service Executive", 2: "Dublin City Council"}
    input_data = {"results": [
        {"statespend_id": 52, "statespend_name": "Health Service Executive",
         "statespend_entity_type": "agency", "statespend_url": "https://statespend.ie/body/52"},
        {"statespend_id": 189, "statespend_name": "Dublin City Council",
         "statespend_entity_type": "local_authority", "statespend_url": "https://statespend.ie/body/189"},
    ]}
    writer = make_writer("match_public_bodies")
    log = process(input_data, candidates, attrs, writer)
    assert len(log) == 2
    by_sid = {e["statespend_id"]: e for e in log}
    assert by_sid[52]["matched_public_body_id"] == 1
    assert by_sid[52]["match_score"] >= 0.90
    assert by_sid[52]["matched_canonical_name"] == "Health Service Executive"
    assert "entity_type_flag" not in by_sid[52]
    assert writer.results[0]["public_body_id"] == 1


def test_process_flags_entity_type_mismatch_into_log_not_fatal(make_writer):
    candidates = [cand(1, "Office of Public Works")]
    attrs = {1: "Office of Public Works"}
    input_data = {"results": [
        {"statespend_id": 108, "statespend_name": "Office of Public Works",
         "statespend_entity_type": "local_authority", "statespend_url": "x"},
    ]}
    writer = make_writer("match_public_bodies")
    log = process(input_data, candidates, attrs, writer)
    assert log[0]["matched_public_body_id"] == 1
    assert "entity_type_flag" in log[0]


def test_process_records_unresolved_with_score(make_writer):
    from lib.body_matching import normalise
    candidates = [cand(1, "Completely Different Thing")]
    input_data = {"results": [
        {"statespend_id": 999, "statespend_name": "No Such Body Anywhere",
         "statespend_entity_type": "agency", "statespend_url": "x"},
    ]}
    writer = make_writer("match_public_bodies")
    log = process(input_data, candidates, attrs := {1: "Completely Different Thing"}, writer)
    assert log[0]["matched_public_body_id"] is None
    assert log[0]["match_score"] < 0.90
    assert writer.results[0]["public_body_id"] is None
