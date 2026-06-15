import json
from pathlib import Path

import pytest

_HERE = Path(__file__).parent
_REPO_ROOT = _HERE
while not (_REPO_ROOT / ".git").exists():
    _REPO_ROOT = _REPO_ROOT.parent

_LOOKUP_PATH = _REPO_ROOT / "pipelines" / "cso_pipeline" / "steps" / "normalize_cso_fields" / "nace_lookup.json"
_PARSE_OUTPUT_PATH = _REPO_ROOT / "pipelines" / "cso_pipeline" / "steps" / "parse_cso_bodies" / "output.json"


def _load_lookup():
    return json.loads(_LOOKUP_PATH.read_text(encoding="utf-8"))


def test_nace_lookup_is_valid_json_with_required_keys():
    lookup = _load_lookup()
    assert "sections" in lookup, "nace_lookup.json must have 'sections' key"
    assert "classes" in lookup, "nace_lookup.json must have 'classes' key"


def test_nace_lookup_has_all_21_sections():
    lookup = _load_lookup()
    expected_sections = set("ABCDEFGHIJKLMNOPQRSTU")
    assert expected_sections == set(lookup["sections"].keys())


def test_nace_lookup_section_values_are_nonempty_strings():
    lookup = _load_lookup()
    for letter, name in lookup["sections"].items():
        assert isinstance(name, str) and name, f"Section {letter!r} has empty/null name"


def test_all_cso_nace_codes_resolve_to_nonnull_descriptions():
    """Every NACE code in the live parse_cso_bodies output must have a class description."""
    if not _PARSE_OUTPUT_PATH.exists():
        pytest.skip("parse_cso_bodies/output.json not present — run parse_cso_bodies first")

    lookup = _load_lookup()
    bodies = json.loads(_PARSE_OUTPUT_PATH.read_text(encoding="utf-8"))["public_bodies"]
    nace_codes = sorted(set(b["nace_code"] for b in bodies if b.get("nace_code")))

    missing = [
        code for code in nace_codes
        if lookup["classes"].get(code[1:]) is None
    ]
    assert not missing, (
        f"{len(missing)} CSO NACE code(s) have no class description in nace_lookup.json: {missing}"
    )
