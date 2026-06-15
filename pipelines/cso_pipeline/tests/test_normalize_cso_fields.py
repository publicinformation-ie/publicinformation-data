import sys

from steps.normalize_cso_fields.process import (
    parse_legal_status,
    parse_nace_code,
    normalize_bodies,
    STEP_NAME,
)

# ── legal_status: all 10 known values ──

def test_commercial_financial_corporation_dept():
    fields, err = parse_legal_status(
        "Commercial Financial Corporation under the aegis of Department"
    )
    assert fields == {
        "is_commercial": True, "is_financial": True,
        "aegis": "Department", "legal_entity_type": "Corporation",
    }
    assert err is False


def test_commercial_non_financial_corporation_dept():
    fields, err = parse_legal_status(
        "Commercial Non-Financial Corporation under the aegis of Department"
    )
    assert fields == {
        "is_commercial": True, "is_financial": False,
        "aegis": "Department", "legal_entity_type": "Corporation",
    }
    assert err is False


def test_commercial_non_financial_corporation_local_gov():
    fields, err = parse_legal_status(
        "Commercial Non-Financial Corporation under the aegis of Local Government"
    )
    assert fields == {
        "is_commercial": True, "is_financial": False,
        "aegis": "Local Government", "legal_entity_type": "Corporation",
    }
    assert err is False


def test_non_commercial_agency_central_gov():
    fields, err = parse_legal_status(
        "Non-Commercial Agency under the aegis of Central Government"
    )
    assert fields == {
        "is_commercial": False, "is_financial": None,
        "aegis": "Central Government", "legal_entity_type": "Agency",
    }
    assert err is False


def test_non_commercial_agency_dept():
    fields, err = parse_legal_status(
        "Non-Commercial Agency under the aegis of Department"
    )
    assert fields == {
        "is_commercial": False, "is_financial": None,
        "aegis": "Department", "legal_entity_type": "Agency",
    }
    assert err is False


def test_non_commercial_agency_local_gov():
    fields, err = parse_legal_status(
        "Non-Commercial Agency under the aegis of Local Government"
    )
    assert fields == {
        "is_commercial": False, "is_financial": None,
        "aegis": "Local Government", "legal_entity_type": "Agency",
    }
    assert err is False


def test_extra_budgetary_fund():
    fields, err = parse_legal_status("Extra-Budgetary Fund")
    assert fields == {
        "is_commercial": None, "is_financial": None,
        "aegis": None, "legal_entity_type": "Extra-Budgetary Fund",
    }
    assert err is False


def test_social_security_fund():
    fields, err = parse_legal_status("Social Security Fund")
    assert fields == {
        "is_commercial": None, "is_financial": None,
        "aegis": None, "legal_entity_type": "Social Security Fund",
    }
    assert err is False


def test_vote():
    fields, err = parse_legal_status("Vote")
    assert fields == {
        "is_commercial": None, "is_financial": None,
        "aegis": None, "legal_entity_type": "Vote",
    }
    assert err is False


def test_vote_46():
    fields, err = parse_legal_status("Vote 46")
    assert fields == {
        "is_commercial": None, "is_financial": None,
        "aegis": None, "legal_entity_type": "Vote",
    }
    assert err is False


def test_unrecognised_legal_status_returns_null_fields_and_error_flag():
    fields, err = parse_legal_status("Unknown Status")
    assert fields == {
        "is_commercial": None, "is_financial": None,
        "aegis": None, "legal_entity_type": None,
    }
    assert err is True


def test_null_legal_status_returns_null_fields_no_error():
    fields, err = parse_legal_status(None)
    assert fields == {
        "is_commercial": None, "is_financial": None,
        "aegis": None, "legal_entity_type": None,
    }
    assert err is False


# ── NACE: structural field extraction ──

_SAMPLE_LOOKUP = {
    "sections": {"F": "Construction", "A": "Agriculture, forestry and fishing"},
    "classes": {"4110": "Development of building projects", "0210": "Silviculture and other forestry activities"},
}


def test_nace_structural_fields_extracted():
    fields, err = parse_nace_code("F4110", _SAMPLE_LOOKUP)
    assert fields["nace_section"] == "F"
    assert fields["nace_division"] == "41"
    assert fields["nace_group"] == "411"
    assert fields["nace_class"] == "4110"
    assert err is False


def test_nace_section_name_resolved():
    fields, _ = parse_nace_code("F4110", _SAMPLE_LOOKUP)
    assert fields["nace_section_name"] == "Construction"


def test_nace_class_name_resolved():
    fields, _ = parse_nace_code("F4110", _SAMPLE_LOOKUP)
    assert fields["nace_class_name"] == "Development of building projects"


def test_nace_unknown_section_gives_null_section_name():
    fields, err = parse_nace_code("Z9999", _SAMPLE_LOOKUP)
    assert fields["nace_section"] == "Z"
    assert fields["nace_class"] == "9999"
    assert fields["nace_section_name"] is None
    assert fields["nace_class_name"] is None
    assert err is False


def test_nace_unknown_class_gives_null_class_name():
    fields, err = parse_nace_code("F9999", _SAMPLE_LOOKUP)
    assert fields["nace_section_name"] == "Construction"
    assert fields["nace_class_name"] is None
    assert err is False


def test_null_nace_code_returns_null_fields_no_error():
    fields, err = parse_nace_code(None, _SAMPLE_LOOKUP)
    assert all(v is None for v in fields.values())
    assert err is False


def test_malformed_nace_wrong_length_returns_null_and_error():
    fields, err = parse_nace_code("F41", _SAMPLE_LOOKUP)
    assert all(v is None for v in fields.values())
    assert err is True


def test_malformed_nace_no_letter_prefix_returns_null_and_error():
    fields, err = parse_nace_code("14110", _SAMPLE_LOOKUP)
    assert all(v is None for v in fields.values())
    assert err is True


# ── normalize_bodies integration ──

def _make_body(legal_status, nace_code, body_id=1):
    return {
        "public_body_id": body_id,
        "name": "Test Body",
        "legal_status": legal_status,
        "nace_code": nace_code,
    }


def test_normalize_bodies_adds_10_fields():
    bodies = [_make_body("Commercial Financial Corporation under the aegis of Department", "F4110")]
    enriched, errors = normalize_bodies(bodies, _SAMPLE_LOOKUP)
    r = enriched[0]
    assert r["is_commercial"] is True
    assert r["nace_section"] == "F"
    assert len(errors) == 0


def test_normalize_bodies_unrecognised_legal_status_logs_error():
    bodies = [_make_body("Unknown Status", "F4110")]
    enriched, errors = normalize_bodies(bodies, _SAMPLE_LOOKUP)
    assert enriched[0]["is_commercial"] is None
    assert len(errors) == 1
    assert errors[0]["error_type"] == "UnrecognisedLegalStatus"


def test_normalize_bodies_malformed_nace_logs_error():
    bodies = [_make_body("Vote", "BAD")]
    enriched, errors = normalize_bodies(bodies, _SAMPLE_LOOKUP)
    assert enriched[0]["nace_section"] is None
    assert len(errors) == 1
    assert errors[0]["error_type"] == "MalformedNaceCode"


def test_normalize_bodies_null_inputs_no_errors():
    bodies = [_make_body(None, None)]
    enriched, errors = normalize_bodies(bodies, _SAMPLE_LOOKUP)
    assert enriched[0]["is_commercial"] is None
    assert enriched[0]["nace_section"] is None
    assert len(errors) == 0


# ── main() integration: file I/O ──

def _write_input(path, bodies):
    import json
    path.write_text(json.dumps({
        "metadata": {"step": "parse_cso_bodies"},
        "public_bodies": bodies,
    }))


def _write_lookup(path, lookup):
    import json
    path.write_text(json.dumps(lookup))


def test_main_writes_output_and_no_errors_for_valid_input(tmp_path):
    import json
    from steps.normalize_cso_fields import process as proc_mod

    step_dir = tmp_path / "normalize_cso_fields"
    step_dir.mkdir()
    _write_lookup(step_dir / "nace_lookup.json", _SAMPLE_LOOKUP)
    input_path = tmp_path / "input.json"
    _write_input(input_path, [_make_body(
        "Commercial Financial Corporation under the aegis of Department", "F4110"
    )])
    output_path = step_dir / "output.json"

    sys.argv = ["process.py", "--input", str(input_path), "--output", str(output_path), "--force"]
    proc_mod.main(step_dir=step_dir)

    output = json.loads(output_path.read_text())
    assert output["metadata"]["step"] == STEP_NAME
    assert len(output["public_bodies"]) == 1
    assert output["public_bodies"][0]["is_commercial"] is True
    errors = json.loads((step_dir / "errors.json").read_text())
    assert errors == []


def test_main_logs_errors_for_unrecognised_values(tmp_path):
    import json
    from steps.normalize_cso_fields import process as proc_mod

    step_dir = tmp_path / "normalize_cso_fields"
    step_dir.mkdir()
    _write_lookup(step_dir / "nace_lookup.json", _SAMPLE_LOOKUP)
    input_path = tmp_path / "input.json"
    _write_input(input_path, [_make_body("Unknown Status", "BADINPUT")])
    output_path = step_dir / "output.json"

    sys.argv = ["process.py", "--input", str(input_path), "--output", str(output_path), "--force"]
    proc_mod.main(step_dir=step_dir)

    errors = json.loads((step_dir / "errors.json").read_text())
    error_types = {e["error_type"] for e in errors}
    assert "UnrecognisedLegalStatus" in error_types
    assert "MalformedNaceCode" in error_types


def test_main_skips_if_output_exists(tmp_path, capsys):
    from steps.normalize_cso_fields import process as proc_mod

    step_dir = tmp_path / "normalize_cso_fields"
    step_dir.mkdir()
    output_path = step_dir / "output.json"
    output_path.write_text("{}")

    sys.argv = ["process.py", "--input", str(tmp_path / "unused.json"), "--output", str(output_path)]
    proc_mod.main(step_dir=step_dir)
    assert "skipping" in capsys.readouterr().out
