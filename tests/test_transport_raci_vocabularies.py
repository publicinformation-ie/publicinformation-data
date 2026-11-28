"""Tests for the transport RACI vocabularies and generator check mode."""
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import pytest

from scripts import build_transport_raci as generator

REPO = Path(__file__).resolve().parent.parent
VOCAB = REPO / "public" / "vocabularies"
NS = REPO / "public" / "ns"
BASE = "https://data.publicinformation.ie/ns"
VOCABULARIES = [
    "transport-stage",
    "transport-activity",
    "transport-raci-party",
    "raci-evidence-level",
]
STAGES = [
    "S1", "S2", "S3", "S4", "S5", "S5G", "S6", "S7a", "S7b", "S7c",
    "S7D", "S8", "S9", "S10", "S11", "S12", "S13a", "S13b", "S14", "S15",
]


def notations_from_csv(name: str) -> set[str]:
    with (VOCAB / f"{name}.csv").open(encoding="utf-8", newline="") as handle:
        return {row["notation"] for row in csv.DictReader(handle)}


def notations_from_json(name: str) -> set[str]:
    payload = json.loads((VOCAB / f"{name}.json").read_text(encoding="utf-8"))
    return {concept["notation"] for concept in payload["concepts"]}


def notations_from_turtle(name: str) -> set[str]:
    rdflib = pytest.importorskip("rdflib")
    from rdflib.namespace import SKOS

    graph = rdflib.Graph()
    graph.parse(VOCAB / f"{name}.ttl", format="turtle")
    return {str(value) for value in graph.objects(None, SKOS.notation)}


def test_every_vocabulary_has_four_distributions() -> None:
    for name in VOCABULARIES:
        for suffix in ("json", "csv", "csv-metadata.json", "ttl", "md"):
            assert (VOCAB / f"{name}.{suffix}").exists(), f"{name}.{suffix}"


@pytest.mark.parametrize("name", VOCABULARIES)
def test_distributions_agree(name: str) -> None:
    assert notations_from_csv(name) == notations_from_json(name)
    assert notations_from_csv(name) == notations_from_turtle(name)


@pytest.mark.parametrize("name", VOCABULARIES)
def test_csvw_contract(name: str) -> None:
    payload = json.loads(
        (VOCAB / f"{name}.csv-metadata.json").read_text(encoding="utf-8"))
    assert payload["tableSchema"]["primaryKey"] == "uri"
    assert payload["tableSchema"]["aboutUrl"] == "{uri}"
    assert [column["name"] for column in payload["tableSchema"]["columns"]] == [
        "uri", "notation", "name", "description"]


def test_stage_vocabulary_has_twenty_stages() -> None:
    assert notations_from_json("transport-stage") == set(STAGES)


def test_confirmed_grouping_is_broader_than_cofog() -> None:
    rdflib = pytest.importorskip("rdflib")
    from rdflib.namespace import SKOS

    graph = rdflib.Graph()
    graph.parse(VOCAB / "transport-activity.ttl", format="turtle")
    subject = rdflib.URIRef(f"{BASE}/transport-activity#RT3")
    assert (subject, SKOS.broader,
            rdflib.URIRef(f"{BASE}/cofog#04.5.1")) in graph


def test_candidate_grouping_is_related_only() -> None:
    rdflib = pytest.importorskip("rdflib")
    from rdflib.namespace import SKOS

    graph = rdflib.Graph()
    graph.parse(VOCAB / "transport-activity.ttl", format="turtle")
    subject = rdflib.URIRef(f"{BASE}/transport-activity#X1")
    assert (subject, SKOS.related,
            rdflib.URIRef(f"{BASE}/cofog#03.1.0")) in graph
    cofog_broader = [
        value for value in graph.objects(subject, SKOS.broader)
        if str(value).startswith(f"{BASE}/cofog#")
    ]
    assert cofog_broader == []


def test_no_cofog_concept_is_declared() -> None:
    rdflib = pytest.importorskip("rdflib")

    graph = rdflib.Graph()
    graph.parse(VOCAB / "transport-activity.ttl", format="turtle")
    assert not [subject for subject in graph.subjects()
                if str(subject).startswith(f"{BASE}/cofog#")]


def test_retired_activity_is_published_as_retired() -> None:
    payload = json.loads(
        (VOCAB / "transport-activity.json").read_text(encoding="utf-8"))
    activity = next(
        concept for concept in payload["concepts"]
        if concept["notation"] == "RT-30")
    assert activity["status"] == "retired"
    assert activity["stages"] == []


def test_party_exact_match_and_evidence_labels() -> None:
    rdflib = pytest.importorskip("rdflib")
    from rdflib.namespace import SKOS

    graph = rdflib.Graph()
    graph.parse(VOCAB / "transport-raci-party.ttl", format="turtle")
    assert (rdflib.URIRef(f"{BASE}/transport-raci-party#TII"),
            SKOS.exactMatch,
            rdflib.URIRef(
                "https://data.publicinformation.ie/body/"
                "transport-infrastructure-ireland")) in graph

    evidence = json.loads(
        (VOCAB / "raci-evidence-level.json").read_text(encoding="utf-8"))
    levels = {concept["notation"]: concept for concept in evidence["concepts"]}
    assert levels["statute"]["plain_label"] == "set by law"
    assert levels["not-assessed"]["plain_label"] == "not yet assessed"
    assert levels["not-assessed"]["coverage_state"] is True


@pytest.mark.parametrize("name", VOCABULARIES)
def test_resolver_page_links_every_distribution(name: str) -> None:
    html = (NS / name / "index.html").read_text(encoding="utf-8")
    for suffix in ("json", "csv", "csv-metadata.json", "ttl"):
        assert f"../../vocabularies/{name}.{suffix}" in html


def test_generator_check_is_a_no_op() -> None:
    assert generator.main(["--check"]) == 0


def test_check_detects_a_hand_edit(tmp_path: Path, monkeypatch) -> None:
    shutil.copytree(REPO / "public" / "vocabularies", tmp_path / "vocabularies")
    shutil.copytree(REPO / "public" / "ns", tmp_path / "ns")
    shutil.copytree(REPO / "public" / "latest" / "transport-raci",
                    tmp_path / "latest" / "transport-raci")
    shutil.copytree(REPO / "public" / "v0.1.0" / "transport-raci",
                    tmp_path / "v0.1.0" / "transport-raci")
    shutil.copytree(REPO / "public" / "catalog", tmp_path / "catalog")
    for name, value in {
        "REPO": tmp_path,
        "VOCAB_DIR": tmp_path / "vocabularies",
        "NS_DIR": tmp_path / "ns",
        "LATEST_DIR": tmp_path / "latest" / "transport-raci",
        "VERSION_DIR": tmp_path / "v0.1.0" / "transport-raci",
        "CATALOG": tmp_path / "catalog" / "dataset-transport-raci.ttl",
    }.items():
        monkeypatch.setattr(generator, name, value)
    assert generator.main(["--check"]) == 0
    path = tmp_path / "vocabularies" / "transport-stage.csv"
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert generator.main(["--check"]) == 1


def test_activity_level_cofog_links_are_related_with_status() -> None:
    rdflib = pytest.importorskip("rdflib")
    from rdflib.namespace import SKOS

    graph = rdflib.Graph()
    graph.parse(VOCAB / "transport-activity.ttl", format="turtle")
    with (REPO / "reference" / "transport-raci" / "activity_cofog.csv").open(
            encoding="utf-8", newline="") as handle:
        links = list(csv.DictReader(handle))
    assert links
    for link in links:
        subject = rdflib.URIRef(
            f"{BASE}/transport-activity#{link['activity_id']}")
        target = rdflib.URIRef(f"{BASE}/cofog#{link['cofog_code']}")
        assert (subject, SKOS.related, target) in graph
        assert (subject, SKOS.broader, target) not in graph
        assert rdflib.Literal(
            f"COFOG {link['cofog_code']}: {link['status']}", lang="en") in set(
                graph.objects(subject, SKOS.scopeNote))


def test_validation_failure_writes_nothing(monkeypatch) -> None:
    from dataclasses import replace

    from src.lib.transport_raci import AssignmentRole, load_master

    master = load_master()
    first = master.assignments[0].assignment_id
    broken = replace(master, assignment_roles=[
        *master.assignment_roles,
        AssignmentRole(first, "A", "NTA", ""),
        AssignmentRole(first, "A", "TII", ""),
    ])
    calls: list[object] = []
    monkeypatch.setattr(generator, "load_master", lambda: broken)
    monkeypatch.setattr(generator, "stamp_if_changed",
                        lambda *args, **kwargs: calls.append(args) or True)
    monkeypatch.setattr(generator, "build_all",
                        lambda *args: calls.append("build") or {})
    assert generator.main([]) == 1
    assert calls == []
