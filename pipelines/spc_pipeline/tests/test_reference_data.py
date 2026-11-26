import json
import re
from pathlib import Path

PIPELINE = Path(__file__).resolve().parents[1]
REPO = PIPELINE.parents[1]
COFOG = PIPELINE / "reference" / "cofog_1999.json"
SUBDOMAINS = PIPELINE / "reference" / "transport_subdomains.json"
VOCABULARY = REPO / ".claude" / "skills" / "transport-governance" / "vocabulary.md"


def _cofog():
    return json.loads(COFOG.read_text())


def test_cofog_has_ten_divisions():
    data = _cofog()
    divisions = [code for code in data["codes"] if code["level"] == "division"]
    assert len(divisions) == 10
    assert {code["code"] for code in divisions} == {
        f"{number:02d}" for number in range(1, 11)
    }


def test_cofog_named_codes_and_descriptions():
    by_code = {code["code"]: code for code in _cofog()["codes"]}
    assert by_code["04.5"]["description"] == "Transport"
    assert by_code["04.5.1"]["description"] == "Road transport"
    assert by_code["05.4.0"]["description"] == "Protection of biodiversity and landscape"
    assert by_code["06.4.0"]["description"] == "Street lighting"


def test_every_cofog_parent_exists():
    data = _cofog()
    known = {code["code"] for code in data["codes"]}
    for code in data["codes"]:
        if code["parent"] is not None:
            assert code["parent"] in known, code["code"]
            assert code["level"] != "division"


def test_cofog_metadata_records_provenance():
    metadata = _cofog()["metadata"]
    assert metadata["source_url"].endswith("COFOG_english_structure.txt")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", metadata["retrieved_date"])
    assert re.fullmatch(r"[0-9a-f]{64}", metadata["sha256"])
    assert metadata["byte_size"] > 0


def _vocabulary_subdomain_ids() -> set[str]:
    text = VOCABULARY.read_text(encoding="utf-8")
    section = text.split("## Subdomains", 1)[1].split("\n## ", 1)[0]
    ids = set()
    for line in section.splitlines():
        match = re.match(r"\|\s*([a-z]+/[a-z-]+)\s*\|", line)
        if match:
            ids.add(match.group(1))
    return ids


def test_subdomain_ids_match_the_governance_vocabulary():
    if not VOCABULARY.exists():
        import pytest

        pytest.skip("the transport-governance vocabulary is not present")
    data = json.loads(SUBDOMAINS.read_text())
    assert {entry["id"] for entry in data["subdomains"]} == _vocabulary_subdomain_ids()


def test_subdomains_have_terms_and_plain_labels():
    for entry in json.loads(SUBDOMAINS.read_text())["subdomains"]:
        assert entry["id"]
        assert entry["term"]
        assert entry["plain_label"]
