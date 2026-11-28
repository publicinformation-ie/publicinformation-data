import json
from pathlib import Path

import jsonschema
import pytest

from scripts.transform_spc_meetings import (
    build_outputs,
    build_records,
    csv_bytes,
    csvw_metadata,
    mirror_to_latest,
    write_if_changed,
)

REPO = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((REPO / "public/schemas/spc-meetings.schema.json").read_text())
BODY_LOOKUP = {1511: "meath-county-council"}


def _export():
    return {
        "meetings": [{
            "meeting_id": "meath/transportation-urban-regeneration/2026-02-19",
            "committee_id": "meath/transportation-urban-regeneration",
            "committee_name": "Transportation & Urban Regeneration Strategic Policy Committee",
            "public_body_id": 1511,
            "meeting_date": "2026-02-19",
            "venue": "Swift Room",
            "start_time": "2.30 pm",
            "end_time": "16.10 pm",
            "source_url": "https://www.meath.ie/x.pdf",
            "source_sha256": "a" * 64,
            "minutes_path": ("minutes/meath/transportation-urban-regeneration/"
                             "2026-02-19.md"),
            "attendance_published": True,
            "text_source": "text_layer",
            "ocr_engine": None,
        }],
        "people": [{
            "person_id": "meath/michael-bray",
            "canonical_name": "Mike Bray",
            "kind": "councillor",
            "councillor_id": "meath/michael-bray",
            "public_body_id": 1511,
        }],
        "attendance": [{
            "meeting_id": "meath/transportation-urban-regeneration/2026-02-19",
            "meeting_date": "2026-02-19",
            "person_id": "meath/michael-bray",
            "category": "councillors",
            "role": "Chair",
            "status": "present",
            "mode": "not_stated",
            "presented": False,
        }],
        "items": [{
            "item_id": "meath/transportation-urban-regeneration/2026-02-19/item-2-0",
            "meeting_id": "meath/transportation-urban-regeneration/2026-02-19",
            "item_number": "2.0",
            "item_key": "item-2-0",
            "title": "Matters Arising from Minutes",
            "text": "It was agreed to circulate the policy.",
            "is_minutes_approval": False,
            "topics_published": True,
            "cofog": ["04.5.1"],
            "subdomains": ["infra/regional-local-roads"],
            "procedural": False,
        }],
        "decisions": [{
            "decision_id": "meath/transportation-urban-regeneration/2026-02-19/d01",
            "meeting_id": "meath/transportation-urban-regeneration/2026-02-19",
            "meeting_date": "2026-02-19",
            "item_number": "2.0",
            "item_key": "item-2-0",
            "decision_text": "It was agreed to circulate the policy.",
            "decision_type": "agreed",
            "proposer": "meath/michael-bray",
            "seconder": None,
            "proposer_unresolved": False,
            "seconder_unresolved": False,
        }],
        "minutes": [{
            "meeting_id": "meath/transportation-urban-regeneration/2026-02-19",
            "path": ("minutes/meath/transportation-urban-regeneration/"
                     "2026-02-19.md"),
            "markdown": "# Minutes\n",
        }],
        "report": {"meetings": 1, "people": 1, "attendance": 1, "items": 1,
                   "decisions": 1},
    }


def _records():
    return build_records(_export(), BODY_LOOKUP)


def test_records_get_stable_uris_and_body_links():
    records = _records()
    meeting = records["meetings"][0]
    assert meeting["@id"] == (
        "https://data.publicinformation.ie/spc-meetings/meeting/"
        "meath/transportation-urban-regeneration/2026-02-19"
    )
    assert meeting["public_body"] == "https://data.publicinformation.ie/body/meath-county-council"
    assert records["attendance"][0]["@id"].endswith(
        "/attendance/meath/transportation-urban-regeneration/2026-02-19/meath/michael-bray")
    assert records["decisions"][0]["@id"].endswith("/decision/"
                                                   "meath/transportation-urban-regeneration/"
                                                   "2026-02-19/d01")


def test_every_record_validates_against_the_schema():
    for kind, records in _records().items():
        assert records, kind
        for record in records:
            jsonschema.validate(record, SCHEMA)


def test_schema_accepts_the_new_terms_and_requires_the_provenance_fields():
    attendance = _records()["attendance"][0]
    for category, status in (("absent", "absent"), ("guests", "present")):
        jsonschema.validate({**attendance, "category": category, "status": status}, SCHEMA)
    meeting = _records()["meetings"][0]
    for field in ("text_source", "ocr_engine"):
        broken = {k: v for k, v in meeting.items() if k != field}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(broken, SCHEMA)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({**meeting, "text_source": "scanned"}, SCHEMA)


def test_schema_rejects_an_unknown_attendance_status():
    record = _records()["attendance"][0]
    record["status"] = "late"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(record, SCHEMA)


def test_schema_rejects_an_unpublished_cofog_code():
    record = _records()["items"][0]
    record["cofog"] = ["04.5.9"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(record, SCHEMA)


def test_schema_rejects_an_undeclared_field():
    record = _records()["decisions"][0]
    record["unexpected"] = "value"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(record, SCHEMA)


def test_decisions_csv_carries_the_item_key_and_unresolved_flags():
    text = csv_bytes("decisions", _records()["decisions"]).decode("utf-8")
    header = text.splitlines()[0].split(",")
    assert "item_key" in header
    assert "proposer_unresolved" in header
    assert "seconder_unresolved" in header
    assert "item-2-0" in text


def test_items_csv_carries_the_item_id():
    text = csv_bytes("items", _records()["items"]).decode("utf-8")
    assert text.splitlines()[0].split(",")[1] == "item_id"
    assert "2026-02-19/item-2-0" in text


def test_csvw_marks_pipe_separated_arrays():
    columns = {column["name"]: column for column in
               json.loads(csvw_metadata("items"))["tableSchema"]["columns"]}
    for field in ("cofog", "subdomains"):
        assert columns[field]["separator"] == "|"
        assert columns[field]["null"] == ""


def test_unresolvable_public_body_fails_publication():
    with pytest.raises(ValueError, match="does not resolve"):
        build_records(_export(), {})


def test_csv_joins_array_fields():
    text = csv_bytes("items", _records()["items"]).decode("utf-8")
    assert "04.5.1" in text
    assert "infra/regional-local-roads" in text
    header = text.splitlines()[0]
    assert header.startswith("id,item_id,meeting_id")
    assert text.splitlines()[1].split(",")[0].startswith(
        "https://data.publicinformation.ie/spc-meetings/item/")


def test_csvw_metadata_declares_real_datatypes_and_descriptions():
    for kind in ("meetings", "people", "attendance", "items", "decisions"):
        metadata = json.loads(csvw_metadata(kind))
        columns = {column["name"]: column
                   for column in metadata["tableSchema"]["columns"]}
        assert columns["id"]["datatype"] == "uri"
        assert columns["id"]["titles"] == "ID"
        assert all(column["description"] for column in columns.values())
    meetings = {c["name"]: c for c in
                json.loads(csvw_metadata("meetings"))["tableSchema"]["columns"]}
    assert meetings["public_body_id"]["datatype"] == "integer"
    assert meetings["meeting_date"]["datatype"] == "date"
    assert meetings["attendance_published"]["datatype"] == "boolean"


def test_boolean_cells_are_written_as_true_and_false():
    text = csv_bytes("meetings", _records()["meetings"]).decode("utf-8")
    assert text.splitlines()[1].endswith(",true,text_layer,")
    assert "True" not in text and "False" not in text


def _notations(name: str) -> set[str]:
    import csv as csv_module

    path = REPO / "public/vocabularies" / f"{name}.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["notation"] for row in csv_module.DictReader(handle)}


def test_published_vocabulary_notations_match_the_schema_enums():
    attendance = SCHEMA["$defs"]["attendance"]["properties"]
    assert _notations("spc-attendance-status") == set(attendance["status"]["enum"])
    assert _notations("spc-attendance-mode") == set(attendance["mode"]["enum"])
    assert _notations("spc-attendee-category") == set(attendance["category"]["enum"])
    meeting = SCHEMA["$defs"]["meeting"]["properties"]
    assert _notations("spc-text-source") == set(meeting["text_source"]["enum"])
    decisions = SCHEMA["$defs"]["decision"]["properties"]
    assert _notations("spc-decision-type") == set(decisions["decision_type"]["enum"])
    items = SCHEMA["$defs"]["item"]["properties"]
    assert _notations("cofog-1999") == set(items["cofog"]["items"]["enum"])
    assert _notations("transport-subdomain") == set(items["subdomains"]["items"]["enum"])


def _ttl(path: Path):
    path.write_text(
        '@prefix dct: <http://purl.org/dc/terms/> .\n'
        '@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n'
        '<https://data.publicinformation.ie/dataset/spc-meetings> dct:modified '
        '"2026-01-01"^^xsd:date ; .\n'
    )


def test_latest_mirrors_the_versioned_release_and_unchanged_rerun_is_a_noop(tmp_path):
    output_dir = tmp_path / "v1.1.0" / "spc-meetings"
    latest_dir = tmp_path / "latest" / "spc-meetings"
    ttl = tmp_path / "dataset.ttl"
    _ttl(ttl)

    export = _export()
    records = build_records(export, BODY_LOOKUP)
    generated = build_outputs(export, records, output_dir)
    assert write_if_changed(generated, ttl, output_dir) is True
    mirror_to_latest(output_dir, latest_dir)

    for path in generated:
        relative = path.relative_to(output_dir)
        assert path.read_bytes() == (latest_dir / relative).read_bytes()

    after_first = ttl.read_text()
    changed_again = write_if_changed(
        build_outputs(export, build_records(export, BODY_LOOKUP), output_dir),
        ttl, output_dir)
    assert changed_again is False
    assert ttl.read_text() == after_first


def test_stale_generated_files_are_deleted_and_count_as_a_change(tmp_path):
    output_dir = tmp_path / "v1.1.0" / "spc-meetings"
    ttl = tmp_path / "dataset.ttl"
    _ttl(ttl)
    export = _export()
    generated = build_outputs(export, build_records(export, BODY_LOOKUP), output_dir)
    assert write_if_changed(generated, ttl, output_dir) is True

    stale = output_dir / "minutes" / "meath" / "old" / "2024-01-01.md"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("# a meeting that later failed to render\n", encoding="utf-8")

    assert write_if_changed(generated, ttl, output_dir) is True
    assert not stale.exists()
    assert not stale.parent.exists()


def test_catalogue_parses_as_turtle():
    from rdflib import Graph, URIRef

    path = REPO / "public/catalog/dataset-spc-meetings.ttl"
    graph = Graph()
    graph.parse(path, format="turtle")
    dataset = URIRef("https://data.publicinformation.ie/dataset/spc-meetings")
    assert (dataset, None, None) in graph
    distributions = list(graph.objects(dataset, None))
    assert distributions


def test_discovery_pages_link_to_the_dataset():
    for relative in ("public/GET_THE_DATA.md", "public/README.md",
                     "public/get-the-data.html"):
        text = (REPO / relative).read_text(encoding="utf-8")
        assert "latest/spc-meetings/" in text, relative


def _real_records():
    from src.lib.body_refs import build_body_slug_lookup

    export = json.loads((REPO / "pipelines/spc_pipeline/steps/export_spc_meetings/output.json")
                        .read_text())["results"]
    bodies = json.loads((REPO / "pipelines/foi_pipeline/steps/find_public_bodies/output.json")
                        .read_text())["public_bodies"]
    seed = {int(key): value for key, value in json.loads(
        (REPO / "pipelines/foi_pipeline/steps/db_upload/slug_seed.json").read_text()).items()}
    return build_records(export, build_body_slug_lookup(bodies, seed))


@pytest.mark.skipif(
    not (REPO / "pipelines/spc_pipeline/steps/export_spc_meetings/output.json").exists(),
    reason="the export is a git-ignored pipeline output",
)
def test_every_real_exported_record_validates_and_links_its_body():
    export = json.loads((REPO / "pipelines/spc_pipeline/steps/export_spc_meetings/output.json")
                        .read_text())["results"]
    if any("text_source" not in meeting for meeting in export["meetings"]):
        pytest.skip("the local export predates schema 1.2.0 (no text_source); re-run export_spc_meetings")
    records = _real_records()
    for kind, rows in records.items():
        for record in rows:
            jsonschema.validate(record, SCHEMA)
            if "public_body" in record:
                assert record["public_body"].startswith(
                    "https://data.publicinformation.ie/body/")


@pytest.mark.skipif(
    not (REPO / "public/latest/spc-meetings").exists(),
    reason="the dataset has not been published in this checkout",
)
def test_published_latest_and_versioned_files_are_byte_identical():
    versioned = REPO / "public/v1.2.0/spc-meetings"
    latest = REPO / "public/latest/spc-meetings"
    versioned_files = sorted(p.relative_to(versioned) for p in versioned.rglob("*") if p.is_file())
    latest_files = sorted(p.relative_to(latest) for p in latest.rglob("*") if p.is_file())
    assert versioned_files == latest_files
    for relative in versioned_files:
        assert (versioned / relative).read_bytes() == (latest / relative).read_bytes()


def test_a_content_change_stamps_dct_modified(tmp_path):
    output_dir = tmp_path / "v1.1.0" / "spc-meetings"
    ttl = tmp_path / "dataset.ttl"
    _ttl(ttl)
    export = _export()
    assert write_if_changed(
        build_outputs(export, build_records(export, BODY_LOOKUP), output_dir),
        ttl, output_dir)

    export["items"][0]["title"] = "Matters Arising"
    assert write_if_changed(
        build_outputs(export, build_records(export, BODY_LOOKUP), output_dir),
        ttl, output_dir) is True
    assert "2026-01-01" not in ttl.read_text()


def _readme(tmp_path):
    outputs = build_outputs(_export(), _records(), tmp_path)
    return outputs[tmp_path / "README.md"].decode("utf-8")


def test_readme_states_the_real_coverage_not_all_authorities(tmp_path):
    text = _readme(tmp_path)
    assert ("- Meath County Council, Transportation & Urban Regeneration Strategic Policy "
            "Committee: 1 meeting, 2026-02-19 to 2026-02-19") in text
    assert "no other council or committee is published yet" in text
    assert "Irish local authorities" not in text


KILDARE_ID = "kildare/transport-mobility-open-spaces/2025-12-11"
ENGINE = "tesseract 5.5.2 lang=eng psm=4 dpi=300"


def _three_council_export():
    """The Meath export plus one Kildare (scanned) and one Westmeath (mixed) meeting."""
    import copy

    export = _export()
    template = export["meetings"][0]
    for council, committee, name, body, date, source, engine in (
        ("kildare", "transport-mobility-open-spaces",
         "Transport, Mobility and Open Spaces Strategic Policy Committee", 1456,
         "2025-12-11", "ocr", ENGINE),
        ("westmeath", "planning-regeneration-transportation",
         "Planning, Regeneration & Transportation Strategic Policy Committee", 1870,
         "2026-03-06", "mixed", ENGINE),
    ):
        meeting = copy.deepcopy(template)
        meeting.update(
            meeting_id=f"{council}/{committee}/{date}", committee_id=f"{council}/{committee}",
            committee_name=name, public_body_id=body, meeting_date=date,
            minutes_path=f"minutes/{council}/{committee}/{date}.md",
            text_source=source, ocr_engine=engine,
            source_url=f"https://example.ie/{council}.pdf")
        export["meetings"].append(meeting)
        export["minutes"].append({"meeting_id": meeting["meeting_id"],
                                  "path": meeting["minutes_path"], "markdown": "# Minutes\n"})
    return export


LOOKUP3 = {1511: "meath-county-council", 1456: "kildare-county-council",
           1870: "westmeath-county-council"}


def test_kildare_meeting_links_its_own_council_and_sits_under_its_own_slugs():
    records = build_records(_three_council_export(), LOOKUP3)
    kildare = next(m for m in records["meetings"] if m["meeting_id"] == KILDARE_ID)
    assert kildare["public_body"] == "https://data.publicinformation.ie/body/kildare-county-council"
    assert kildare["minutes_path"] == (
        "minutes/kildare/transport-mobility-open-spaces/2025-12-11.md")
    assert (kildare["text_source"], kildare["ocr_engine"]) == ("ocr", ENGINE)
    meath = next(m for m in records["meetings"] if m["meeting_id"].startswith("meath/"))
    assert meath["public_body"].endswith("/meath-county-council")
    assert (meath["text_source"], meath["ocr_engine"]) == ("text_layer", None)
    for record in records["meetings"]:
        jsonschema.validate(record, SCHEMA)


def test_the_published_minutes_land_under_each_councils_slugs(tmp_path):
    export = _three_council_export()
    outputs = build_outputs(export, build_records(export, LOOKUP3), tmp_path)
    for relative in ("minutes/kildare/transport-mobility-open-spaces/2025-12-11.md",
                     "minutes/westmeath/planning-regeneration-transportation/2026-03-06.md",
                     "minutes/meath/transportation-urban-regeneration/2026-02-19.md"):
        assert tmp_path / relative in outputs


def test_a_council_with_no_entry_stops_the_build(tmp_path):
    export = _three_council_export()
    export["meetings"][1]["committee_id"] = "galway/some-committee"
    with pytest.raises(ValueError, match="galway"):
        build_outputs(export, build_records(export, LOOKUP3), tmp_path)


def test_scanned_meeting_csv_row_gives_text_source_and_engine():
    records = build_records(_three_council_export(), LOOKUP3)
    lines = csv_bytes("meetings", records["meetings"]).decode().splitlines()
    assert lines[0].endswith(",attendance_published,text_source,ocr_engine")
    assert lines[1].endswith(",true,text_layer,")
    assert any(line.endswith(f",true,ocr,{ENGINE}") for line in lines[2:])


def test_readme_lists_every_council_and_states_what_verbatim_means_for_ocr(tmp_path):
    export = _three_council_export()
    text = build_outputs(export, build_records(export, LOOKUP3), tmp_path)[
        tmp_path / "README.md"].decode("utf-8")
    for council in ("Meath County Council", "Kildare County Council", "Westmeath County Council"):
        assert f"- {council}: https://" in text
    assert "Attribute as: *Source: Kildare County Council, Meath County Council, Westmeath" in text
    assert "verbatim to the OCR text" in text
    assert "source PDF, identified by" in text and "authoritative" in text
    assert "`spc-text-source`" in text
    assert "1 meeting, 2025-12-11 to 2025-12-11" in text


def test_readme_documents_fields_from_field_specs_and_null_semantics(tmp_path):
    from scripts.transform_spc_meetings import CSV_FIELDS, FIELD_SPECS

    text = _readme(tmp_path)
    for kind, fields in CSV_FIELDS.items():
        assert f"### {kind}" in text
        for field in fields:
            assert f"| `{field}` | {FIELD_SPECS[field][0]} |" in text
    for phrase in ("topics_published", "attendance_published", "pipe-joined",
                   "https://data.publicinformation.ie/dataset/spc-meetings"):
        assert phrase in text


def test_readme_names_the_people_and_attribution(tmp_path):
    text = _readme(tmp_path)
    assert "People named in this dataset" in text
    assert "Source: Meath County Council" in text
    assert "DATA_SOURCES.md" not in text  # not published, so it must not be the only pointer


def test_readme_links_the_vocabularies_as_the_published_readme_does(tmp_path):
    """The generator, not a hand edit, owns the vocabulary links in the README."""
    text = _readme(tmp_path)
    assert "[`cofog-1999`](../../vocabularies/cofog-1999.md)" in text
    related = next(line for line in text.splitlines() if line.startswith("Each table is published"))
    from scripts.transform_spc_meetings import OUTPUT_DIR

    repo = Path(__file__).resolve().parents[1]
    # The current release and its latest/ mirror; older releases are frozen.
    for published in (repo / OUTPUT_DIR / "README.md",
                      repo / "public/latest/spc-meetings/README.md"):
        lines = published.read_text(encoding="utf-8").splitlines()
        assert related in lines, published


def test_minutes_have_a_resolvable_index_and_the_catalogue_links_to_it(tmp_path):
    outputs = build_outputs(_export(), _records(), tmp_path)
    index = outputs[tmp_path / "minutes" / "index.md"].decode("utf-8")
    assert "(meath/transportation-urban-regeneration/2026-02-19.md)" in index
    ttl = (REPO / "public/catalog/dataset-spc-meetings.ttl").read_text()
    assert "minutes/index.md" in ttl
    assert "spc-meetings/minutes/>" not in ttl


def test_catalogue_and_discovery_pages_state_the_real_scope():
    for relative in ("public/catalog/dataset-spc-meetings.ttl", "public/README.md",
                     "public/GET_THE_DATA.md", "public/get-the-data.html"):
        text = (REPO / relative).read_text(encoding="utf-8")
        assert "Meath County Council" in text, relative
