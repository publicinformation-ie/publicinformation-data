import json
import sys

import pytest

import steps.find_public_bodies.process as proc
from steps.find_public_bodies.process import ingest_bodies, derive_category, main, STEP_NAME


# --- helpers ---

def _hub_record(**kwargs):
    defaults = {
        "public_body_id": 1000,
        "name": "An Post",
        "sector": "S11001",
        "legal_status": "Commercial State Body",
        "government_department": "",
        "nace_code": "H5310",
        "cro": "98788",
        "data_vintage": 2025,
        "official_website_url": "https://anpost.ie/",
        "parent_name": None,
        "parent_id": None,
        "description_for_sub_sector": None,
    }
    defaults.update(kwargs)
    return defaults


def _hub_output(records):
    return {
        "metadata": {"step": "resolve_website_urls", "completed_at": "2026-06-12T00:00:00+00:00"},
        "public_bodies": records,
    }


def write_hub_input(path, records):
    path.write_text(json.dumps(_hub_output(records)))


def run_main(tmp_path, monkeypatch, argv):
    monkeypatch.setattr(proc, "__file__", str(tmp_path / "process.py"))
    sys.argv = argv
    main()


# --- derive_category ---

def test_category_local_authorities_subsector_is_local_authority():
    assert derive_category(_hub_record(description_for_sub_sector="Local Authorities")) == "local authority"


def test_category_default_is_public_body():
    assert derive_category(_hub_record()) == "public body"


def test_category_other_subsector_is_public_body():
    assert derive_category(_hub_record(description_for_sub_sector="Vote")) == "public body"


# --- ingest_bodies ---

def test_ingest_maps_public_body_id():
    result = ingest_bodies([_hub_record(public_body_id=1042)])
    assert result[0]["public_body_id"] == 1042


def test_ingest_maps_name():
    result = ingest_bodies([_hub_record(name="An Post")])
    assert result[0]["name"] == "An Post"


def test_ingest_maps_official_website_url():
    result = ingest_bodies([_hub_record(official_website_url="https://anpost.ie/")])
    assert result[0]["official_website_url"] == "https://anpost.ie/"


def test_ingest_derives_category():
    result = ingest_bodies([_hub_record(description_for_sub_sector="Local Authorities")])
    assert result[0]["category"] == "local authority"


def test_ingest_initialises_all_status_fields_to_not_attempted():
    result = ingest_bodies([_hub_record()])
    s = result[0]["status"]
    assert s["website_url"]["status"] == "not_attempted"
    assert s["foi_page"]["status"] == "not_attempted"
    assert s["foi_email"]["status"] == "not_attempted"
    assert s["disclosures_page"]["status"] == "not_attempted"
    assert s["disclosure_files"]["status"] == "not_attempted"
    assert s["foi_requests"]["status"] == "not_attempted"


def test_ingest_status_website_url_matches_official_website_url():
    result = ingest_bodies([_hub_record(official_website_url="https://example.ie/")])
    assert result[0]["status"]["website_url"]["url"] == "https://example.ie/"


def test_ingest_status_foi_page_url_is_none():
    result = ingest_bodies([_hub_record()])
    assert result[0]["status"]["foi_page"]["url"] is None


def test_ingest_status_disclosure_files_counts_are_zero():
    result = ingest_bodies([_hub_record()])
    df = result[0]["status"]["disclosure_files"]
    assert df["total"] == 0
    assert df["valid"] == 0
    assert df["failed"] == 0


def test_ingest_null_website_url_propagates():
    result = ingest_bodies([_hub_record(official_website_url=None)])
    assert result[0]["official_website_url"] is None
    assert result[0]["status"]["website_url"]["url"] is None


def test_ingest_preserves_all_records():
    records = [_hub_record(public_body_id=i) for i in range(1000, 1005)]
    result = ingest_bodies(records)
    assert len(result) == 5


def test_ingest_result_has_no_cso_only_fields():
    result = ingest_bodies([_hub_record()])
    for key in ("sector", "legal_status", "nace_code", "cro", "data_vintage", "parent_name", "parent_id"):
        assert key not in result[0], f"CSO-only field '{key}' should not appear in FOI output"


# --- main() integration ---

def test_main_writes_output_from_hub_json(tmp_path, monkeypatch):
    inp = tmp_path / "input.json"
    out = tmp_path / "output.json"
    write_hub_input(inp, [_hub_record(public_body_id=1042, name="An Post")])
    run_main(tmp_path, monkeypatch, ["process.py", "--input", str(inp), "--output", str(out), "--force"])
    result = json.loads(out.read_text())
    assert len(result["public_bodies"]) == 1
    assert result["public_bodies"][0]["name"] == "An Post"
    assert result["metadata"]["step"] == STEP_NAME


def test_main_skips_if_output_exists_without_force(tmp_path, monkeypatch):
    inp = tmp_path / "input.json"
    out = tmp_path / "output.json"
    write_hub_input(inp, [_hub_record()])
    out.write_text(json.dumps({"metadata": {}, "public_bodies": [{"sentinel": True}]}))
    monkeypatch.setattr(proc, "__file__", str(tmp_path / "process.py"))
    sys.argv = ["process.py", "--input", str(inp), "--output", str(out)]
    try:
        main()
    except SystemExit as e:
        assert e.code == 0
    result = json.loads(out.read_text())
    assert result["public_bodies"][0].get("sentinel") is True


def test_main_public_body_scoping_confirms_existing(tmp_path, monkeypatch):
    inp = tmp_path / "input.json"
    out = tmp_path / "output.json"
    write_hub_input(inp, [_hub_record(public_body_id=1042)])
    out.write_text(json.dumps({
        "metadata": {"step": STEP_NAME},
        "public_bodies": [_hub_record(public_body_id=1042)],
    }))
    monkeypatch.setattr(proc, "__file__", str(tmp_path / "process.py"))
    sys.argv = ["process.py", "--input", str(inp), "--output", str(out), "--public-body", "1042"]
    try:
        main()
    except SystemExit as e:
        assert e.code == 0
    result = json.loads(out.read_text())
    assert result["public_bodies"][0]["public_body_id"] == 1042


def test_main_public_body_scoping_errors_if_not_found(tmp_path, monkeypatch):
    inp = tmp_path / "input.json"
    out = tmp_path / "output.json"
    write_hub_input(inp, [_hub_record(public_body_id=1042)])
    out.write_text(json.dumps({
        "metadata": {"step": STEP_NAME},
        "public_bodies": [_hub_record(public_body_id=1042)],
    }))
    monkeypatch.setattr(proc, "__file__", str(tmp_path / "process.py"))
    sys.argv = ["process.py", "--input", str(inp), "--output", str(out), "--public-body", "9999"]
    try:
        main()
        assert False, "Expected SystemExit"
    except SystemExit as e:
        assert e.code != 0
