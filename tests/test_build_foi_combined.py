import csv
import json
import re
from pathlib import Path

import openpyxl
import pytest

from scripts.build_foi_combined import build
from src.lib import foi_dataset as fd

REPO = Path(__file__).resolve().parent.parent


def _row(body, rid, **kw):
    r = {
        "public_body_id": body, "name": f"Body {body}", "file_url": f"https://x/{body}.csv",
        "file_type": "csv", "foi_reference_id": None, "date_received": "2024-01-02",
        "decision_date": None, "requester_type": None, "decision_status": None,
        "review_status": None, "related_request": None, "request_description": "d",
        "row_id": rid, "known_issues": [], "missing_columns": [],
    }
    r.update(kw)
    return r


@pytest.fixture
def root(tmp_path):
    rows = [_row(2, "b2"), _row(1, "a2"), _row(1, "a1", request_description="x\x0by"), _row(2, "b1")]
    fd.write_parts(rows, tmp_path / "public/latest/foi-disclosures/bodies")
    (tmp_path / "public/pipeline-data.json").write_text(json.dumps({"public_bodies": [
        {"public_body_id": 1, "public_body_name": "Body 1", "public_body_url": None},
        {"public_body_id": 2, "public_body_name": "Body 2", "public_body_url": None}]}))
    (tmp_path / "pipelines/foi_pipeline/steps/db_upload").mkdir(parents=True)
    (tmp_path / "pipelines/foi_pipeline/steps/db_upload/slug_seed.json").write_text(json.dumps({"1": "body-1", "2": "body-2"}))
    return tmp_path


def test_build_writes_every_form_with_equal_row_counts(root):
    summary = build(root, commit="abc")
    out = root / "public/latest/foi-disclosures"
    combined = json.loads((root / "public/foi-disclosures.json").read_text())
    assert [(r["public_body_id"], r["row_id"]) for r in combined] == [(1, "a1"), (1, "a2"), (2, "b1"), (2, "b2")]
    assert len(json.loads((out / "foi-disclosures.jsonld").read_text())["@graph"]) == 4
    assert len(list(csv.reader(open(out / "foi-disclosures.csv", newline="", encoding="utf-8")))) == 5
    assert len(list(openpyxl.load_workbook(out / "foi-disclosures.xlsx", read_only=True).active.iter_rows())) == 5
    manifest = json.loads((out / "bodies/manifest.json").read_text())
    assert manifest["total_rows"] == 4 == summary["total_rows"]
    assert manifest["commit"] == "abc" and manifest["build"] is None


def test_build_never_touches_the_catalog_ttl(root):
    ttl = root / "public/catalog/dataset-foi-disclosures.ttl"
    ttl.parent.mkdir(parents=True)
    ttl.write_text('dct:modified "2020-01-01"^^xsd:date ;\n')
    build(root)
    build(root)
    assert ttl.read_text() == 'dct:modified "2020-01-01"^^xsd:date ;\n'


def test_build_is_deterministic(root):
    build(root, commit="abc")
    first = {p.name: p.read_bytes() for p in (root / "public/latest/foi-disclosures").glob("foi-disclosures.[cj]*")}
    build(root, commit="abc")
    assert {p.name: p.read_bytes() for p in (root / "public/latest/foi-disclosures").glob("foi-disclosures.[cj]*")} == first


def test_build_refuses_non_canonical_per_body_files(root):
    p = root / "public/latest/foi-disclosures/bodies/1.ndjson"
    p.write_text(p.read_text().replace('"file_type":"csv"', '"file_type": "csv"'))
    with pytest.raises(ValueError, match="not canonical"):
        build(root)


def test_build_pin_matches_pipeline_pin():
    def pin(path):
        return re.search(r"^openpyxl==(\S+)", (REPO / path).read_text(), re.M).group(1)

    assert pin("scripts/requirements-build.txt") == pin("pipelines/foi_pipeline/requirements.txt")
