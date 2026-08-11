#!/usr/bin/env python3
"""Step: publish_bundles — pack each publishable document's sections and
assets into a reproducible `.tar.gz` bundle, plus the `index.json` library
manifest the web repo's seed fetches first.

Ninth and final data-side step. Consumes `assemble_sections/output.json` and
two further sibling fan-ins resolved by path, the way `assemble_sections`
itself resolves its own upstreams: `extract_figures/` for the WebP assets a
section's frontmatter references, and `fetch_pdfs/` for `publisher`,
`published_date` and `source_sha256` — provenance fields the contract's
`index.json` and `meta.json` both need but that exist nowhere downstream of
the fetch (`assemble_sections` only carries `doc_title`, `source_url` and
`public_body_id` forward, the frontmatter keys it needs for itself).

Output shape is fixed by `docs/superpowers/specs/2026-08-10-document-bundle-contract.md`
§3 (`index.json`) and §4 (bundle interior: `meta.json`, `llms.txt`, `full.md`,
`sections/`, `assets/`).

**Reproducibility (contract §7).** The web repo's skip-if-unchanged cache
keys on `bundle_sha256`, so the same PDF plus the same overrides must produce
byte-identical archives across runs. Two things would silently defeat that:
a naive `tarfile.open(mode="w:gz")`, which embeds the current time in the
gzip header, and any wall-clock timestamp inside the archive's own content.
The first is avoided by building the tar in memory and gzip-compressing it
explicitly with `mtime=0`; the second by deriving each document's `built_at`
from `fetch_pdfs`'s `fetched_at` rather than `datetime.now()` — `fetched_at`
only changes when the PDF is actually re-fetched, so an unrelated rerun
reproduces the same bundle exactly.

A document `assemble_sections` marked `publishable: false` is skipped here —
that is the point at which a coverage gap or overlap actually withholds a
document, per the contract's "never half-published" guarantee — and listed
under `index.json`'s `failed` with a reason and message instead.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import shutil
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from lib.cli_utils import add_doc_arg
from lib.file_utils import IncrementalWriter, append_error, read_json, write_json, write_status

STEP_NAME = "publish_bundles"

# SemVer over the bundle contract (docs/superpowers/specs/2026-08-10-document-bundle-contract.md
# §8), not over content. Bump MAJOR on a removed/retyped field, a changed slug
# rule or a changed bundle layout; MINOR on a new optional field or
# `detection_method` value. Coordinate with the web repo on any bump.
CONTRACT_VERSION = "1.0.0"

_UNSAFE_ARCNAME = re.compile(r"(^/|(^|/)\.\.(/|$))")
_FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


# --------------------------------------------------------------------------
# Pure builders: no disk I/O, so they're testable against hand-written
# fixtures the same way assemble_sections' build() is.
# --------------------------------------------------------------------------

def _bundle_relative_file(file_path: str, doc_slug: str) -> str:
    """`sections/<doc_slug>/<chapter>/<section>.md` (assemble_sections, a
    multi-document step directory) -> `sections/<chapter>/<section>.md`
    (a single-document bundle interior, contract §4)."""
    prefix = f"sections/{doc_slug}/"
    if not file_path.startswith(prefix):
        raise ValueError(f"unexpected section file path {file_path!r} for doc {doc_slug!r}")
    return "sections/" + file_path[len(prefix):]


def contract_meta(record: dict, fetch_record: dict) -> dict:
    """The bundle's `meta.json` (contract §4): the per-document record plus
    the navigation tree, with section `file` paths rewritten bundle-relative."""
    doc_slug = record["doc_slug"]
    chapters = []
    for chapter in record["chapters"]:
        sections = []
        for section in chapter["sections"]:
            sections.append({
                "slug": section["slug"],
                "title": section["title"],
                "order": section["order"],
                "file": _bundle_relative_file(section["file"], doc_slug),
                "source_pages": section["source_pages"],
                "word_count": section["word_count"],
                "assets": list(section["assets"]),
            })
        chapters.append({
            "slug": chapter["slug"],
            "title": chapter["title"],
            "order": chapter["order"],
            "source_pages": chapter["source_pages"],
            "sections": sections,
        })
    coverage = record["coverage"]
    return {
        "doc_slug": doc_slug,
        "title": record["doc_title"],
        "publisher": fetch_record.get("publisher"),
        "public_body_id": record["public_body_id"],
        "source_url": record["source_url"],
        "published_date": fetch_record.get("published_date"),
        "page_count": record["page_count"],
        "detection_method": record["detection_method"],
        "source_sha256": fetch_record.get("source_sha256"),
        # Pinned to the PDF fetch, not to this run — see the module docstring
        # on reproducibility.
        "built_at": fetch_record.get("fetched_at"),
        "chapters": chapters,
        "coverage": {"page_count": coverage["page_count"], "gaps": coverage["gaps"],
                     "overlaps": coverage["overlaps"]},
    }


def index_entry(record: dict, fetch_record: dict, meta: dict, figures_record: dict,
                bundle_rel_path: str, bundle_sha256: str, bundle_bytes: int) -> dict:
    """One `index.json` `documents[]` entry (contract §3)."""
    section_count = sum(len(c["sections"]) for c in meta["chapters"])
    return {
        "doc_slug": meta["doc_slug"],
        "title": meta["title"],
        "publisher": meta["publisher"],
        "public_body_id": meta["public_body_id"],
        "source_url": meta["source_url"],
        "published_date": meta["published_date"],
        "page_count": meta["page_count"],
        "chapter_count": len(meta["chapters"]),
        "section_count": section_count,
        "figure_count": len((figures_record or {}).get("figures", [])),
        "detection_method": meta["detection_method"],
        "bundle": bundle_rel_path,
        "bundle_sha256": bundle_sha256,
        "bundle_bytes": bundle_bytes,
        "source_sha256": meta["source_sha256"],
        "built_at": meta["built_at"],
    }


def build_full_md(meta: dict, section_bodies: dict[str, str]) -> str:
    """The whole document as one Markdown file, so a model can ingest it in
    one fetch instead of walking every section URL. Each section's YAML
    frontmatter is stripped — headings carry that information here instead."""
    parts = [f"# {meta['title']}\n", f"Source: {meta['source_url']}\n"]
    for chapter in meta["chapters"]:
        parts.append(f"## {chapter['title']}\n")
        for section in chapter["sections"]:
            pages = section["source_pages"]
            body = _FRONTMATTER_RE.sub("", section_bodies[section["file"]]).strip()
            parts.append(f"### {section['title']}\n\n*Pages {pages[0]}–{pages[1]}*\n\n{body}\n")
    return "\n".join(parts)


def build_llms_txt(meta: dict) -> str:
    """A per-document `llms.txt` (contract §4 lists it inside every bundle,
    unlike the source design's single library-wide file — each bundle now
    ships standalone, so its own index travels with it)."""
    section_count = sum(len(c["sections"]) for c in meta["chapters"])
    lines = [
        f"# {meta['title']}",
        "",
        f"> {meta.get('publisher') or 'Unknown publisher'} — "
        f"{len(meta['chapters'])} chapters, {section_count} sections, "
        f"{meta['page_count']} source pages.",
        f"> Source: {meta['source_url']}",
        "> Full text: full.md",
        "",
        "## Chapters",
        "",
    ]
    for chapter in meta["chapters"]:
        pages = chapter["source_pages"]
        lines.append(f"- [{chapter['title']}](sections/{chapter['slug']}/) "
                     f"— pages {pages[0]}–{pages[1]}")
        for section in chapter["sections"]:
            spages = section["source_pages"]
            lines.append(f"  - [{section['title']}]({section['file']}) "
                         f"— pages {spages[0]}–{spages[1]}")
    return "\n".join(lines) + "\n"


def bundle_entries(meta: dict, section_bodies: dict[str, str], asset_bytes: dict[str, bytes],
                   llms_txt: str, full_md: str) -> list[tuple[str, bytes]]:
    """The bundle's file list, sorted by path (contract §7: reproducibility)."""
    entries = {
        "meta.json": json.dumps(meta, indent=2, ensure_ascii=False).encode("utf-8"),
        "llms.txt": llms_txt.encode("utf-8"),
        "full.md": full_md.encode("utf-8"),
    }
    for path, body in section_bodies.items():
        entries[path] = body.encode("utf-8")
    for name, data in asset_bytes.items():
        entries[f"assets/{name}"] = data
    return sorted(entries.items())


def _assert_safe_arcname(name: str) -> None:
    if _UNSAFE_ARCNAME.search(name):
        raise ValueError(f"unsafe archive path (escapes the bundle): {name!r}")


def build_bundle_bytes(entries: list[tuple[str, bytes]]) -> bytes:
    """Deterministic `.tar.gz` bytes: every mutable TarInfo field pinned, and
    a `mtime=0` gzip wrapper built by hand — `tarfile.open(mode="w:gz")`
    embeds the current time in the gzip header, which would defeat the
    reproducibility guarantee on every single run."""
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w", format=tarfile.GNU_FORMAT) as tar:
        for name, data in entries:
            _assert_safe_arcname(name)
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(data))

    gz_buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=gz_buffer, mode="wb", mtime=0, filename="") as gz:
        gz.write(tar_buffer.getvalue())
    return gz_buffer.getvalue()


# --------------------------------------------------------------------------
# process(): the disk I/O and per-document orchestration
# --------------------------------------------------------------------------

def _index_by_doc(path: Path) -> dict:
    if not Path(path).exists():
        return {}
    return {record["doc_slug"]: record
            for record in read_json(path).get("results", [])
            if "doc_slug" in record}


def _error_dict(error_type: str, message: str, context: dict) -> dict:
    return {"error_type": error_type, "message": message, "context": context}


def _write_document(record: dict, fetch_record: dict, figures_record: dict,
                    assemble_dir: Path, figures_dir: Path, public_root: Path) -> dict:
    """Build and write one document's bundle + loose files. Returns the
    index.json entry. Raises on any problem — the caller isolates failures
    per document."""
    doc_slug = record["doc_slug"]
    if re.search(r"(^\.\.$|/|\\)", doc_slug) or doc_slug in (".", ".."):
        raise ValueError(f"unsafe doc_slug: {doc_slug!r}")

    meta = contract_meta(record, fetch_record)

    section_bodies = {}
    for chapter in meta["chapters"]:
        for section in chapter["sections"]:
            # assemble_dir stores files under sections/<doc_slug>/..., meta's
            # path has already dropped the doc_slug segment (contract §4).
            source = assemble_dir / "sections" / doc_slug / section["file"][len("sections/"):]
            section_bodies[section["file"]] = source.read_text(encoding="utf-8")

    wanted_assets = sorted({asset for chapter in meta["chapters"]
                            for section in chapter["sections"] for asset in section["assets"]})
    asset_bytes = {}
    for name in wanted_assets:
        source = figures_dir / "assets" / doc_slug / name
        asset_bytes[name] = source.read_bytes()

    llms_txt = build_llms_txt(meta)
    full_md = build_full_md(meta, section_bodies)
    entries = bundle_entries(meta, section_bodies, asset_bytes, llms_txt, full_md)
    bundle = build_bundle_bytes(entries)
    bundle_sha256 = hashlib.sha256(bundle).hexdigest()

    doc_root = public_root / doc_slug
    if doc_root.resolve().parent != public_root.resolve():
        raise ValueError(f"computed document path escapes public_root: {doc_root}")
    doc_root.mkdir(parents=True, exist_ok=True)
    (doc_root / "bundle.tar.gz").write_bytes(bundle)
    (doc_root / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (doc_root / "llms.txt").write_text(llms_txt, encoding="utf-8")
    (doc_root / "full.md").write_text(full_md, encoding="utf-8")

    return index_entry(record, fetch_record, meta, figures_record,
                       bundle_rel_path=f"{doc_slug}/bundle.tar.gz",
                       bundle_sha256=bundle_sha256, bundle_bytes=len(bundle))


def _safe_doc_root(public_root: Path, doc_slug: str) -> Path:
    """Resolve `public_root/<doc_slug>`, raising if the slug isn't a plain,
    direct child name — same posture as the doc_slug/arcname safety checks
    above (`_write_document`, `_assert_safe_arcname`), applied here so a
    directory-removal path can never be tricked outside `public_root`."""
    if re.search(r"(^\.\.$|/|\\)", doc_slug) or doc_slug in (".", ".."):
        raise ValueError(f"unsafe doc_slug: {doc_slug!r}")
    doc_root = public_root / doc_slug
    if doc_root.resolve().parent != public_root.resolve():
        raise ValueError(f"computed document path escapes public_root: {doc_root}")
    return doc_root


def _remove_stale_doc_dir(public_root: Path, doc_slug: str) -> None:
    """Remove a document's published directory, if any. Called whenever a
    doc_slug is no longer among the current run's successfully-published or
    -failed set, so `bundle.tar.gz`/`meta.json`/`full.md`/`llms.txt` from a
    stale prior run never outlive their `index.json` entry (contract §3: "a
    document that disappears from index.json should disappear from the
    site")."""
    doc_root = _safe_doc_root(public_root, doc_slug)
    if doc_root.is_dir():
        shutil.rmtree(doc_root)


def _prune_orphaned_doc_dirs(public_root: Path, valid_slugs: set, step_dir: Path) -> None:
    """Remove any `public_root` subdirectory whose name isn't a slug present
    in this run's `index.json` (`documents[]` or `failed[]`). Covers a
    doc_slug being deleted from `documents.yml` entirely or renamed — not
    just the not-publishable regression handled inline in `process()` —
    without ever half-publishing (per-directory failures are logged and
    skipped, not fatal to the batch)."""
    if not public_root.is_dir():
        return
    for child in sorted(public_root.iterdir()):
        if not child.is_dir() or child.name in valid_slugs:
            continue
        try:
            _remove_stale_doc_dir(public_root, child.name)
        except Exception as e:
            append_error(step_dir, _error_dict(
                "PublishBundlesStaleDirRemovalFailed", str(e), {"doc_slug": child.name}))


def process(records, figures_by_doc, fetched_by_doc, assemble_dir, figures_dir,
           step_dir, public_root, writer, doc_slug=None, verbose=False):
    """Pack every publishable document into a bundle and (re)write
    `public/documents/index.json` from the full accumulated result set."""
    step_dir = Path(step_dir)
    assemble_dir = Path(assemble_dir)
    figures_dir = Path(figures_dir)
    public_root = Path(public_root)
    write_json(step_dir / "errors.json", [])

    documents = records
    if doc_slug is not None:
        documents = [r for r in documents if r["doc_slug"] == doc_slug]

    for record in documents:
        slug = record["doc_slug"]
        if writer.is_processed(slug):
            continue
        if verbose:
            print(f"  {slug} ...", end=" ", flush=True)

        if not record.get("publishable"):
            coverage = record["coverage"]
            writer.append([{
                "doc_slug": slug, "status": "failed", "reason": "not_publishable",
                "message": f"assemble_sections marked this document not publishable "
                          f"(gaps={coverage['gaps']}, overlaps={coverage['overlaps']})",
            }])
            # A document that published successfully on a prior run and now
            # regresses to not-publishable must not leave its old bundle
            # live at its old URL — see module docstring / contract §3.
            try:
                _remove_stale_doc_dir(public_root, slug)
            except Exception as e:
                append_error(step_dir, _error_dict(
                    "PublishBundlesStaleDirRemovalFailed", str(e), {"doc_slug": slug}))
            if verbose:
                print("[not publishable]", flush=True)
            continue

        fetch_record = fetched_by_doc.get(slug)
        figures_record = figures_by_doc.get(slug) or {"figures": []}
        if fetch_record is None:
            append_error(step_dir, _error_dict(
                "PublishBundlesFailed", "no fetch_pdfs record for this document",
                {"doc_slug": slug}))
            writer.append([])
            if verbose:
                print("[error]", flush=True)
            continue

        try:
            entry = _write_document(record, fetch_record, figures_record,
                                    assemble_dir, figures_dir, public_root)
        except Exception as e:
            # One document's bundle failing to build (a missing asset file, a
            # stale sibling record) must not abort the batch — same isolation
            # assemble_sections applies. Not marked processed, so a later run
            # retries it.
            append_error(step_dir, _error_dict(
                "PublishBundlesFailed", str(e), {"doc_slug": slug}))
            writer.append([])
            if verbose:
                print("[error]", flush=True)
            continue

        writer.append([{**entry, "status": "published"}])
        if verbose:
            print("published", flush=True)

    _write_index_json(writer.results, public_root)

    # General orphan-prune (contract §3, "never half-published"): remove any
    # public_root subdirectory that isn't a slug in the index we just wrote —
    # catches a doc_slug dropped from documents.yml entirely or renamed, on
    # top of the not-publishable regression handled above.
    valid_slugs = {r["doc_slug"] for r in writer.results
                  if r.get("status") in ("published", "failed")}
    _prune_orphaned_doc_dirs(public_root, valid_slugs, step_dir)


def _write_index_json(results: list, public_root: Path) -> None:
    published = sorted((r for r in results if r["status"] == "published"),
                       key=lambda r: r["doc_slug"])
    failed = sorted((r for r in results if r["status"] == "failed"),
                    key=lambda r: r["doc_slug"])
    index = {
        "version": CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "documents": [{k: v for k, v in r.items() if k != "status"} for r in published],
        "failed": [{k: v for k, v in r.items() if k != "status"} for r in failed],
    }
    public_root.mkdir(parents=True, exist_ok=True)
    write_json(public_root / "index.json", index)


def main():
    parser = argparse.ArgumentParser(
        description="Pack each publishable document into a reproducible bundle "
                    "and write public/documents/index.json")
    parser.add_argument("--input", required=True, help="Path to assemble_sections/output.json")
    parser.add_argument("--output", default=None, help="Path to write output.json")
    parser.add_argument("--force", action="store_true", help="Re-publish every document")
    parser.add_argument("--verbose", action="store_true", help="Print progress")
    parser.add_argument("--public-root", type=Path, default=None,
                        help="Override public/documents/ (defaults to the repo root's)")
    add_doc_arg(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output) if args.output else step_dir / "output.json"

    input_path = Path(args.input)
    records = read_json(input_path).get("results", [])

    # Fan-in, resolved the way assemble_sections resolves its own siblings.
    assemble_dir = input_path.resolve().parent
    steps_dir = assemble_dir.parent
    figures_by_doc = _index_by_doc(steps_dir / "extract_figures" / "output.json")
    fetched_by_doc = _index_by_doc(steps_dir / "fetch_pdfs" / "output.json")

    public_root = args.public_root or (step_dir.parents[3] / "public" / "documents")

    writer = IncrementalWriter(output_path, STEP_NAME, key_field="doc_slug",
                               force=args.force, target_key=args.doc)
    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")

    process(records, figures_by_doc, fetched_by_doc, assemble_dir,
           steps_dir / "extract_figures", step_dir, public_root, writer,
           doc_slug=args.doc, verbose=args.verbose)

    count = writer.finalize()
    write_status(step_dir, count)
    published = sum(1 for r in read_json(output_path).get("results", [])
                    if r.get("status") == "published")
    print(f"Wrote {published} of {len(records)} document bundle(s) to {public_root}")


if __name__ == "__main__":
    main()
