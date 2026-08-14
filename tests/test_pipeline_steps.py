from src.lib.pipeline_steps import (
    STEP_NAMES,
    STEP_CONFIG,
    get_step_path,
    load_json,
)


def test_step_names_ordered():
    assert STEP_NAMES[0] == "transform_disclosure_files"
    assert STEP_NAMES[-1] == "extract_disclosures_deduplicate"
    assert len(STEP_NAMES) == 10


def test_step_config_keys_match_step_names():
    assert set(STEP_CONFIG.keys()) == set(STEP_NAMES)


def test_get_step_path_output(tmp_path, monkeypatch):
    import src.lib.pipeline_steps as ps
    monkeypatch.setattr(ps, "STEPS_DIR", tmp_path)
    p = get_step_path("transform_disclosure_files", "output")
    assert p == tmp_path / "transform_disclosure_files" / "output.json"


def test_load_json_missing_returns_none(tmp_path):
    result = load_json(tmp_path / "nonexistent.json")
    assert result is None


def test_load_json_malformed_returns_none(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json")
    assert load_json(bad) is None


def test_load_json_valid(tmp_path):
    import json
    f = tmp_path / "data.json"
    f.write_text(json.dumps({"key": "value"}))
    assert load_json(f) == {"key": "value"}
