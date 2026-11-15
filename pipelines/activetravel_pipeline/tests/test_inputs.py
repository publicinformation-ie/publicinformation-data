"""The committed inputs: the publication list, the recipient maps, and status."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

PIPELINE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = PIPELINE_DIR.parent.parent

from allocations import (  # noqa: E402
    DOC_KINDS, alias_key, flatten_documents, load_code_prefixes,
    load_publications, load_recipient_aliases, load_row_repairs,
)

PUBLIC_BODIES_CSV = REPO_ROOT / "public/latest/public-bodies/public-bodies.csv"


def test_five_years_2022_to_2026():
    publications = load_publications()
    assert [p["year"] for p in publications] == [2022, 2023, 2024, 2025, 2026]


def test_every_document_url_is_unique():
    urls = [d["url"] for d in flatten_documents(load_publications())]
    assert len(urls) == len(set(urls))


def test_no_year_lacks_a_project_table():
    for publication in load_publications():
        kinds = {kind for document in publication["documents"] for kind in document["kinds"]}
        assert "project_table" in kinds, publication["year"]


def test_document_kinds_are_from_the_closed_vocabulary():
    for document in flatten_documents(load_publications()):
        assert set(document["kinds"]) <= set(DOC_KINDS)


def test_the_2022_annex_is_a_programme_summary_and_nothing_else():
    annex = [d for d in flatten_documents(load_publications())
             if d["document_id"] == "nta-active-travel-2022-annex-1"]
    assert len(annex) == 1
    assert annex[0]["kinds"] == ["programme_summary"]


def test_2025_and_2026_carry_a_recipient_summary():
    for year in (2025, 2026):
        document = next(d for d in flatten_documents(load_publications()) if d["year"] == year)
        assert "recipient_summary" in document["kinds"]


def _public_bodies_register() -> dict[str, int]:
    """Name -> public_body_id from the committed public-bodies distribution."""
    import csv

    register = {}
    with open(PUBLIC_BODIES_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            register[" ".join(row["name"].split()).lower()] = row["id"]
    return register


def test_every_local_authority_alias_maps_to_a_published_public_body():
    aliases = load_recipient_aliases()
    register = _public_bodies_register()
    authorities = {r["canonical"] for r in aliases.values() if r["kind"] == "local_authority"}
    assert len(authorities) == 31, "the five documents cover 31 local authorities"
    for recipient in aliases.values():
        if recipient["kind"] != "local_authority":
            continue
        name = recipient["public_body_name"]
        assert " ".join(name.split()).lower() in register, (
            f"{recipient['canonical']} maps to {name!r}, which is not in the public-bodies register")


def test_aliases_are_unique_to_one_recipient():
    path = PIPELINE_DIR / "steps/resolve_recipients/recipient_aliases.json"
    data = json.loads(path.read_text())
    seen = {}
    for recipient in data["recipients"]:
        for alias in [recipient["canonical"], *recipient.get("aliases", [])]:
            key = alias_key(alias)
            assert key not in seen or seen[key] == recipient["canonical"], (
                f"{alias!r} is claimed by {seen[key]!r} and {recipient['canonical']!r}")
            seen[key] = recipient["canonical"]


def test_every_declared_recipient_has_a_prefix_that_reaches_it():
    prefixes = load_code_prefixes()
    aliases = load_recipient_aliases()
    named = {r["canonical"] for r in aliases.values()}
    for prefix, entry in prefixes.items():
        assert entry["recipients"], prefix
        for recipient in entry["recipients"]:
            assert recipient in named, f"{prefix} names undeclared recipient {recipient!r}"
    covered = {r for entry in prefixes.values() for r in entry["recipients"]}
    assert named - covered == set(), "every recipient needs at least one code prefix"


def test_prefixes_that_must_be_unique_are():
    prefixes = load_code_prefixes()
    for prefix in ("KCC", "KK", "WCC", "FCC", "SDCC", "DCC"):
        assert len(prefixes[prefix]["recipients"]) == 1, prefix


def test_lcc_is_the_only_genuine_collision_and_is_documented():
    prefixes = load_code_prefixes()
    shared = {p for p, e in prefixes.items() if len(e["recipients"]) > 1}
    assert shared == {"LCC"}
    assert set(prefixes["LCC"]["recipients"]) == {
        "Limerick City and County Council", "Louth County Council"}
    assert prefixes["LCC"]["note"]


def test_the_document_cache_is_git_ignored_and_documented():
    import subprocess

    result = subprocess.run(
        ["git", "check-ignore", "-q",
         "pipelines/activetravel_pipeline/cache/0000000000000000.pdf"],
        cwd=REPO_ROOT)
    assert result.returncode == 0, "the downloaded documents must never be committed"
    readme = (PIPELINE_DIR / "README.md").read_text(encoding="utf-8")
    step_readme = (PIPELINE_DIR / "steps/fetch_grant_documents/README.md").read_text(encoding="utf-8")
    for text in (readme, step_readme):
        assert "pipelines/activetravel_pipeline/cache/" in text


def test_row_repairs_are_manual_and_keyed():
    repairs = load_row_repairs()
    assert repairs, "the 2022 overflow cells need their confirmed repairs"
    for repair in repairs:
        assert repair["source_method"] == "manual" and repair["overridden"] is True
        assert repair["action"] in ("set_amount", "drop_row")
        assert isinstance(repair["value"], int) or repair["action"] == "drop_row"
        assert repair["reason"]


def _write_status_fixture(tmp_path: Path, steps: list[str],
                          overrides: dict[str, dict]) -> None:
    (tmp_path / "steps").mkdir()
    for step in steps:
        step_dir = tmp_path / "steps" / step
        step_dir.mkdir()
        payload = overrides.get(step)
        if payload is None:
            payload = {"rows": [{"document_id": "nta-active-travel-2026",
                                 "kind": "project", "year": 2026}]}
        (step_dir / "output.json").write_text(json.dumps(payload))
    (tmp_path / "pipeline.json").write_text(json.dumps({"steps": steps}))


def _steps() -> list[str]:
    return json.loads((PIPELINE_DIR / "pipeline.json").read_text())["steps"]


def test_status_exits_zero_on_a_completed_run(tmp_path, capsys):
    """A completed run: every document carries project rows to the export."""
    from status import main

    _write_status_fixture(tmp_path, _steps(), {
        "fetch_grant_documents": {"documents": [
            {"document_id": "nta-active-travel-2026", "year": 2026,
             "kinds": ["project_table"], "available": True, "source": "cache",
             "byte_size": 10}]},
        "extract_grant_tables": {"rows": [{"document_id": "nta-active-travel-2026"}],
                                 "summary_rows": [], "pages": [
                                     {"document_id": "nta-active-travel-2026", "accepted": True}]},
        "export_allocations": {"results": [{"year": 2026, "allocation_eur": 100}]},
    })

    assert main(["--all"], pipeline_dir=tmp_path) == 0
    assert "flowing" in capsys.readouterr().out


def test_status_names_the_first_dry_step(tmp_path, capsys):
    """A truncated run: the classifier produced no rows, so nothing flows."""
    from status import main

    _write_status_fixture(tmp_path, _steps(), {
        "fetch_grant_documents": {"documents": [
            {"document_id": "nta-active-travel-2026", "year": 2026,
             "kinds": ["project_table"], "available": True}]},
        "classify_grant_rows": {"rows": [], "unknown_rows": []},
        "export_allocations": {"results": []},
    })

    assert main(["--document", "2026"], pipeline_dir=tmp_path) == 1
    assert "Runs dry at: classify" in capsys.readouterr().out


def test_status_ignores_the_programme_summary_document(tmp_path, capsys):
    """The 2022 annex is cached for provenance and is never 'dry'."""
    from status import main

    _write_status_fixture(tmp_path, _steps(), {
        "fetch_grant_documents": {"documents": [
            {"document_id": "nta-active-travel-2022", "year": 2022,
             "kinds": ["project_table"], "available": True},
            {"document_id": "nta-active-travel-2022-annex-1", "year": 2022,
             "kinds": ["programme_summary"], "available": True}]},
        "extract_grant_tables": {"rows": [{"document_id": "nta-active-travel-2022"}],
                                 "summary_rows": [], "pages": []},
        "export_allocations": {"results": [{"year": 2022, "allocation_eur": 100}]},
    })

    assert main(["--document", "nta-active-travel-2022-annex-1"],
                pipeline_dir=tmp_path) == 0
    assert "programme summary" in capsys.readouterr().out
