import csv
import io

import pytest

from transform_transport_policies import FIELDNAMES, build_rows, publish

POLICIES = [
    {"policy_id": "alpha", "number": 1, "title": 'Alpha, "Quoted" & <b>', "kind": "policy",
     "issuing_authority": "DoT", "horizon": "2022–2030", "scope": "line one\nline two, with comma",
     "linkages": "NSMP, Project Ireland 2040", "source_urls": ["https://e.org/a"]},
    {"policy_id": "beta", "number": 2, "title": "Beta", "kind": "code-of-practice",
     "issuing_authority": "DoT", "horizon": "Current", "scope": "S", "linkages": "L",
     "source_urls": ["https://e.org/b1", "https://e.org/b2"]},
    {"policy_id": "gamma", "number": 3, "title": "Gamma", "kind": "policy",
     "issuing_authority": "DoT", "horizon": "Current", "scope": "S", "linkages": "L",
     "source_urls": ["https://www.localgov.ie/"]},
]
DOCS = [
    {"doc_slug": "alpha-plan", "policy_id": "alpha"},
    {"doc_slug": "alpha-report", "policy_id": "alpha"},
    {"doc_slug": "beta-doc", "policy_id": "beta"},
]


def test_columns_are_the_published_contract():
    assert FIELDNAMES == ["policy_id", "title", "kind", "issuing_authority", "horizon", "scope",
                          "linkages", "source_urls", "has_document", "doc_slugs"]


def test_build_rows_joins_documents_in_file_order():
    rows = {r["policy_id"]: r for r in build_rows(POLICIES, DOCS)}
    assert rows["alpha"]["doc_slugs"] == "alpha-plan|alpha-report"
    assert rows["alpha"]["has_document"] == "true"
    assert rows["beta"]["source_urls"] == "https://e.org/b1|https://e.org/b2"


def test_a_policy_without_documents_is_kept_with_an_empty_doc_slugs_cell():
    row = {r["policy_id"]: r for r in build_rows(POLICIES, DOCS)}["gamma"]
    assert row["has_document"] == "false"
    assert row["doc_slugs"] == ""


def test_rows_keep_inventory_order_and_only_fieldname_keys():
    rows = build_rows(POLICIES, DOCS)
    assert [r["policy_id"] for r in rows] == ["alpha", "beta", "gamma"]
    assert all(list(r) == FIELDNAMES for r in rows)


def test_a_document_for_an_unknown_policy_is_fatal():
    with pytest.raises(ValueError, match="not-a-policy"):
        build_rows(POLICIES, DOCS + [{"doc_slug": "x", "policy_id": "not-a-policy"}])


def test_csv_round_trips_commas_quotes_newlines_and_html_characters(tmp_path):
    csv_path = tmp_path / "t.csv"
    ttl_path = tmp_path / "t.ttl"
    ttl_path.write_text('<x>\n    dct:modified "2000-01-01"^^xsd:date ;\n', encoding="utf-8")
    assert publish(build_rows(POLICIES, DOCS), csv_path, ttl_path) is True
    parsed = list(csv.DictReader(io.StringIO(csv_path.read_text(encoding="utf-8"), newline="")))
    assert parsed[0]["title"] == 'Alpha, "Quoted" & <b>'
    assert parsed[0]["scope"] == "line one\nline two, with comma"
    assert "2000-01-01" not in ttl_path.read_text()           # dct:modified restamped


def test_republishing_identical_content_does_not_touch_the_ttl(tmp_path):
    csv_path, ttl_path = tmp_path / "t.csv", tmp_path / "t.ttl"
    ttl_path.write_text('<x>\n    dct:modified "2000-01-01"^^xsd:date ;\n', encoding="utf-8")
    rows = build_rows(POLICIES, DOCS)
    publish(rows, csv_path, ttl_path)
    ttl_after_first = ttl_path.read_text()
    assert publish(rows, csv_path, ttl_path) is False
    assert ttl_path.read_text() == ttl_after_first
