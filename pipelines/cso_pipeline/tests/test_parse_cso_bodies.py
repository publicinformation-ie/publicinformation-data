import csv
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

from steps.parse_cso_bodies.process import parse_rows, normalize, STEP_NAME, CSO_CSV_FILENAME


# --- helpers ---

def _rows(*entities):
    """Build a list of CSV-like row dicts for testing."""
    return [
        {
            "entity_name": e.get("entity_name", ""),
            "controlling_sub_sector": "",
            "sector": e.get("sector", "S11"),
            "legal_status": e.get("legal_status", "State Body"),
            "government_department_or_local_authority": e.get("govt_dept", ""),
            "nace_code": e.get("nace_code", ""),
            "parent": e.get("parent", ""),
            "vote_number": "",
            "cro": e.get("cro", ""),
            "data_vintage": e.get("data_vintage", "2025"),
            "description_for_sub_sector": "",
        }
        for e in entities
    ]


# --- normalize ---

def test_normalize_lowercases_and_strips():
    assert normalize("  An Post  ") == "an post"
    assert normalize("DEPARTMENT OF FINANCE") == "department of finance"


# --- parse_rows: ID assignment ---

def test_stable_ids_first_run_sorted_by_name():
    rows = _rows(
        {"entity_name": "Zebra Corp"},
        {"entity_name": "Alpha Agency"},
        {"entity_name": "Metro Council"},
    )
    records, id_map = parse_rows(rows, {})

    # IDs start at 1000, assigned in normalized alphabetical order
    assert id_map[normalize("Alpha Agency")] == 1000
    assert id_map[normalize("Metro Council")] == 1001
    assert id_map[normalize("Zebra Corp")] == 1002
    assert len(records) == 3


def test_stable_ids_idempotent():
    rows = _rows({"entity_name": "Alpha Agency"}, {"entity_name": "Zebra Corp"})
    _, id_map1 = parse_rows(rows, {})
    _, id_map2 = parse_rows(rows, id_map1)
    assert id_map1 == id_map2


def test_new_entity_appended_with_next_id():
    rows_v1 = _rows({"entity_name": "Alpha Agency"})
    _, id_map = parse_rows(rows_v1, {})  # Alpha gets 1000

    rows_v2 = _rows({"entity_name": "Alpha Agency"}, {"entity_name": "New Body"})
    _, id_map2 = parse_rows(rows_v2, id_map)

    assert id_map2[normalize("Alpha Agency")] == 1000  # unchanged
    assert id_map2[normalize("New Body")] == 1001      # appended


def test_existing_entity_keeps_id_even_if_new_entity_sorts_before():
    """An existing entity must not be renumbered when a new earlier-sorting entity arrives."""
    rows_v1 = _rows({"entity_name": "Zebra Corp"})
    _, id_map = parse_rows(rows_v1, {})  # Zebra gets 1000

    rows_v2 = _rows({"entity_name": "Alpha Agency"}, {"entity_name": "Zebra Corp"})
    _, id_map2 = parse_rows(rows_v2, id_map)

    assert id_map2[normalize("Zebra Corp")] == 1000   # unchanged
    assert id_map2[normalize("Alpha Agency")] == 1001  # new entity gets next


# --- parse_rows: parent resolution ---

def test_parent_id_resolved_within_dataset():
    rows = _rows(
        {"entity_name": "Parent Dept", "parent": ""},
        {"entity_name": "Child Agency", "parent": "Parent Dept"},
    )
    records, _ = parse_rows(rows, {})

    parent = next(r for r in records if r["name"] == "Parent Dept")
    child = next(r for r in records if r["name"] == "Child Agency")

    assert child["parent_name"] == "Parent Dept"
    assert child["parent_id"] == parent["public_body_id"]
    assert parent["parent_id"] is None
    assert parent["parent_name"] is None


def test_parent_id_null_when_parent_not_in_dataset():
    rows = _rows({"entity_name": "Orphan Agency", "parent": "Unknown Parent"})
    records, _ = parse_rows(rows, {})

    assert records[0]["parent_name"] == "Unknown Parent"
    assert records[0]["parent_id"] is None


def test_parent_id_null_when_parent_field_empty():
    rows = _rows({"entity_name": "Solo Body", "parent": ""})
    records, _ = parse_rows(rows, {})

    assert records[0]["parent_name"] is None
    assert records[0]["parent_id"] is None


# --- parse_rows: output shape ---

def test_output_record_has_all_required_fields():
    rows = _rows({
        "entity_name": "An Post",
        "sector": "S11001",
        "legal_status": "Commercial State Body",
        "govt_dept": "Department of Climate",
        "nace_code": "H5310",
        "cro": "98788",
        "data_vintage": "2025",
    })
    records, _ = parse_rows(rows, {})
    r = records[0]

    assert r["public_body_id"] == 1000
    assert r["name"] == "An Post"
    assert r["parent_name"] is None
    assert r["parent_id"] is None
    assert r["sector"] == "S11001"
    assert r["legal_status"] == "Commercial State Body"
    assert r["government_department"] == "Department of Climate"
    assert r["nace_code"] == "H5310"
    assert r["cro"] == "98788"
    assert r["data_vintage"] == 2025        # integer, not string
    assert r["official_website_url"] is None


def test_data_vintage_cast_to_int():
    rows = _rows({"entity_name": "Body A", "data_vintage": "2025"})
    records, _ = parse_rows(rows, {})
    assert records[0]["data_vintage"] == 2025
    assert isinstance(records[0]["data_vintage"], int)


def test_empty_string_fields_become_none():
    rows = _rows({"entity_name": "Body B", "sector": "", "cro": "", "nace_code": ""})
    records, _ = parse_rows(rows, {})
    r = records[0]
    assert r["sector"] is None
    assert r["cro"] is None
    assert r["nace_code"] is None


# --- main() integration: CSV reading and file I/O ---

def _write_csv(path, rows_data):
    fieldnames = [
        "entity_name", "controlling_sub_sector", "sector", "legal_status",
        "government_department_or_local_authority", "nace_code", "parent",
        "vote_number", "cro", "data_vintage", "description_for_sub_sector",
    ]
    with open(path, "w", newline="", encoding="latin-1") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows_data:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def test_main_writes_output_and_id_map(tmp_path):
    csv_path = tmp_path / CSO_CSV_FILENAME
    _write_csv(csv_path, [
        {"entity_name": "An Post", "sector": "S11", "legal_status": "Commercial State Body",
         "data_vintage": "2025", "cro": "98788"},
        {"entity_name": "Aer Lingus", "sector": "S11", "legal_status": "Commercial State Body",
         "data_vintage": "2025", "cro": "12345"},
    ])
    id_map_path = tmp_path / "id_map.json"
    output_path = tmp_path / "output.json"

    sys.argv = [
        "process.py",
        "--input", str(tmp_path),
        "--output", str(output_path),
        "--force",
        "--data-dir", str(tmp_path),
        "--id-map", str(id_map_path),
    ]

    from steps.parse_cso_bodies import process as proc_mod
    proc_mod.main()

    output = json.loads(output_path.read_text())
    assert output["metadata"]["step"] == STEP_NAME
    assert len(output["public_bodies"]) == 2

    id_map = json.loads(id_map_path.read_text())
    # sorted: Aer Lingus (1000), An Post (1001)
    assert id_map[normalize("Aer Lingus")] == 1000
    assert id_map[normalize("An Post")] == 1001


def test_main_skips_if_output_exists(tmp_path, capsys):
    output_path = tmp_path / "output.json"
    output_path.write_text("{}")

    sys.argv = [
        "process.py",
        "--input", str(tmp_path),
        "--output", str(output_path),
        "--data-dir", str(tmp_path),
        "--id-map", str(tmp_path / "id_map.json"),
    ]

    from steps.parse_cso_bodies import process as proc_mod
    proc_mod.main()

    assert "skipping" in capsys.readouterr().out


def test_main_exits_if_csv_missing(tmp_path):
    output_path = tmp_path / "output.json"
    sys.argv = [
        "process.py",
        "--input", str(tmp_path),
        "--output", str(output_path),
        "--force",
        "--data-dir", str(tmp_path),     # no CSV in tmp_path
        "--id-map", str(tmp_path / "id_map.json"),
    ]

    from steps.parse_cso_bodies import process as proc_mod
    with pytest.raises(SystemExit) as exc:
        proc_mod.main()
    assert exc.value.code != 0
