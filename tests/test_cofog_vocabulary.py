"""Tests for the published COFOG 1999 vocabulary.

Covers the generator (`scripts/build_cofog_vocabulary.py`), the four
distributions under `public/vocabularies/`, the `/ns/cofog` resolver, the
DCAT catalogue record, the documentation links, and the SPC schema contract
the vocabulary must not break.
"""
import copy
import csv
import hashlib
import importlib.util
import json
import posixpath
import re
import subprocess
import sys
from pathlib import Path

import pytest

from build_cofog_vocabulary import (
    LICENSE,
    NAMESPACE,
    OUTPUT_NAMES,
    REFERENCE,
    SCHEME_URI,
    TITLE,
    VERSION,
    build,
    check,
    load_reference,
    validate,
)

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "public" / "vocabularies"
NS_DIR = REPO / "public" / "ns" / "cofog"
SCHEMA = json.loads(
    (REPO / "public/schemas/spc-meetings.schema.json").read_text(encoding="utf-8"))


def _committed(name: str) -> bytes:
    return (OUT_DIR / name).read_bytes()


@pytest.fixture(scope="module")
def reference() -> dict:
    return load_reference(REFERENCE)


@pytest.fixture(scope="module")
def outputs(reference) -> dict[str, bytes]:
    return build(reference)


# --- Generator: validation is fail closed ---------------------------------


def _mutated(reference: dict, mutate) -> dict:
    bad = copy.deepcopy(reference)
    mutate(bad)
    return bad


def test_missing_source_url_raises(reference):
    bad = _mutated(reference, lambda d: d["metadata"].pop("source_url"))
    with pytest.raises(ValueError, match="source URL"):
        build(bad)


def test_missing_sha256_raises(reference):
    bad = _mutated(reference, lambda d: d["metadata"].pop("sha256"))
    with pytest.raises(ValueError, match="sha256"):
        build(bad)


def test_duplicate_code_raises(reference):
    bad = _mutated(reference, lambda d: d["codes"].append(copy.deepcopy(d["codes"][0])))
    with pytest.raises(ValueError, match="duplicate code"):
        build(bad)


@pytest.mark.parametrize("level,missing", [("group", "99"), ("class", "99.9")])
def test_missing_parent_raises(reference, level, missing):
    def break_parent(d):
        for entry in d["codes"]:
            if entry["level"] == level:
                entry["parent"] = missing
                break
    bad = _mutated(reference, break_parent)
    with pytest.raises(ValueError, match="unknown parent"):
        build(bad)


@pytest.mark.parametrize("bad_text", ["Street\nlighting", "Street\rlighting",
                                      "Street\tlighting", "Street\x00lighting"])
def test_control_character_in_a_label_raises(reference, bad_text):
    def poison(d):
        d["codes"][0]["description"] = bad_text
    with pytest.raises(ValueError, match="control character"):
        build(_mutated(reference, poison))


def test_impossible_retrieval_date_raises(reference):
    bad = _mutated(reference, lambda d: d["metadata"].update(retrieved_date="2026-13-45"))
    with pytest.raises(ValueError, match="not a valid date"):
        build(bad)


def test_non_object_code_entry_raises(reference):
    bad = _mutated(reference, lambda d: d["codes"].insert(0, "01"))
    with pytest.raises(ValueError, match="not an object"):
        build(bad)


def test_count_mismatch_raises(reference):
    bad = _mutated(reference, lambda d: d["codes"].pop())
    with pytest.raises(ValueError, match="expected"):
        build(bad)


def _published_tree(tmp_path: Path, monkeypatch, reference: dict, outputs) -> tuple[Path, Path]:
    """Point the generator's main() at a temp reference, output dir and catalogue."""
    out_dir = tmp_path / "vocabularies"
    out_dir.mkdir()
    for name in OUTPUT_NAMES:
        (out_dir / name).write_bytes(outputs[name])
    catalog = tmp_path / "dataset-cofog-1999.ttl"
    catalog.write_bytes((REPO / "public/catalog/dataset-cofog-1999.ttl").read_bytes())
    ref_path = tmp_path / "cofog_1999.json"
    ref_path.write_text(json.dumps(reference), encoding="utf-8")
    monkeypatch.setattr("build_cofog_vocabulary.REFERENCE", ref_path)
    monkeypatch.setattr("build_cofog_vocabulary.OUT_DIR", out_dir)
    monkeypatch.setattr("build_cofog_vocabulary.CATALOG_TTL", catalog)
    return out_dir, catalog


@pytest.mark.parametrize("mutate", [
    lambda d: d["metadata"].pop("source_url"),
    lambda d: d["metadata"].pop("sha256"),
    lambda d: d["codes"].append(copy.deepcopy(d["codes"][0])),
    lambda d: d["codes"].pop(),
    lambda d: d["codes"][1].update(parent="99"),
], ids=["no-source-url", "no-sha256", "duplicate", "count", "missing-parent"])
def test_invalid_reference_leaves_the_published_files_untouched(
        tmp_path, monkeypatch, reference, outputs, mutate):
    from build_cofog_vocabulary import main as bcv_main

    # Change one label so a successful run *would* rewrite every distribution;
    # the mutation must still stop main() before any byte is written.
    def mutate_and_relabel(d):
        d["codes"][0]["description"] += " (edited)"
        mutate(d)
    out_dir, catalog = _published_tree(
        tmp_path, monkeypatch, _mutated(reference, mutate_and_relabel), outputs)
    before = {p.name: p.read_bytes() for p in [*out_dir.iterdir(), catalog]}
    with pytest.raises(ValueError):
        bcv_main([])
    after = {p.name: p.read_bytes() for p in [*out_dir.iterdir(), catalog]}
    assert after == before


def test_write_restamps_the_catalogue_only_on_change(tmp_path, monkeypatch, reference, outputs):
    from datetime import date

    from build_cofog_vocabulary import main as bcv_main

    out_dir, catalog = _published_tree(tmp_path, monkeypatch, reference, outputs)
    catalog.write_text(re.sub(r'(dct:modified ")[^"]*', r"\g<1>2000-01-01",
                              catalog.read_text(encoding="utf-8")), encoding="utf-8")
    stale_catalog = catalog.read_bytes()

    assert bcv_main([]) == 0  # unchanged reference: no write, no stamp
    assert catalog.read_bytes() == stale_catalog

    edited = _mutated(reference, lambda d: d["codes"][0].update(
        description=d["codes"][0]["description"] + " (edited)"))
    (tmp_path / "cofog_1999.json").write_text(json.dumps(edited), encoding="utf-8")
    assert bcv_main([]) == 0
    assert b"(edited)" in (out_dir / "cofog-1999.ttl").read_bytes()
    assert f'dct:modified "{date.today().isoformat()}"' in catalog.read_text(encoding="utf-8")


def test_validate_reports_the_code_list(reference):
    codes = validate(reference)
    assert [entry["code"] for entry in codes][:3] == ["01", "01.1", "01.1.1"]


# --- JSON distribution ------------------------------------------------------


def _json_distribution() -> dict:
    return json.loads(_committed("cofog-1999.json"))


@pytest.fixture(scope="module")
def vocabulary() -> dict:
    return _json_distribution()


def test_json_scheme_metadata_carries_provenance(vocabulary):
    scheme = vocabulary["scheme"]
    assert scheme["title"] == TITLE
    assert scheme["version"] == VERSION
    assert scheme["namespace"] == f"{NAMESPACE}#"
    assert scheme["license"] == LICENSE
    assert scheme["source"]["url"] == (
        "https://unstats.un.org/unsd/classifications/Econ/Download/"
        "In%20Text/COFOG_english_structure.txt")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", scheme["source"]["retrieved_date"])
    assert re.fullmatch(r"[0-9a-f]{64}", scheme["source"]["sha256"])


def _tree_codes(vocabulary: dict) -> set[str]:
    codes = set()
    for division in vocabulary["divisions"]:
        codes.add(division["code"])
        for group in division["groups"]:
            codes.add(group["code"])
            codes.update(c["code"] for c in group["classes"])
    return codes


def _tree_concepts(vocabulary: dict) -> dict[str, dict]:
    concepts = {}
    for division in vocabulary["divisions"]:
        for node in [division, *division["groups"],
                     *(c for g in division["groups"] for c in g["classes"])]:
            concepts[node["code"]] = {
                key: node[key] for key in
                ("code", "uri", "label", "level", "parent", "service_type")}
    return concepts


def test_json_counts_match_the_source(vocabulary):
    index = vocabulary["concepts"]
    assert len(index) == 188
    assert sum(1 for c in index if c["level"] == "division") == 10
    assert sum(1 for c in index if c["level"] == "group") == 69
    assert sum(1 for c in index if c["level"] == "class") == 109
    assert _tree_codes(vocabulary) == {c["code"] for c in index}


def test_json_tree_and_index_agree(vocabulary):
    index = {c["code"]: c for c in vocabulary["concepts"]}
    tree = _tree_concepts(vocabulary)
    assert tree == index


def test_json_parent_integrity(vocabulary):
    levels = {c["code"]: c["level"] for c in vocabulary["concepts"]}
    for concept in vocabulary["concepts"]:
        if concept["level"] == "division":
            assert concept["parent"] is None
        elif concept["level"] == "group":
            assert levels[concept["parent"]] == "division"
        else:
            assert levels[concept["parent"]] == "group"


def test_json_concept_fields(vocabulary):
    index = {c["code"]: c for c in vocabulary["concepts"]}
    road = index["04.5.1"]
    assert road["level"] == "class"
    assert road["label"] == "Road transport"
    assert road["parent"] == "04.5"
    assert road["service_type"] == "collective"
    assert road["uri"] == f"{NAMESPACE}#04.5.1"
    lighting = index["06.4.0"]
    assert lighting["label"] == "Street lighting"
    assert lighting["parent"] == "06.4"
    assert lighting["service_type"] == "collective"
    group = index["04.5"]
    assert group["service_type"] is None
    individual = index["07.1.1"]
    assert individual["service_type"] == "individual"


def test_unknown_code_is_absent(vocabulary):
    index = {c["code"] for c in vocabulary["concepts"]}
    assert "04.5.9" not in index
    with open(OUT_DIR / "cofog-1999.csv", newline="", encoding="utf-8") as handle:
        assert "04.5.9" not in {row["notation"] for row in csv.DictReader(handle)}
    assert f"{NAMESPACE}#04.5.9>" not in _committed("cofog-1999.ttl").decode("utf-8")


# --- Regeneration is a no-op and drift is detected --------------------------


def test_committed_files_match_the_generator(outputs):
    for name in OUTPUT_NAMES:
        assert _committed(name) == outputs[name], name


def test_check_is_clean_on_the_committed_tree():
    proc = subprocess.run(
        [sys.executable, str(REPO / "scripts/build_cofog_vocabulary.py"), "--check"],
        capture_output=True, text=True, cwd=REPO)
    assert proc.returncode == 0, proc.stderr


def test_check_names_a_drifted_file(tmp_path, monkeypatch, capsys, outputs, reference):
    from build_cofog_vocabulary import main as bcv_main

    for name in OUTPUT_NAMES:
        (tmp_path / name).write_bytes(outputs[name])
    monkeypatch.setattr("build_cofog_vocabulary.OUT_DIR", tmp_path)
    assert bcv_main(["--check"]) == 0

    data = json.loads((tmp_path / "cofog-1999.json").read_text(encoding="utf-8"))
    data["divisions"][0]["label"] += " "  # one-byte edit
    (tmp_path / "cofog-1999.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    capsys.readouterr()
    assert bcv_main(["--check"]) == 1
    err = capsys.readouterr().err
    assert "cofog-1999.json" in err
    assert "cofog-1999.csv" not in err and "cofog-1999.ttl" not in err


# --- CSV and CSVW metadata --------------------------------------------------


def test_csv_keeps_the_four_column_shape():
    rows = list(csv.DictReader(_committed("cofog-1999.csv").decode("utf-8").splitlines()))
    assert rows[0].keys() == {"uri", "notation", "name", "description"}
    assert len(rows) == 188
    assert rows[0]["description"] == "COFOG 1999 division"


def test_csv_notations_equal_the_json_codes(outputs):
    rows = list(csv.DictReader(_committed("cofog-1999.csv").decode("utf-8").splitlines()))
    codes = {c["code"] for c in json.loads(outputs["cofog-1999.json"])["concepts"]}
    assert {row["notation"] for row in rows} == codes


def test_csvw_declares_the_primary_key_and_about_url():
    metadata = json.loads(_committed("cofog-1999.csv-metadata.json"))
    schema = metadata["tableSchema"]
    assert schema["primaryKey"] == "uri"
    assert schema["aboutUrl"] == "{uri}"
    assert [column["name"] for column in schema["columns"]] == [
        "uri", "notation", "name", "description"]


def test_spc_schema_cofog_enum_still_equals_the_csv_notations():
    path = OUT_DIR / "cofog-1999.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        notations = {row["notation"] for row in csv.DictReader(handle)}
    enum = SCHEMA["$defs"]["item"]["properties"]["cofog"]["items"]["enum"]
    assert notations == set(enum)


# --- SPC builder no longer writes COFOG -------------------------------------


def _load_spc_vocabulary_builder():
    spec = importlib.util.spec_from_file_location(
        "spc_build_vocabularies",
        REPO / "pipelines/spc_pipeline/scripts/build_vocabularies.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_spc_builder_has_no_cofog_writer():
    source = (REPO / "pipelines/spc_pipeline/scripts/build_vocabularies.py"
              ).read_text(encoding="utf-8")
    assert "cofog_rows" not in source
    assert 'write_vocabulary("cofog-1999"' not in source
    assert "build_cofog_vocabulary.py" in source


def test_spc_builder_still_writes_its_vocabularies(tmp_path):
    module = _load_spc_vocabulary_builder()
    module.OUT = tmp_path
    module.main()
    expected = {
        "spc-attendance-status", "spc-attendance-mode", "spc-attendee-category",
        "spc-decision-type", "spc-text-source", "transport-subdomain"}
    names = {path.stem for path in tmp_path.glob("*.csv")}
    assert names == expected
    assert not (tmp_path / "cofog-1999.csv").exists()


# --- Turtle distribution ----------------------------------------------------


@pytest.fixture(scope="module")
def turtle_graph(reference):
    rdflib = pytest.importorskip("rdflib")
    graph = rdflib.Graph()
    graph.parse(OUT_DIR / "cofog-1999.ttl", format="turtle")
    return graph


def _cofog_uri(code: str) -> str:
    return f"{NAMESPACE}#{code}"


def test_turtle_has_one_scheme_and_188_concepts(turtle_graph):
    from rdflib import RDF, URIRef
    from rdflib.namespace import SKOS

    schemes = list(turtle_graph.subjects(RDF.type, SKOS.ConceptScheme))
    assert schemes == [URIRef(SCHEME_URI)]
    concepts = list(turtle_graph.subjects(RDF.type, SKOS.Concept))
    assert len(concepts) == 188


def test_turtle_scheme_metadata(turtle_graph):
    from rdflib import URIRef
    from rdflib.namespace import DCTERMS, OWL, RDF

    scheme = URIRef(SCHEME_URI)
    assert turtle_graph.value(scheme, RDF.type) is not None
    assert str(turtle_graph.value(scheme, OWL.versionInfo)) == "1999"
    assert str(turtle_graph.value(scheme, DCTERMS.license)) == LICENSE
    assert str(turtle_graph.value(scheme, DCTERMS.source)) == (
        "https://unstats.un.org/unsd/classifications/Econ/Download/"
        "In%20Text/COFOG_english_structure.txt")
    assert str(turtle_graph.value(scheme, DCTERMS.title)) == TITLE


def test_turtle_notations_match_the_json_codes(turtle_graph, vocabulary):
    from rdflib.namespace import SKOS

    notations = {str(o) for o in turtle_graph.objects(None, SKOS.notation)}
    assert notations == {c["code"] for c in vocabulary["concepts"]}


def test_turtle_broader_matches_the_json_parent(turtle_graph, vocabulary):
    from rdflib import RDF, URIRef
    from rdflib.namespace import SKOS

    for concept in vocabulary["concepts"]:
        uri = URIRef(concept["uri"])
        assert (uri, RDF.type, SKOS.Concept) in turtle_graph
        assert (uri, SKOS.inScheme, URIRef(SCHEME_URI)) in turtle_graph
        broader = list(turtle_graph.objects(uri, SKOS.broader))
        if concept["parent"] is None:
            assert broader == []
        else:
            assert [str(b) for b in broader] == [_cofog_uri(concept["parent"])]


def test_turtle_top_concepts_are_the_divisions(turtle_graph, vocabulary):
    from rdflib import URIRef
    from rdflib.namespace import SKOS

    scheme = URIRef(SCHEME_URI)
    top = {str(o) for o in turtle_graph.objects(scheme, SKOS.hasTopConcept)}
    divisions = {c["uri"] for c in vocabulary["concepts"]
                 if c["level"] == "division"}
    assert top == divisions
    assert len(top) == 10


def test_turtle_class_scope_notes(turtle_graph):
    from rdflib import URIRef
    from rdflib.namespace import SKOS

    road = URIRef(_cofog_uri("04.5.1"))
    pharma = URIRef(_cofog_uri("07.1.1"))
    transport = URIRef(_cofog_uri("04.5"))
    general = URIRef(_cofog_uri("01"))
    assert str(turtle_graph.value(road, SKOS.scopeNote)) == "Collective service"
    assert str(turtle_graph.value(pharma, SKOS.scopeNote)) == "Individual service"
    assert turtle_graph.value(transport, SKOS.scopeNote) is None
    assert turtle_graph.value(general, SKOS.scopeNote) is None


def test_turtle_scope_notes_only_on_classes(turtle_graph, vocabulary):
    from rdflib import URIRef
    from rdflib.namespace import SKOS

    levels = {c["code"]: c["level"] for c in vocabulary["concepts"]}
    for subject in turtle_graph.subjects(SKOS.scopeNote, None):
        code = str(subject).rsplit("#", 1)[-1]
        assert levels[code] == "class", code


# --- Resolver page ----------------------------------------------------------


def test_resolver_page_exists_and_names_the_vocabulary():
    html = (NS_DIR / "index.html").read_text(encoding="utf-8")
    assert "COFOG 1999" in html
    assert "https://data.publicinformation.ie/ns/cofog#<em>&lt;code&gt;</em>" in html


def test_resolver_links_resolve_from_public_ns_cofog():
    html = (NS_DIR / "index.html").read_text(encoding="utf-8")
    hrefs = re.findall(r'(?:href|content)="([^"]+)"', html)
    linked = [href for href in hrefs if href.startswith("../../")]
    assert linked, "the resolver page should link the distributions relatively"
    for href in linked:
        resolved = posixpath.normpath(posixpath.join("public/ns/cofog", href))
        assert (REPO / resolved).exists(), href
        if "cofog-1999" in href:
            assert resolved.startswith("public/vocabularies/"), href


def test_resolver_declares_alternate_formats():
    html = (NS_DIR / "index.html").read_text(encoding="utf-8")
    for fmt in ("cofog-1999.json", "cofog-1999.csv",
                "cofog-1999.csv-metadata.json", "cofog-1999.ttl"):
        assert f'href="../../vocabularies/{fmt}"' in html
    assert 'rel="alternate"' in html


def test_resolver_lists_ten_divisions():
    html = (NS_DIR / "index.html").read_text(encoding="utf-8")
    for code in [f"{n:02d}" for n in range(1, 11)]:
        assert f"ns/cofog#{code}" in html


# --- Catalogue, README and discovery links ----------------------------------


@pytest.fixture(scope="module")
def catalogue_graph():
    rdflib = pytest.importorskip("rdflib")
    graph = rdflib.Graph()
    graph.parse(REPO / "public/catalog/dataset-cofog-1999.ttl", format="turtle")
    return graph


DATASET_URI = "https://data.publicinformation.ie/dataset/cofog-1999"


def test_catalogue_describes_the_vocabulary(catalogue_graph):
    from rdflib import RDF, URIRef
    from rdflib.namespace import DCTERMS

    dataset = URIRef(DATASET_URI)
    assert (dataset, RDF.type, URIRef("http://www.w3.org/ns/dcat#Dataset")) in catalogue_graph
    distributions = list(catalogue_graph.objects(
        dataset, URIRef("http://www.w3.org/ns/dcat#distribution")))
    assert len(distributions) == 3
    media_types = {str(catalogue_graph.value(d, URIRef(
        "http://www.w3.org/ns/dcat#mediaType"))) for d in distributions}
    assert media_types == {"application/json", "text/csv", "text/turtle"}
    assert str(catalogue_graph.value(dataset, DCTERMS.source)) == (
        "https://unstats.un.org/unsd/classifications/Econ/Download/"
        "In%20Text/COFOG_english_structure.txt")
    assert str(catalogue_graph.value(dataset, DCTERMS.license)) == LICENSE
    assert str(catalogue_graph.value(dataset, URIRef(
        "http://www.w3.org/2002/07/owl#versionInfo"))) == "1999"
    assert catalogue_graph.value(dataset, DCTERMS.relation) == URIRef(
        "https://data.publicinformation.ie/dataset/spc-meetings")


def _catalogue_distribution_paths() -> list[str]:
    from rdflib import Graph, URIRef

    graph = Graph()
    graph.parse(REPO / "public/catalog/dataset-cofog-1999.ttl", format="turtle")
    dcat = "http://www.w3.org/ns/dcat#"
    paths = []
    for node in graph.objects(URIRef(DATASET_URI), URIRef(dcat + "distribution")):
        url = str(graph.value(node, URIRef(dcat + "accessURL")))
        assert url.startswith("https://data.publicinformation.ie/")
        paths.append(url.removeprefix("https://data.publicinformation.ie/"))
    return paths


def test_catalogue_distributions_point_at_committed_files():
    for path in _catalogue_distribution_paths():
        assert (REPO / "public" / path).exists(), path


def test_both_readmes_link_the_vocabulary_readme():
    assert "vocabularies/cofog-1999.md" in (
        REPO / "public/README.md").read_text(encoding="utf-8")
    assert "vocabularies/cofog-1999.md" in (
        REPO / "public/latest/spc-meetings/README.md").read_text(encoding="utf-8")


def test_vocabulary_readme_links_resolve():
    text = (OUT_DIR / "cofog-1999.md").read_text(encoding="utf-8")
    targets = re.findall(r"\]\(([^)#]+?)\)", text)
    for target in targets:
        if target.startswith("http"):
            continue
        resolved = posixpath.normpath(posixpath.join("public/vocabularies", target))
        assert (REPO / resolved).exists(), target


def test_data_sources_names_the_formats_source_and_licence():
    text = (REPO / "DATA_SOURCES.md").read_text(encoding="utf-8")
    for name in ("cofog-1999.json", "cofog-1999.csv", "cofog-1999.ttl"):
        assert name in text, name
    assert "COFOG_english_structure.txt" in text
    assert "creativecommons.org/licenses/by/4.0/" in text


def test_changelog_names_the_formats_resolver_and_the_no_spc_change():
    text = (REPO / "public/CHANGELOG.md").read_text(encoding="utf-8")
    for needle in ("cofog-1999.json", "cofog-1999.ttl", "cofog-1999.md",
                   "ns/cofog", "No published SPC record changes"):
        assert needle in text, needle


# --- Cross-distribution agreement -------------------------------------------


def test_json_csv_and_turtle_code_sets_agree(outputs, turtle_graph, vocabulary):
    from rdflib.namespace import SKOS

    json_codes = {c["code"] for c in json.loads(outputs["cofog-1999.json"])["concepts"]}
    csv_codes = {row["notation"] for row in csv.DictReader(
        outputs["cofog-1999.csv"].decode("utf-8").splitlines())}
    ttl_codes = {str(o) for o in turtle_graph.objects(None, SKOS.notation)}
    assert json_codes == csv_codes == ttl_codes
    assert len(json_codes) == 188

