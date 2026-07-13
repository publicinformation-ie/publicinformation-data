from pathlib import Path

from src.lib.dataset_publish import render_jsonld, render_csv, stamp_if_changed


def test_render_jsonld_produces_utf8_indented_bytes():
    data = {"@graph": [{"name": "Áras an Uachtaráin"}]}
    result = render_jsonld(data)
    assert isinstance(result, bytes)
    assert result.decode("utf-8") == (
        '{\n  "@graph": [\n    {\n      "name": "Áras an Uachtaráin"\n    }\n  ]\n}'
    )


def test_render_csv_produces_header_and_rows():
    result = render_csv(["id", "name"], [{"id": "1", "name": "A"}, {"id": "2", "name": "B"}])
    assert result == b"id,name\r\n1,A\r\n2,B\r\n"


def test_render_csv_empty_rows_still_writes_header():
    result = render_csv(["id", "name"], [])
    assert result == b"id,name\r\n"


def _write_ttl(path, modified_date):
    path.write_text(
        "@prefix dct: <http://purl.org/dc/terms/> .\n"
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
        "<https://example.ie/dataset/x>\n"
        "    a dcat:Dataset ;\n"
        f'    dct:modified "{modified_date}"^^xsd:date ;\n'
        '    owl:versionInfo "1.0.0" ;\n'
        "    .\n"
    )


def test_stamp_if_changed_writes_files_and_updates_ttl_when_content_differs(tmp_path):
    ttl_path = tmp_path / "dataset.ttl"
    _write_ttl(ttl_path, "2020-01-01")
    jsonld_path = tmp_path / "out.jsonld"
    csv_path = tmp_path / "out.csv"
    jsonld_path.write_bytes(b'{"old": true}')
    csv_path.write_bytes(b"old,csv\r\n")

    generated = {jsonld_path: b'{"new": true}', csv_path: b"new,csv\r\n"}
    changed = stamp_if_changed(ttl_path, [jsonld_path, csv_path], generated)

    assert changed is True
    assert jsonld_path.read_bytes() == b'{"new": true}'
    assert csv_path.read_bytes() == b"new,csv\r\n"
    ttl_text = ttl_path.read_text()
    assert '"2020-01-01"' not in ttl_text
    assert 'owl:versionInfo "1.0.0"' in ttl_text  # untouched


def test_stamp_if_changed_is_noop_when_content_identical(tmp_path):
    ttl_path = tmp_path / "dataset.ttl"
    _write_ttl(ttl_path, "2020-01-01")
    jsonld_path = tmp_path / "out.jsonld"
    csv_path = tmp_path / "out.csv"
    jsonld_path.write_bytes(b'{"same": true}')
    csv_path.write_bytes(b"same,csv\r\n")

    generated = {jsonld_path: b'{"same": true}', csv_path: b"same,csv\r\n"}
    changed = stamp_if_changed(ttl_path, [jsonld_path, csv_path], generated)

    assert changed is False
    assert jsonld_path.read_bytes() == b'{"same": true}'
    assert csv_path.read_bytes() == b"same,csv\r\n"
    assert '"2020-01-01"' in ttl_path.read_text()


def test_stamp_if_changed_treats_missing_payload_file_as_changed(tmp_path):
    ttl_path = tmp_path / "dataset.ttl"
    _write_ttl(ttl_path, "2020-01-01")
    jsonld_path = tmp_path / "out.jsonld"  # does not exist yet
    csv_path = tmp_path / "out.csv"
    csv_path.write_bytes(b"a,b\r\n")

    generated = {jsonld_path: b'{"first": true}', csv_path: b"a,b\r\n"}
    changed = stamp_if_changed(ttl_path, [jsonld_path, csv_path], generated)

    assert changed is True
    assert jsonld_path.read_bytes() == b'{"first": true}'
    assert '"2020-01-01"' not in ttl_path.read_text()
