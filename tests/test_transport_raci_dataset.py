"""Tests for the published transport RACI dataset."""
from __future__ import annotations

import csv
import json
import re
from dataclasses import replace
from pathlib import Path

import pytest

from scripts import build_transport_raci as generator
from src.lib.transport_raci import load_master
from src.lib.transport_raci.model import INTERNAL_REF, LEAK_REF

REPO = Path(__file__).resolve().parent.parent
PUBLIC = REPO / "public"
LATEST = PUBLIC / "latest" / "transport-raci"
VERSIONED = PUBLIC / "v0.1.0" / "transport-raci"
SCOPE = (
    "The assignments have been analysed for Meath County Council only. They "
    "may differ for other councils. Meath is in the Greater Dublin Area.")
MEATH = "https://data.publicinformation.ie/body/meath-county-council"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_latest_and_versioned_trees_are_byte_identical() -> None:
    names = sorted(path.name for path in LATEST.iterdir() if path.is_file())
    assert names == sorted(
        path.name for path in VERSIONED.iterdir() if path.is_file())
    for name in names:
        assert (LATEST / name).read_bytes() == (VERSIONED / name).read_bytes(), name


def test_roles_reference_party_vocabulary_uris() -> None:
    roles = read_csv(LATEST / "assignment-roles.csv")
    assert roles
    for role in roles:
        assert role["party"].startswith(
            "https://data.publicinformation.ie/ns/transport-raci-party#")
        assert role["role"] in {"R", "A", "C", "I"}


def test_every_assignment_is_scoped_to_meath() -> None:
    assignments = read_csv(LATEST / "assignments.csv")
    assert assignments
    assert {row["applies_to"] for row in assignments} == {MEATH}


def test_coverage_totals_and_a_not_assessed_row() -> None:
    rows = read_csv(LATEST / "rows.csv")
    assert len(rows) == 613
    assert sum(1 for row in rows if row["coverage"] == "assessed") == 184
    assert sum(1 for row in rows if row["coverage"] == "not assessed") == 429
    rail = next(row for row in rows if row["row_id"] == "RL-03.S2")
    assert rail["coverage"] == "not assessed"
    assert rail["assessed_lines"] == "0"


def test_wide_view_reads_the_expected_line() -> None:
    wide = read_csv(LATEST / "raci-wide.csv")
    assert len(wide) == 224
    line = next(row for row in wide if row["row_id"] == "RT-09.S12")
    assert line["A"] == (
        "the Chief Executive and executive of Meath County Council")
    assert line["evidence"] == "set by law"


def test_json_and_csv_tables_agree() -> None:
    payload = json.loads(
        (LATEST / "transport-raci.json").read_text(encoding="utf-8"))
    json_assignments = set()
    json_roles = set()
    for activity in payload["activities"]:
        for stage in activity["stages"]:
            for assignment in stage["assignments"]:
                json_assignments.add(assignment["assignment_id"])
                for role in assignment["roles"]:
                    json_roles.add((assignment["assignment_id"],
                                    role["role"], role["party_id"],
                                    role["qualifier"]))
    csv_assignments = {
        row["assignment_id"] for row in read_csv(LATEST / "assignments.csv")}
    csv_roles = {
        (row["assignment_id"], row["role"],
         row["party"].rsplit("#", 1)[1], row["qualifier"])
        for row in read_csv(LATEST / "assignment-roles.csv")}
    assert json_assignments == csv_assignments
    assert json_roles == csv_roles


def test_no_local_authority_role_is_derived() -> None:
    wide = {row["assignment_id"]: row
            for row in read_csv(LATEST / "raci-wide.csv")}
    national_roads = wide["RT-25.S13a~national-managed-roads"]
    assert national_roads["no_local_authority_role"] == "true"
    assert "Meath County Council" not in (
        national_roads["R"] + national_roads["A"]
        + national_roads["C"] + national_roads["I"])
    active_travel = wide["RT-09.S12"]
    assert active_travel["no_local_authority_role"] == "false"
    # A council organ with a role reads false even on a thin line.
    assert wide["RT-10.S11"]["no_local_authority_role"] == "false"
    # No Accountable party: not established, never "no role".
    for assignment_id in (
            "RT-10.S11~royal-canal-greenway-waterways-ireland-land",
            "RT-10.S12~royal-canal-greenway-waterways-ireland-land",
            "RT-13.S12~nta-delivered-busconnects"):
        assert wide[assignment_id]["no_local_authority_role"] == "unknown"
        assert wide[assignment_id]["A"] == ""
    assert {row["no_local_authority_role"] for row in wide.values()} == {
        "true", "false", "unknown"}


def test_no_local_authority_role_is_typed_in_json_and_csvw() -> None:
    wide = {row["assignment_id"]: row["no_local_authority_role"]
            for row in read_csv(LATEST / "raci-wide.csv")}
    assert set(wide.values()) == {"true", "false", "unknown"}
    payload = json.loads(
        (LATEST / "transport-raci.json").read_text(encoding="utf-8"))
    cell = {True: "true", False: "false", None: "unknown"}
    seen = {}
    for activity in payload["activities"]:
        for stage in activity["stages"]:
            for assignment in stage["assignments"]:
                value = assignment["no_local_authority_role"]
                assert value is None or isinstance(value, bool)
                assert cell[value] == wide[assignment["assignment_id"]]
                seen[assignment["assignment_id"]] = value
    assert len(seen) == len(wide)
    unknown = sorted(key for key, value in seen.items() if value is None)
    assert unknown == sorted([
        "RT-10.S11~royal-canal-greenway-waterways-ireland-land",
        "RT-10.S12~royal-canal-greenway-waterways-ireland-land",
        "RT-13.S5G~nta-delivered-busconnects",
        "RT-13.S12~nta-delivered-busconnects",
    ])
    assert all(wide[key] == "unknown" for key in unknown)
    metadata = json.loads(
        (LATEST / "raci-wide.csv-metadata.json").read_text(encoding="utf-8"))
    column = next(column for column in metadata["tableSchema"]["columns"]
                  if column["name"] == "no_local_authority_role")
    assert column["datatype"] == "boolean"
    assert column["null"] == "unknown"
    assert "format" not in column


def test_organ_labels_name_the_council_from_the_jurisdiction() -> None:
    parties = json.loads((PUBLIC / "vocabularies" / "transport-raci-party.json")
                         .read_text(encoding="utf-8"))
    labels = {concept["notation"]: concept["plain_label"]
              for concept in parties["concepts"]}
    assert labels["LA-M"] == "the elected members of the council"
    assert labels["LA-CE"] == "the Chief Executive and executive of the council"
    for concept in parties["concepts"]:
        assert "Meath" not in concept["plain_label"]
    wide = {row["assignment_id"]: row
            for row in read_csv(LATEST / "raci-wide.csv")}
    assert wide["RT-24.S13a"]["A"] == "the elected members of Meath County Council"


def test_catalogue_download_urls_are_versioned() -> None:
    rdflib = pytest.importorskip("rdflib")
    graph = rdflib.Graph()
    graph.parse(PUBLIC / "catalog" / "dataset-transport-raci.ttl",
                format="turtle")
    dcat = rdflib.Namespace("http://www.w3.org/ns/dcat#")
    downloads = [str(value) for value in graph.objects(None, dcat.downloadURL)]
    access = [str(value) for value in graph.objects(None, dcat.accessURL)]
    assert len(downloads) == 9
    for url in downloads:
        assert url.startswith(
            "https://data.publicinformation.ie/v0.1.0/transport-raci/"), url
        relative = url.removeprefix("https://data.publicinformation.ie/")
        assert (PUBLIC / relative).exists(), url
    for url in access:
        assert url.startswith(
            "https://data.publicinformation.ie/latest/transport-raci/"), url


def test_readme_gives_a_correction_route_and_keeps_variant_labels() -> None:
    readme = (LATEST / "README.md").read_text(encoding="utf-8")
    catalogue = (PUBLIC / "catalog" / "dataset-transport-raci.ttl").read_text(
        encoding="utf-8")
    email = re.search(r"vcard:hasEmail <mailto:([^>]+)>", catalogue)
    assert email
    assert f"email {email.group(1)}" in readme
    assert "(Garda-run event closures (e.g. Slane 2026))" in readme
    assert "NTA-delivered (BusConnects, GDA)" in readme
    assert "Royal Canal Greenway (Waterways Ireland land)" in readme


def test_scope_statement_is_in_readme_and_llms() -> None:
    for name in ("README.md", "llms.txt"):
        text = (LATEST / name).read_text(encoding="utf-8")
        assert SCOPE in text, name


def test_llms_links_resolve_in_the_tree() -> None:
    text = (LATEST / "llms.txt").read_text(encoding="utf-8")
    links = re.findall(r"\((https://data\.publicinformation\.ie/[^)]+)\)", text)
    assert links
    for link in links:
        relative = link.removeprefix("https://data.publicinformation.ie/")
        assert (PUBLIC / relative).exists(), link


def test_methodology_is_hand_written_and_leak_safe() -> None:
    methodology = (LATEST / "METHODOLOGY.md").read_text(encoding="utf-8")
    assert "14 scenarios" in methodology
    assert SCOPE in methodology
    assert not LEAK_REF.search(methodology)


def test_leak_check_passes_on_real_output() -> None:
    master = load_master()
    assert generator.check(master, generator.build_all(master)) == []


def test_leak_check_fails_on_an_internal_reference() -> None:
    master = load_master()
    outputs = generator.build_all(master)
    outputs[LATEST / "bad.md"] = b"See F9 and Decision 4."
    with pytest.raises(SystemExit):
        generator.check(master, outputs)


@pytest.mark.parametrize("text", [
    "Department of Education (v0.4)", "v0.4: S6 added.", "Retired in v0.3.",
    "Post-construction party UNVERIFIED (v0.4 correction).",
])
def test_leak_check_fails_on_a_version_marker(text: str) -> None:
    master = load_master()
    outputs = generator.build_all(master)
    outputs[LATEST / "bad.md"] = text.encode("utf-8")
    with pytest.raises(SystemExit):
        generator.check(master, outputs)


def test_version_pattern_spares_dataset_urls() -> None:
    assert INTERNAL_REF.search("(v0.4)")
    assert INTERNAL_REF.search("v0.4: the order moves")
    assert INTERNAL_REF.search("Retired in v0.3.")
    assert not LEAK_REF.search(
        "https://data.publicinformation.ie/v0.1.0/transport-raci/README.md")
    assert not LEAK_REF.search("owl:versionInfo \"0.1.0\"")


def test_published_files_carry_no_version_marker() -> None:
    master = load_master()
    for path, data in generator.build_all(master).items():
        if path.suffix in {".csv", ".json", ".ttl", ".md", ".html", ".txt"}:
            assert not LEAK_REF.search(data.decode("utf-8")), path


def test_missing_public_note_blocks_the_build() -> None:
    master = load_master()
    assignment = master.assignments[0]
    leaked = replace(assignment, note="See F9.", public_note="")
    broken = replace(master, assignments=[leaked, *master.assignments[1:]])
    outputs = generator.build_all(master)
    with pytest.raises(SystemExit):
        generator.check(broken, outputs)


def test_catalogue_parses_with_provenance() -> None:
    rdflib = pytest.importorskip("rdflib")
    from rdflib.namespace import DCTERMS, OWL

    graph = rdflib.Graph()
    graph.parse(PUBLIC / "catalog" / "dataset-transport-raci.ttl",
                format="turtle")
    dataset = rdflib.URIRef(
        "https://data.publicinformation.ie/dataset/transport-raci")
    assert list(graph.objects(dataset, DCTERMS.provenance))
    assert list(graph.objects(dataset, DCTERMS.spatial)) == [
        rdflib.URIRef(MEATH)]
    assert list(graph.objects(dataset, DCTERMS.license)) == [
        rdflib.URIRef("https://creativecommons.org/licenses/by/4.0/")]
    assert [str(value) for value in graph.objects(dataset, OWL.versionInfo)] == [
        "0.1.0"]
    assert list(graph.objects(
        dataset, rdflib.URIRef("http://www.w3.org/ns/adms#status")))
    derived = {str(value) for value in graph.objects(
        dataset, rdflib.URIRef("http://www.w3.org/ns/prov#wasDerivedFrom"))}
    urls = set()
    for source in read_csv(LATEST / "sources.csv"):
        for url in source["urls"].split(";"):
            if url.strip():
                urls.add(url.strip())
    assert derived == urls
    assert any("public-bodies" in str(value)
               for value in graph.objects(dataset, DCTERMS.relation))
    assert any("cofog" in str(value)
               for value in graph.objects(dataset, DCTERMS.relation))
