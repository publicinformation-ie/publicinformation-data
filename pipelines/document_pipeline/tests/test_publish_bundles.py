"""Tests for the publish_bundles step.

Reproducibility is the load-bearing guarantee here (contract §7): the web
repo's skip-if-unchanged cache keys on `bundle_sha256`, so two runs over
identical inputs must produce byte-identical `.tar.gz` files. The trap is any
wall-clock timestamp leaking into the archive — `built_at` is therefore
derived from `fetch_pdfs`'s `fetched_at` (itself only set when a PDF is
actually re-fetched), never from `datetime.now()`.
"""

import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path

import pytest

from lib.file_utils import IncrementalWriter
from steps.publish_bundles.process import (
    CONTRACT_VERSION,
    build_bundle_bytes,
    build_full_md,
    build_llms_txt,
    bundle_entries,
    contract_meta,
    index_entry,
    process,
)

DOC = "fixture-doc"
DOC_TITLE = "Fixture Transport Strategy"
SOURCE_URL = "https://example.org/fixture.pdf"

SECTION_MD = """---
title: "1.1 Introduction"
doc: fixture-doc
doc_title: "Fixture Transport Strategy"
chapter: 1-first-chapter
chapter_title: "1 First Chapter"
section: 1-1-introduction
order: 101
source_pages: [2, 2]
source_url: "https://example.org/fixture.pdf"
public_body_id: 1570
assets: ["p003-f01.webp"]
---

Walking is available.

![Figure 1.1 A vector diagram](assets/p003-f01.webp)
*Figure 1.1 A vector diagram*
"""


@pytest.fixture
def record():
    """One assemble_sections result: one chapter, one section, one asset,
    fully covered (publishable)."""
    return {
        "doc_slug": DOC,
        "doc_title": DOC_TITLE,
        "source_url": SOURCE_URL,
        "page_count": 4,
        "public_body_id": 1570,
        "detection_method": "numbering",
        "sections_dir": f"sections/{DOC}",
        "chapters": [
            {
                "slug": "1-first-chapter", "title": "1 First Chapter", "order": 100,
                "source_pages": [2, 2],
                "sections": [{
                    "slug": "1-1-introduction", "title": "1.1 Introduction", "order": 101,
                    "file": f"sections/{DOC}/1-first-chapter/1-1-introduction.md",
                    "source_pages": [2, 2], "word_count": 24,
                    "assets": ["p003-f01.webp"],
                }],
            },
        ],
        "coverage": {"page_count": 4, "covered": [1, 2, 3, 4], "gaps": [], "overlaps": [],
                     "empty_sections": []},
        "publishable": True,
    }


@pytest.fixture
def not_publishable_record(record):
    bad = json.loads(json.dumps(record))
    bad["doc_slug"] = "broken-doc"
    bad["coverage"]["gaps"] = [3]
    bad["publishable"] = False
    return bad


@pytest.fixture
def figures_record():
    return {"doc_slug": DOC, "figures": [
        {"id": "p003-f01", "kind": "figure", "page": 3, "bbox": [72, 130, 320, 300],
         "y": 130.0, "asset": f"assets/{DOC}/p003-f01.webp",
         "caption": "Figure 1.1 A vector diagram", "alt": "Figure 1.1 A vector diagram",
         "width": 496, "height": 340},
        {"id": "p003-f99", "kind": "figure", "page": 3, "bbox": [72, 500, 320, 600],
         "y": 500.0, "asset": f"assets/{DOC}/p003-f99.webp",
         "caption": "Unused figure", "alt": "Unused figure", "width": 100, "height": 100},
    ]}


@pytest.fixture
def fetch_record():
    return {"doc_slug": DOC, "title": DOC_TITLE, "url": SOURCE_URL,
            "publisher": "Test Authority", "public_body_id": 1570,
            "published_date": "2023-01-19", "source_sha256": "a" * 64,
            "bytes": 4349, "page_count": 4, "encrypted": False,
            "fetched_at": "2026-08-10T09:00:00Z", "pdf_path": f"pdfs/{DOC}.pdf"}


@pytest.fixture
def assemble_dir(tmp_path, record):
    d = tmp_path / "assemble_sections"
    section_file = d / record["chapters"][0]["sections"][0]["file"]
    section_file.parent.mkdir(parents=True)
    section_file.write_text(SECTION_MD, encoding="utf-8")
    return d


@pytest.fixture
def figures_dir(tmp_path):
    d = tmp_path / "extract_figures"
    assets = d / "assets" / DOC
    assets.mkdir(parents=True)
    (assets / "p003-f01.webp").write_bytes(b"RIFF-fake-webp-01")
    (assets / "p003-f99.webp").write_bytes(b"RIFF-fake-webp-99")
    return d


def run_process(tmp_path, records, figures_by_doc, fetched_by_doc, assemble_dir, figures_dir,
                 force=True, doc_slug=None):
    step_dir = tmp_path / "publish_bundles"
    step_dir.mkdir(parents=True, exist_ok=True)
    public_root = tmp_path / "public" / "documents"
    writer = IncrementalWriter(step_dir / "output.json", "publish_bundles",
                               key_field="doc_slug", force=force)
    process(records, figures_by_doc, fetched_by_doc, assemble_dir, figures_dir,
            step_dir, public_root, writer, doc_slug=doc_slug)
    writer.finalize()
    return step_dir, public_root


# --- index.json ---------------------------------------------------------

def test_index_json_matches_contract_shape_and_lists_one_document(
        record, figures_record, fetch_record, assemble_dir, figures_dir, tmp_path):
    _step_dir, public_root = run_process(
        tmp_path, [record], {DOC: figures_record}, {DOC: fetch_record},
        assemble_dir, figures_dir)

    index = json.loads((public_root / "index.json").read_text())
    assert index["version"] == CONTRACT_VERSION
    assert "generated_at" in index
    assert [d["doc_slug"] for d in index["documents"]] == [DOC]
    assert index["failed"] == []

    entry = index["documents"][0]
    assert entry["title"] == DOC_TITLE
    assert entry["publisher"] == "Test Authority"
    assert entry["public_body_id"] == 1570
    assert entry["source_url"] == SOURCE_URL
    assert entry["published_date"] == "2023-01-19"
    assert entry["page_count"] == 4
    assert entry["chapter_count"] == 1
    assert entry["section_count"] == 1
    assert entry["figure_count"] == 2
    assert entry["detection_method"] == "numbering"
    assert entry["bundle"] == f"{DOC}/bundle.tar.gz"
    assert entry["source_sha256"] == "a" * 64
    assert entry["built_at"] == "2026-08-10T09:00:00Z"
    assert len(entry["bundle_sha256"]) == 64
    assert entry["bundle_bytes"] > 0


def test_not_publishable_document_is_omitted_and_listed_as_failed(
        record, not_publishable_record, figures_record, fetch_record,
        assemble_dir, figures_dir, tmp_path):
    broken_fetch = dict(fetch_record, doc_slug="broken-doc")
    _step_dir, public_root = run_process(
        tmp_path, [record, not_publishable_record],
        {DOC: figures_record, "broken-doc": figures_record},
        {DOC: fetch_record, "broken-doc": broken_fetch},
        assemble_dir, figures_dir)

    index = json.loads((public_root / "index.json").read_text())
    assert [d["doc_slug"] for d in index["documents"]] == [DOC]
    assert len(index["failed"]) == 1
    failed = index["failed"][0]
    assert failed["doc_slug"] == "broken-doc"
    assert failed["reason"]
    assert failed["message"]
    assert not (public_root / "broken-doc").exists()


def test_regression_to_not_publishable_removes_the_stale_published_dir(
        record, not_publishable_record, figures_record, fetch_record,
        assemble_dir, figures_dir, tmp_path):
    """A doc_slug that published successfully on run 1 and then fails
    assemble_sections' coverage check on a rerun (--force) must not leave its
    old bundle.tar.gz/meta.json/full.md/llms.txt live under public_root —
    contract §3: 'a document that disappears from index.json should
    disappear from the site'."""
    same_slug_broken = json.loads(json.dumps(record))
    same_slug_broken["coverage"]["gaps"] = [3]
    same_slug_broken["publishable"] = False

    step_dir = tmp_path / "publish_bundles"
    step_dir.mkdir(parents=True, exist_ok=True)
    public_root = tmp_path / "public" / "documents"

    # Run 1: publishes successfully.
    writer1 = IncrementalWriter(step_dir / "output.json", "publish_bundles",
                                key_field="doc_slug", force=True)
    process([record], {DOC: figures_record}, {DOC: fetch_record},
           assemble_dir, figures_dir, step_dir, public_root, writer1)
    writer1.finalize()
    assert (public_root / DOC / "bundle.tar.gz").exists()
    index1 = json.loads((public_root / "index.json").read_text())
    assert [d["doc_slug"] for d in index1["documents"]] == [DOC]

    # Run 2: same doc_slug now fails coverage, --force reprocesses it.
    writer2 = IncrementalWriter(step_dir / "output.json", "publish_bundles",
                                key_field="doc_slug", force=True)
    process([same_slug_broken], {DOC: figures_record}, {DOC: fetch_record},
           assemble_dir, figures_dir, step_dir, public_root, writer2)
    writer2.finalize()

    assert not (public_root / DOC).exists()
    index2 = json.loads((public_root / "index.json").read_text())
    assert index2["documents"] == []
    assert [d["doc_slug"] for d in index2["failed"]] == [DOC]


def test_doc_slug_removed_from_current_run_prunes_its_stale_dir(
        record, figures_record, fetch_record, assemble_dir, figures_dir, tmp_path):
    """A doc_slug published on run 1 but absent from run 2's input entirely
    (e.g. deleted or renamed in documents.yml) must have its stale directory
    pruned, even though it was never marked failed."""
    step_dir = tmp_path / "publish_bundles"
    step_dir.mkdir(parents=True, exist_ok=True)
    public_root = tmp_path / "public" / "documents"

    writer1 = IncrementalWriter(step_dir / "output.json", "publish_bundles",
                                key_field="doc_slug", force=True)
    process([record], {DOC: figures_record}, {DOC: fetch_record},
           assemble_dir, figures_dir, step_dir, public_root, writer1)
    writer1.finalize()
    assert (public_root / DOC / "bundle.tar.gz").exists()

    # A stray directory not backed by any known doc_slug at all (e.g. a
    # manual leftover) must be pruned too.
    stray = public_root / "totally-unknown-doc"
    stray.mkdir(parents=True)
    (stray / "bundle.tar.gz").write_bytes(b"stale")

    # Run 2: the input no longer includes DOC at all (evicted upstream), and
    # writer2 is freshly force-initialized with no accumulated results, so
    # DOC never appears in writer2.results/index.json either.
    writer2 = IncrementalWriter(step_dir / "output.json", "publish_bundles",
                                key_field="doc_slug", force=True)
    process([], {}, {}, assemble_dir, figures_dir, step_dir, public_root, writer2)
    writer2.finalize()

    assert not (public_root / DOC).exists()
    assert not stray.exists()
    index2 = json.loads((public_root / "index.json").read_text())
    assert index2["documents"] == []
    assert index2["failed"] == []


# --- bundle interior ------------------------------------------------------

def _read_bundle(public_root, doc_slug=DOC):
    data = (public_root / doc_slug / "bundle.tar.gz").read_bytes()
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        return {member.name: tar.extractfile(member).read() for member in tar.getmembers()}


def test_bundle_contains_meta_llms_full_and_every_section_and_asset(
        record, figures_record, fetch_record, assemble_dir, figures_dir, tmp_path):
    _step_dir, public_root = run_process(
        tmp_path, [record], {DOC: figures_record}, {DOC: fetch_record},
        assemble_dir, figures_dir)

    members = _read_bundle(public_root)
    assert "meta.json" in members
    assert "llms.txt" in members
    assert "full.md" in members

    meta = json.loads(members["meta.json"])
    md_paths = {section["file"] for chapter in meta["chapters"] for section in chapter["sections"]}
    assert md_paths == {"sections/1-first-chapter/1-1-introduction.md"}
    for path in md_paths:
        assert path in members

    referenced_assets = {asset for chapter in meta["chapters"]
                          for section in chapter["sections"] for asset in section["assets"]}
    assert referenced_assets == {"p003-f01.webp"}
    for asset in referenced_assets:
        assert f"assets/{asset}" in members
    # the unused figure (p003-f99) is not referenced by any section and must
    # not be bundled
    assert "assets/p003-f99.webp" not in members


def test_every_md_in_bundle_is_listed_in_meta_json(
        record, figures_record, fetch_record, assemble_dir, figures_dir, tmp_path):
    _step_dir, public_root = run_process(
        tmp_path, [record], {DOC: figures_record}, {DOC: fetch_record},
        assemble_dir, figures_dir)

    members = _read_bundle(public_root)
    meta = json.loads(members["meta.json"])
    md_paths = {section["file"] for chapter in meta["chapters"] for section in chapter["sections"]}
    bundle_md = {name for name in members if name.startswith("sections/") and name.endswith(".md")}
    assert bundle_md == md_paths


def test_no_tar_entry_escapes_the_bundle(
        record, figures_record, fetch_record, assemble_dir, figures_dir, tmp_path):
    _step_dir, public_root = run_process(
        tmp_path, [record], {DOC: figures_record}, {DOC: fetch_record},
        assemble_dir, figures_dir)

    data = (public_root / DOC / "bundle.tar.gz").read_bytes()
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for member in tar.getmembers():
            assert ".." not in Path(member.name).parts
            assert not member.name.startswith("/")


def test_bundle_sha256_equals_sha256_of_bytes_on_disk(
        record, figures_record, fetch_record, assemble_dir, figures_dir, tmp_path):
    _step_dir, public_root = run_process(
        tmp_path, [record], {DOC: figures_record}, {DOC: fetch_record},
        assemble_dir, figures_dir)

    index = json.loads((public_root / "index.json").read_text())
    on_disk = (public_root / DOC / "bundle.tar.gz").read_bytes()
    assert index["documents"][0]["bundle_sha256"] == hashlib.sha256(on_disk).hexdigest()
    assert index["documents"][0]["bundle_bytes"] == len(on_disk)


def test_two_consecutive_runs_over_identical_inputs_produce_identical_hash(
        record, figures_record, fetch_record, assemble_dir, figures_dir, tmp_path):
    _step_dir1, public_root1 = run_process(
        tmp_path / "run1", [record], {DOC: figures_record}, {DOC: fetch_record},
        assemble_dir, figures_dir)
    _step_dir2, public_root2 = run_process(
        tmp_path / "run2", [record], {DOC: figures_record}, {DOC: fetch_record},
        assemble_dir, figures_dir)

    bytes1 = (public_root1 / DOC / "bundle.tar.gz").read_bytes()
    bytes2 = (public_root2 / DOC / "bundle.tar.gz").read_bytes()
    assert hashlib.sha256(bytes1).hexdigest() == hashlib.sha256(bytes2).hexdigest()
    assert bytes1 == bytes2


def test_meta_json_section_file_paths_resolve_inside_the_bundle(
        record, figures_record, fetch_record, assemble_dir, figures_dir, tmp_path):
    _step_dir, public_root = run_process(
        tmp_path, [record], {DOC: figures_record}, {DOC: fetch_record},
        assemble_dir, figures_dir)

    members = _read_bundle(public_root)
    meta = json.loads(members["meta.json"])
    for chapter in meta["chapters"]:
        for section in chapter["sections"]:
            assert section["file"] in members


def test_llms_txt_and_full_md_exist_both_inside_bundle_and_as_loose_files(
        record, figures_record, fetch_record, assemble_dir, figures_dir, tmp_path):
    _step_dir, public_root = run_process(
        tmp_path, [record], {DOC: figures_record}, {DOC: fetch_record},
        assemble_dir, figures_dir)

    members = _read_bundle(public_root)
    assert (public_root / DOC / "llms.txt").read_bytes() == members["llms.txt"]
    assert (public_root / DOC / "full.md").read_bytes() == members["full.md"]
    assert (public_root / DOC / "meta.json").exists()
    assert b"---\ntitle:" not in members["full.md"]


def test_version_is_present_and_equals_contract_version(
        record, figures_record, fetch_record, assemble_dir, figures_dir, tmp_path):
    _step_dir, public_root = run_process(
        tmp_path, [record], {DOC: figures_record}, {DOC: fetch_record},
        assemble_dir, figures_dir)
    index = json.loads((public_root / "index.json").read_text())
    assert index["version"] == CONTRACT_VERSION
    assert CONTRACT_VERSION == "1.0.0"


# --- pure builders ----------------------------------------------------------

def test_contract_meta_strips_doc_slug_segment_from_section_file(record, fetch_record):
    meta = contract_meta(record, fetch_record)
    section = meta["chapters"][0]["sections"][0]
    assert section["file"] == "sections/1-first-chapter/1-1-introduction.md"
    assert meta["coverage"] == {"page_count": 4, "gaps": [], "overlaps": []}
    assert meta["built_at"] == "2026-08-10T09:00:00Z"


def test_index_entry_counts_chapters_sections_and_figures(record, fetch_record, figures_record):
    meta = contract_meta(record, fetch_record)
    entry = index_entry(record, fetch_record, meta, figures_record,
                        bundle_rel_path=f"{DOC}/bundle.tar.gz",
                        bundle_sha256="x" * 64, bundle_bytes=123)
    assert entry["chapter_count"] == 1
    assert entry["section_count"] == 1
    assert entry["figure_count"] == 2


def test_build_full_md_concatenates_sections_in_order(record, fetch_record):
    meta = contract_meta(record, fetch_record)
    section_bodies = {"sections/1-first-chapter/1-1-introduction.md":
                       "Walking is available.\n"}
    full = build_full_md(meta, section_bodies)
    assert full.startswith(f"# {DOC_TITLE}")
    assert SOURCE_URL in full
    assert "Walking is available." in full


def test_build_full_md_strips_each_sections_frontmatter(record, fetch_record):
    """A section's file on disk carries frontmatter (needed inside the
    bundle's sections/ tree); full.md must not repeat it — the chapter and
    section headings already carry that information."""
    meta = contract_meta(record, fetch_record)
    section_bodies = {"sections/1-first-chapter/1-1-introduction.md": SECTION_MD}
    full = build_full_md(meta, section_bodies)
    assert "---\ntitle:" not in full
    assert "doc_title:" not in full
    assert "Walking is available." in full


def test_build_llms_txt_names_the_document(record, fetch_record):
    meta = contract_meta(record, fetch_record)
    llms = build_llms_txt(meta)
    assert DOC_TITLE in llms
    assert SOURCE_URL in llms


def test_bundle_entries_are_sorted_by_path(record, fetch_record):
    meta = contract_meta(record, fetch_record)
    section_bodies = {"sections/1-first-chapter/1-1-introduction.md": "body"}
    asset_bytes = {"p003-f01.webp": b"webp-bytes"}
    entries = bundle_entries(meta, section_bodies, asset_bytes, "llms", "full")
    names = [name for name, _ in entries]
    assert names == sorted(names)
    assert set(names) == {
        "meta.json", "llms.txt", "full.md",
        "sections/1-first-chapter/1-1-introduction.md", "assets/p003-f01.webp"}


def test_build_bundle_bytes_rejects_unsafe_arcnames():
    with pytest.raises(ValueError):
        build_bundle_bytes([("../escape.md", b"x")])
    with pytest.raises(ValueError):
        build_bundle_bytes([("/etc/passwd", b"x")])


def test_build_bundle_bytes_is_a_valid_reproducible_gzip():
    entries = [("meta.json", b'{"a":1}')]
    first = build_bundle_bytes(entries)
    second = build_bundle_bytes(entries)
    assert first == second
    with gzip.GzipFile(fileobj=io.BytesIO(first)) as gz:
        with tarfile.open(fileobj=io.BytesIO(gz.read())) as tar:
            pass  # opens cleanly as a real tar
