from pathlib import Path

from scripts.transform_motions import (
    build_record, publish, transform_to_csv_rows, transform_to_jsonld,
)
from src.lib.body_refs import BASE_URI
from src.lib.dataset_publish import render_csv, render_jsonld


def _motion():
    return {
        "motion_id": "meath/2026-05-20/m001",
        "public_body_id": 1511,
        "public_body_slug": "meath",
        "public_body_name": "Meath County Council",
        "municipal_district": "Navan",
        "meeting_date": "2026-05-20",
        "meeting_type": "municipal_district",
        "source_file_url": "https://www.meath.ie/system/files/media/file-uploads/2026-06/05-2026%20Minutes%20Navan%20MD.pdf",
        "motion_text": "To ask the Executive to approve the construction of a pedestrian crossing on Abbey Road.",
        "proposer": "Eddie Fennessy",
        "seconder": "Francis Deane",
        "status": "not_recorded",
    }


def test_build_record_shape():
    record = build_record(_motion(), {1511: "meath-county-council"})
    assert record == {
        "@id": f"{BASE_URI}/motion/meath/2026-05-20/m001",
        "@type": "mot:Motion",
        "public_body": f"{BASE_URI}/body/meath-county-council",
        "public_body_id": 1511,
        "motion_id": "meath/2026-05-20/m001",
        "municipal_district": "Navan",
        "meeting_date": "2026-05-20",
        "meeting_type": "municipal_district",
        "source_file_url": "https://www.meath.ie/system/files/media/file-uploads/2026-06/05-2026%20Minutes%20Navan%20MD.pdf",
        "motion_text": "To ask the Executive to approve the construction of a pedestrian crossing on Abbey Road.",
        "proposer": "Eddie Fennessy",
        "seconder": "Francis Deane",
        "status": "not_recorded",
    }


def test_build_record_resolves_authoritative_slug_not_motions_own():
    motion = _motion()
    motion["public_body_slug"] = "meath"
    record = build_record(motion, {1511: "meath-county-council"})
    assert record["public_body"] == f"{BASE_URI}/body/meath-county-council"


def test_build_record_omits_null_fields():
    motion = _motion()
    motion["municipal_district"] = None
    motion["proposer"] = None
    record = build_record(motion, {1511: "meath-county-council"})
    assert "municipal_district" not in record
    assert "proposer" not in record
    assert record["status"] == "not_recorded"


def test_build_record_raises_for_unknown_public_body_id():
    try:
        build_record(_motion(), {})
        assert False, "expected ValueError"
    except ValueError as e:
        assert "1511" in str(e)


def test_transform_to_jsonld_wraps_records_in_graph():
    records = [{"@id": f"{BASE_URI}/motion/meath/2026-05-20/m001",
                "@type": "mot:Motion"}]
    doc = transform_to_jsonld(records)
    assert doc["@graph"] == records
    assert doc["@context"]["mot"] == f"{BASE_URI}/ns/motions#"
    assert doc["@context"]["public_body"]["@type"] == "@id"


def test_transform_to_csv_rows_flattens_records():
    records = [build_record(_motion(), {1511: "meath-county-council"})]
    fieldnames, rows = transform_to_csv_rows(records)
    assert fieldnames == [
        "id", "public_body", "public_body_id", "motion_id", "municipal_district",
        "meeting_date", "meeting_type", "source_file_url", "motion_text",
        "proposer", "seconder", "status",
    ]
    assert rows[0]["id"] == records[0]["@id"]
    assert rows[0]["public_body"] == records[0]["public_body"]
    assert rows[0]["motion_id"] == "meath/2026-05-20/m001"


def test_transform_to_csv_rows_null_fields_become_empty_cells():
    motion = _motion()
    motion["municipal_district"] = None
    motion["proposer"] = None
    records = [build_record(motion, {1511: "meath-county-council"})]
    _, rows = transform_to_csv_rows(records)
    assert rows[0]["municipal_district"] == ""
    assert rows[0]["proposer"] == ""


def _ttl_text(modified_date):
    return (
        "@prefix dct: <http://purl.org/dc/terms/> .\n"
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
        "<https://example.ie/dataset/motions>\n"
        "    a dcat:Dataset ;\n"
        f'    dct:modified "{modified_date}"^^xsd:date ;\n'
        '    owl:versionInfo "1.0.0" ;\n'
        "    .\n"
    )


def test_publish_writes_files_and_stamps_ttl_when_content_changed(tmp_path):
    jsonld_path = tmp_path / "motions.jsonld"
    csv_path = tmp_path / "motions.csv"
    ttl_path = tmp_path / "dataset-motions.ttl"
    ttl_path.write_text(_ttl_text("2020-01-01"))
    jsonld_data = {"@graph": [{"motion_id": "old"}]}
    fieldnames, rows = ["id", "motion_id"], [{"id": "1", "motion_id": "old"}]

    changed = publish(
        jsonld_data, fieldnames, rows,
        jsonld_path=jsonld_path, csv_path=csv_path, ttl_path=ttl_path,
    )

    assert changed is True
    assert jsonld_path.read_bytes() == render_jsonld(jsonld_data)
    assert csv_path.read_bytes() == render_csv(fieldnames, rows)
    assert '"2020-01-01"' not in ttl_path.read_text()


def test_publish_is_noop_when_content_identical(tmp_path):
    jsonld_path = tmp_path / "motions.jsonld"
    csv_path = tmp_path / "motions.csv"
    ttl_path = tmp_path / "dataset-motions.ttl"
    ttl_path.write_text(_ttl_text("2020-01-01"))
    jsonld_data = {"@graph": [{"motion_id": "same"}]}
    fieldnames, rows = ["id", "motion_id"], [{"id": "1", "motion_id": "same"}]
    jsonld_path.write_bytes(render_jsonld(jsonld_data))
    csv_path.write_bytes(render_csv(fieldnames, rows))

    changed = publish(
        jsonld_data, fieldnames, rows,
        jsonld_path=jsonld_path, csv_path=csv_path, ttl_path=ttl_path,
    )

    assert changed is False
    assert '"2020-01-01"' in ttl_path.read_text()