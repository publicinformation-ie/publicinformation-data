import pytest

from src.lib import foi_dataset as fd


def row(body, rid, **kw):
    base = {
        "public_body_id": body, "name": f"Body {body}", "file_url": "https://x/f.csv",
        "file_type": "csv", "foi_reference_id": None, "date_received": "2024-01-02",
        "row_id": rid, "known_issues": [], "missing_columns": [],
    }
    base.update(kw)
    return base


ROWS = [row(2, "b2"), row(1, "a2"), row(1, "a1"), row(2, "b1", date_received="2023-05-01")]


def test_write_is_canonical_and_rerun_is_byte_identical(tmp_path):
    fd.write_parts(ROWS, tmp_path)
    first = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    report = fd.write_parts(list(reversed(ROWS)), tmp_path)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == first
    assert report == {"added": [], "changed": [], "removed": []}
    assert set(first) == {"1.ndjson", "2.ndjson"}
    lines = first["1.ndjson"].decode().split("\n")
    assert lines[-1] == "" and [l[:60] for l in lines[:2]] != []
    assert lines[0].startswith('{"public_body_id":1,"name":"Body 1"')
    assert [__import__("json").loads(l)["row_id"] for l in lines[:-1]] == ["a1", "a2"]
    assert b"\r" not in first["1.ndjson"]
    assert fd.verify_parts(tmp_path) == []


def test_only_touched_bodies_change(tmp_path):
    fd.write_parts(ROWS, tmp_path)
    changed = [r if r["row_id"] != "b1" else {**r, "name": "Renamed"} for r in ROWS]
    assert fd.write_parts(changed, tmp_path) == {"added": [], "changed": [2], "removed": []}


def test_empty_body_file_removed(tmp_path):
    fd.write_parts(ROWS, tmp_path)
    report = fd.write_parts([r for r in ROWS if r["public_body_id"] != 2], tmp_path)
    assert report["removed"] == ["2"]
    assert not (tmp_path / "2.ndjson").exists()


def test_non_canonical_file_fails_verification(tmp_path):
    fd.write_parts(ROWS, tmp_path)
    p = tmp_path / "1.ndjson"
    p.write_text(p.read_text().replace('"file_type":"csv"', '"file_type": "csv"'))
    assert any("not canonical" in m for m in fd.verify_parts(tmp_path))


def test_verify_catches_wrong_body_order_and_cross_file_duplicate(tmp_path):
    fd.write_parts(ROWS, tmp_path)
    (tmp_path / "3.ndjson").write_text(fd.serialise_row(row(1, "a1")) + "\n")
    problems = "\n".join(fd.verify_parts(tmp_path))
    assert "3.ndjson" in problems and "duplicate row_id a1" in problems
    assert "public_body_id" in problems


def test_unicode_line_separators_stay_on_one_line(tmp_path):
    fd.write_parts([row(1, "a1", name="x y z é")], tmp_path)
    data = (tmp_path / "1.ndjson").read_bytes().decode()
    assert len(data.splitlines()) == 1 and data.count("\n") == 1
    assert "é" in data
    assert fd.load_parts(tmp_path)[0]["name"] == "x y z é"


def test_missing_body_id_raises_and_writes_nothing(tmp_path):
    bad = {**row(1, "a1"), "public_body_id": None}
    with pytest.raises(ValueError, match="public_body_id"):
        fd.write_parts([row(2, "b1"), bad], tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_load_parts_orders_numerically_by_body_then_row_id(tmp_path):
    fd.write_parts([row(10, "a"), row(9, "z"), row(9, "b")], tmp_path)
    assert [(r["public_body_id"], r["row_id"]) for r in fd.load_parts(tmp_path)] == [(9, "b"), (9, "z"), (10, "a")]


def test_manifest(tmp_path):
    fd.write_parts(ROWS, tmp_path)
    m = fd.build_manifest(tmp_path, schema_version="1.0.0", commit="abc")
    assert m["total_rows"] == 4 and m["total_bodies"] == 2 and m["build"] is None
    b2 = m["bodies"][1]
    assert b2["row_count"] == 2 and b2["date_received_min"] == "2023-05-01"
    assert b2["url"] == "https://data.publicinformation.ie/latest/foi-disclosures/bodies/2.ndjson"
    import hashlib
    assert b2["sha256"] == hashlib.sha256((tmp_path / "2.ndjson").read_bytes()).hexdigest()
    assert m == fd.build_manifest(tmp_path, schema_version="1.0.0", commit="abc")
