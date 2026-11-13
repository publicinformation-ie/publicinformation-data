import pytest
from scripts.transform_foi_disclosures import (
    build_record,
    compute_disclosure_id,
    transform_to_jsonld,
    transform_to_csv_rows,
    DATASET_VERSION,
)
from src.lib.body_refs import BASE_URI


# file_url is not unique per record (many disclosure rows share one source
# file), so the published id is derived from the row's stable row_id instead.
SAMPLE_DISCLOSURE = {
    "row_id": "f292642e7af3",
    "public_body_id": 1052,
    "name": "Bord Bia",
    "file_url": "https://www.bordbia.ie/foi-disclosure-log-2019.pdf",
    "file_type": "pdf",
    "foi_reference_id": None,
    "date_received": "2019-01-02",
    "decision_date": "2019-01-15",
    "requester_type": "Journalist",
    "decision_status": "Granted",
    "review_status": None,
    "related_request": None,
    "request_description": "Total amount spent on bottled water in 2017 and 2018.",
    "known_issues": [],
    "missing_columns": ["foi_reference_id", "related_request", "review_status"],
}

EXPECTED_ID = compute_disclosure_id(SAMPLE_DISCLOSURE["row_id"])


def test_build_record_happy_path():
    record = build_record(SAMPLE_DISCLOSURE, {1052: "bord-bia"})
    assert record["@id"] == f"{BASE_URI}/foi-disclosure/{EXPECTED_ID}"
    assert record["@type"] == "foi:FoiDisclosure"
    assert record["public_body"] == f"{BASE_URI}/body/bord-bia"
    assert record["name"] == "Bord Bia"
    assert record["file_url"] == SAMPLE_DISCLOSURE["file_url"]
    assert record["file_type"] == "pdf"
    assert record["known_issues"] == []
    assert record["missing_columns"] == ["foi_reference_id", "related_request", "review_status"]


def test_build_record_omits_null_fields():
    record = build_record(SAMPLE_DISCLOSURE, {1052: "bord-bia"})
    assert "foi_reference_id" not in record
    assert "review_status" not in record
    assert "related_request" not in record
    assert record["decision_date"] == "2019-01-15"
    assert record["requester_type"] == "Journalist"
    assert record["decision_status"] == "Granted"
    assert record["date_received"] == "2019-01-02"
    assert record["request_description"] == SAMPLE_DISCLOSURE["request_description"]


def test_build_record_unknown_public_body_id_raises():
    with pytest.raises(ValueError, match="Unknown public_body_id"):
        build_record(SAMPLE_DISCLOSURE, body_slug_lookup={})


def test_build_record_different_row_id_yields_different_id():
    record_a = build_record(SAMPLE_DISCLOSURE, {1052: "bord-bia"})
    record_b = build_record({**SAMPLE_DISCLOSURE, "row_id": "other"}, {1052: "bord-bia"})
    assert record_a["@id"] != record_b["@id"]


def test_transform_to_jsonld_includes_version_and_graph():
    records = [build_record(SAMPLE_DISCLOSURE, {1052: "bord-bia"})]
    doc = transform_to_jsonld(records)
    assert doc["version"] == DATASET_VERSION
    assert doc["@graph"] == records
    assert doc["@context"]["public_body"] == {"@id": "foi:publicBody", "@type": "@id"}


def test_transform_to_csv_rows_flattens_arrays_with_pipe_delimiter():
    disclosure = dict(SAMPLE_DISCLOSURE)
    disclosure["known_issues"] = ["ocr_low_confidence", "misaligned_row"]
    record = build_record(disclosure, {1052: "bord-bia"})
    fieldnames, rows = transform_to_csv_rows([record])
    row = rows[0]
    assert row["known_issues"] == "ocr_low_confidence|misaligned_row"
    assert row["missing_columns"] == "foi_reference_id|related_request|review_status"


def test_transform_to_csv_rows_empty_string_for_null_fields():
    record = build_record(SAMPLE_DISCLOSURE, {1052: "bord-bia"})
    fieldnames, rows = transform_to_csv_rows([record])
    row = rows[0]
    assert row["foi_reference_id"] == ""
    assert row["review_status"] == ""
    assert row["related_request"] == ""
    assert row["decision_date"] == "2019-01-15"


from pathlib import Path

from scripts.transform_foi_disclosures import publish, CSV_FIELDNAMES
from src.lib.dataset_publish import render_jsonld, render_csv


def test_publish_writes_jsonld_csv_and_xlsx(tmp_path):
    import openpyxl
    jsonld_path = tmp_path / "foi-disclosures.jsonld"
    csv_path = tmp_path / "foi-disclosures.csv"
    xlsx_path = tmp_path / "foi-disclosures.xlsx"
    jsonld_data = {"version": "1.0.0", "@graph": [{"name": "old"}]}
    fieldnames, rows = ["id", "name"], [{"id": "1", "name": "old"}]

    publish(jsonld_data, fieldnames, rows, jsonld_path=jsonld_path, csv_path=csv_path, xlsx_path=xlsx_path)

    assert jsonld_path.read_bytes() == render_jsonld(jsonld_data)
    assert csv_path.read_bytes() == render_csv(fieldnames, rows)
    xlsx_rows = [tuple(r) for r in _xlsx_values(xlsx_path)]
    assert xlsx_rows == [("id", "name"), ("1", "old")]


def test_xlsx_rows_equal_csv_rows_built_from_same_fixture(tmp_path):
    import csv
    import openpyxl
    disclosure = {**SAMPLE_DISCLOSURE, "foi_reference_id": 7, "request_description": "bad\x0bchar, comma"}
    record = build_record(disclosure, {1052: "bord-bia"})
    fieldnames, rows = transform_to_csv_rows([record])
    jsonld_data = transform_to_jsonld([record])
    paths = dict(jsonld_path=tmp_path / "a.jsonld", csv_path=tmp_path / "a.csv", xlsx_path=tmp_path / "a.xlsx")
    publish(jsonld_data, fieldnames, rows, **paths)
    xlsx = [tuple("" if v is None else str(v) for v in r)
            for r in _xlsx_values(paths["xlsx_path"])]
    csv_rows = [tuple(r) for r in csv.reader(open(paths["csv_path"], newline="", encoding="utf-8"))]
    # XLSX (XML 1.0) cannot hold control characters; everything else is equal.
    csv_rows = [tuple(c.replace("\x0b", "") for c in r) for r in csv_rows]
    assert xlsx == csv_rows
    assert xlsx[0] == tuple(CSV_FIELDNAMES)


def test_known_issues_dicts_publish_as_field_names():
    # The pipeline emits {field, issue_type, raw_value} dicts; the published
    # contract is an array of strings naming the uncertain fields.
    disclosure = dict(SAMPLE_DISCLOSURE)
    disclosure["known_issues"] = [
        {"field": "requester_type", "issue_type": "UnrecognizedRequesterType", "raw_value": "x"},
        {"field": "decision_status", "issue_type": "UnrecognizedDecisionStatus", "raw_value": "y"},
        {"field": "requester_type", "issue_type": "Other", "raw_value": "z"},
    ]
    record = build_record(disclosure, {1052: "bord-bia"})
    assert record["known_issues"] == ["requester_type", "decision_status"]
    _, rows = transform_to_csv_rows([record])
    assert rows[0]["known_issues"] == "requester_type|decision_status"


def test_known_issues_dict_without_field_is_an_error():
    import pytest
    disclosure = dict(SAMPLE_DISCLOSURE)
    disclosure["known_issues"] = [{"issue_type": "X"}]
    with pytest.raises(ValueError):
        build_record(disclosure, {1052: "bord-bia"})


def test_xlsx_never_writes_formulas(tmp_path):
    import openpyxl
    from src.lib.dataset_publish import write_xlsx

    payloads = ["=1+1", "+SUM(A1)", "-2+3", "@cmd", '=HYPERLINK("http://x","y")']
    path = tmp_path / "f.xlsx"
    write_xlsx(path, ["name"], [{"name": p} for p in payloads])
    ws = openpyxl.load_workbook(path).active
    assert ws is not None
    cells = [ws.cell(row=i + 2, column=1) for i in range(len(payloads))]
    assert [c.value for c in cells] == payloads
    assert all(c.data_type == "s" for c in cells)


def _xlsx_values(path):
    import openpyxl
    ws = openpyxl.load_workbook(path, read_only=True).active
    assert ws is not None
    return ws.iter_rows(values_only=True)
