#!/usr/bin/env python3
"""Step: assemble_sections — cut cleaned blocks into per-section Markdown and
assert that no content vanished on the way.

**The ownership rule**, stated once because the coverage assertion depends on
it: every text block and every figure belongs to the **last section boundary
at or before its `(page, y)`**. A boundary's own heading block is excluded —
it is the boundary, not content underneath it, and it lives in the section's
frontmatter `title` rather than being repeated as a body heading. Content that
sits before the *first* boundary — a title page, a table of contents, any
front cover material every real PDF has — has no boundary to own it, so it is
assembled into a synthetic `front-matter` chapter and section (both slugged
`front-matter`, `order: 0`) rather than left uncovered. It is real content,
attributed to its real pages, so this is a legitimate section under the
contract §5 slug rules, not content manufactured from nothing. Because
ownership is otherwise total and exclusive, the coverage check that follows
is meaningful: a page that contributed nothing to any section is content that
went nowhere, which is exactly what a structure-detection miss looks like from
downstream, and a page claimed by two sections means the reading order or the
boundary set is wrong.

**Coverage sets `publishable`; it never aborts.** A document that fails the
check still gets its Markdown and its output record, marked
`publishable: false` with a `CoverageGap` / `CoverageOverlap` error naming the
pages. `publish_bundles` is what actually withholds it — the contract's
guarantee is that a document is never *half* published, not that a failure
stops the batch.

Output shape is fixed by `docs/superpowers/specs/2026-08-10-document-bundle-contract.md`
§4: the eleven frontmatter keys in `FRONTMATTER_KEYS`, bundle-relative
`assets/<figure-id>.webp` image paths, and a Markdown subset of ATX `##`–`####`
headings, paragraphs, `-`/`1.` lists, GFM pipe tables and images each followed
by an italic caption. The web repo writes a strict schema against exactly that
set, so an extra or renamed key breaks its build.

Ported from pdf2site's plan (source plan Task 12, lines 4021-4763): the
section cutting, figure interleaving, table rendering, complex-table demotion
and the coverage assertion. Adapted to:

  * keep the pure functions in this step's own process.py rather than a
    separate `assemble.py`, matching the convention the other steps in this
    pipeline already established;
  * emit the contract's eleven frontmatter keys rather than the source plan's
    older, smaller set, and bundle-relative `assets/<id>.webp` image paths
    rather than the source plan's site-absolute `/assets/<doc>/<id>.webp` —
    the consumer rewrites them, so the producer must not bake in a site path;
  * treat `overlaps` as pages claimed by two or more sections (the contract's
    "covered by exactly one section"), not the source plan's "more than two";
  * exclude a boundary's own heading from its ownership, so a chapter heading
    immediately followed by its first section heading does not silently claim
    that page and manufacture an overlap;
  * report `empty_sections` for section-level nodes only — a chapter with no
    preamble between its heading and its first section is normal, whereas a
    section heading that owns nothing is a real signal;
  * add the synthetic `front-matter` section the source plan calls for
    (line 4025) for content before the first detected boundary, matching the
    document-pipeline plan's own Data Contracts worked example, which shows
    page 1 as covered;
  * replace an in-cell newline with a space rather than the source plan's
    `<br>`: the contract's Markdown subset forbids raw HTML;
  * treat a per-document failure as an `AssembleSectionsFailed` errors.json
    entry that skips the document rather than aborting the run, the same
    isolation `extract_pages`, `extract_figures` and `clean_text` apply.
"""
import argparse
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from lib.cli_utils import add_doc_arg
from lib.file_utils import IncrementalWriter, append_error, read_json, write_json, write_status
from steps.detect_structure.process import SLUG_RE, slugify

STEP_NAME = "assemble_sections"

# --------------------------------------------------------------------------
# Assembly: pure functions over the three upstream JSON payloads
# --------------------------------------------------------------------------

# The contract, §4. Exactly these keys, in this order. The web repo's
# content-collection schema is written against this set: adding, renaming or
# dropping one is a MAJOR contract change (§8), not a tweak.
FRONTMATTER_KEYS = ("title", "doc", "doc_title", "chapter", "chapter_title",
                    "section", "order", "source_pages", "source_url",
                    "public_body_id", "assets")

# Free text and URLs are always quoted; slugs are bare, matching the contract's
# worked example byte for byte.
_ALWAYS_QUOTED = frozenset({"title", "doc_title", "chapter_title", "source_url"})

OVERVIEW = "overview"       # slug for a chapter's own preamble content
FRONT_MATTER = "front-matter"       # slug for content before the first boundary
FRONT_MATTER_TITLE = "Front Matter"
MAX_TABLE_COLUMNS = 12      # wider than this is a layout grid, not a table
MIN_HEADING_LEVEL = 2       # contract: ATX `##`-`####` only
MAX_HEADING_LEVEL = 4


@dataclass
class Section:
    slug: str
    chapter: str
    chapter_title: str
    title: str
    order: int
    file: str
    source_pages: list
    word_count: int
    assets: list
    markdown: str


@dataclass
class AssembleResult:
    sections: list = field(default_factory=list)
    chapters: list = field(default_factory=list)
    coverage: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)
    publishable: bool = True


def table_figure_id(page: int, index: int) -> str:
    """Join key between a `table` block from clean_text and the rasterised
    `kind: "table"` figure extract_figures made of the same region."""
    return f"p{int(page):03d}-t{int(index) + 1:02d}"


def asset_path(figure_id: str) -> str:
    """Bundle-relative image path. No leading slash, no `..` — the consumer
    rewrites these to whatever public path it chooses (contract §4)."""
    return f"assets/{figure_id}.webp"


def _cell(value) -> str:
    """A table cell, safe inside a pipe table. A newline becomes a space, not
    a `<br>`: the contract's Markdown subset forbids raw HTML."""
    return " ".join(str(value).replace("|", r"\|").split())


def render_table(rows: list):
    """GFM pipe table for a simple rectangular table, or `None` when the table
    must be demoted to its rasterised image. Ragged rows are what merged cells
    look like by the time they reach here, and there is no honest pipe-table
    rendering of a merged cell."""
    if not rows or len(rows) < 2:
        return None
    widths = {len(row) for row in rows}
    if len(widths) != 1:
        return None
    columns = widths.pop()
    if columns < 2 or columns > MAX_TABLE_COLUMNS:
        return None
    header, *body = rows
    lines = ["| " + " | ".join(_cell(c) for c in header) + " |",
             "| " + " | ".join("---" for _ in header) + " |"]
    lines += ["| " + " | ".join(_cell(c) for c in row) + " |" for row in body]
    return "\n".join(lines)


def _yaml_value(key: str, value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):                     # not in the contract's set
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(
            json.dumps(v, ensure_ascii=False) if isinstance(v, str) else str(v)
            for v in value) + "]"
    text = str(value)
    if key in _ALWAYS_QUOTED or not SLUG_RE.match(text):
        return json.dumps(text, ensure_ascii=False)
    return text


def frontmatter(fields: dict) -> str:
    """YAML frontmatter carrying exactly `FRONTMATTER_KEYS`. A missing or
    surplus key raises rather than silently shipping a payload the web repo's
    schema will reject."""
    surplus = set(fields) - set(FRONTMATTER_KEYS)
    missing = set(FRONTMATTER_KEYS) - set(fields)
    if surplus or missing:
        raise ValueError(
            f"frontmatter must carry exactly the contract's keys; "
            f"missing={sorted(missing)} surplus={sorted(surplus)}")
    lines = ["---"]
    lines += [f"{key}: {_yaml_value(key, fields[key])}" for key in FRONTMATTER_KEYS]
    lines.append("---")
    return "\n".join(lines)


def _titled(node: dict) -> str:
    number = node.get("number")
    return f"{number} {node['title']}".strip() if number else str(node["title"])


def _chapter_node(node: dict, by_slug: dict) -> dict:
    """Walk up to the level-1 ancestor. A node with no parent is its own
    chapter, so an orphaned section still lands somewhere."""
    current = node
    seen = {current["slug"]}
    while current.get("parent") and current["parent"] in by_slug:
        current = by_slug[current["parent"]]
        if current["slug"] in seen:
            break
        seen.add(current["slug"])
    return current


def _boundaries(nodes: list) -> list:
    return sorted(nodes, key=lambda n: (n["start_page"], n["start_y"], n["level"]))


def owner_index(page: int, y: float, boundaries: list) -> int:
    """Index of the last boundary at or before `(page, y)`; -1 when the item
    sits before the first boundary and therefore has no owning section."""
    owner = -1
    for index, node in enumerate(boundaries):
        if (node["start_page"], node["start_y"]) <= (page, y):
            owner = index
        else:
            break
    return owner


def _is_own_heading(item: dict, node: dict) -> bool:
    """True when this item is the heading that *is* the boundary. It titles
    the section rather than sitting inside it, so it is neither rendered nor
    counted as content."""
    if node is None or item["kind"] != "block":
        return False
    block = item["block"]
    if block["type"] != "heading":
        return False
    if item["page"] != node["start_page"]:
        return False
    return slugify(block["text"]) == node["slug"] or abs(block["y"] - node["start_y"]) < 1.0


def _heading_hashes(level) -> str:
    try:
        level = int(level)
    except (TypeError, ValueError):
        level = MIN_HEADING_LEVEL
    return "#" * min(MAX_HEADING_LEVEL, max(MIN_HEADING_LEVEL, level + 1))


def _figure_markdown(figure: dict) -> str:
    caption = figure.get("caption") or f"Figure from page {figure['page']}"
    alt = figure.get("alt") or caption
    return f"![{alt}]({asset_path(figure['id'])})\n\n*{caption}*"


def _caption_key(page: int, text: str) -> tuple:
    return (int(page), " ".join(str(text).split()).casefold())


def _render(items: list, figures_by_id: dict, errors: list, doc_slug: str):
    """Render one section's owned items in (page, y) order. Returns
    `(markdown_body, assets)`."""
    parts, assets, captions = [], [], set()
    for item in items:
        block = item["block"]
        if item["kind"] == "figure":
            parts.append({"page": item["page"], "text": _figure_markdown(block)})
            captions.add(_caption_key(item["page"], block.get("caption") or ""))
            assets.append(f"{block['id']}.webp")
            continue

        kind = block["type"]
        if kind == "heading":
            parts.append({"page": item["page"],
                          "text": f"{_heading_hashes(block.get('level'))} {block['text']}"})
        elif kind == "paragraph":
            # A caption line is still a paragraph as far as clean_text is
            # concerned — it has no knowledge of figures. This step is the
            # first place both facts are known, so it is where the duplicate
            # is removed: the caption is emitted once, italicised, under its
            # image, not a second time as stray prose.
            parts.append({"page": item["page"], "text": block["text"],
                          "caption_candidate": True})
        elif kind == "list":
            if block.get("ordered"):
                text = "\n".join(f"{n}. {entry}"
                                 for n, entry in enumerate(block["items"], 1))
            else:
                text = "\n".join(f"- {entry}" for entry in block["items"])
            parts.append({"page": item["page"], "text": text})
        elif kind == "table":
            rendered = render_table(block.get("text") or [])
            if rendered is not None:
                parts.append({"page": item["page"], "text": rendered})
                continue
            figure = figures_by_id.get(table_figure_id(item["page"], block.get("index", 0)))
            if figure is None:
                errors.append(_error_dict(
                    "TableDemotionFailed",
                    "Table is too complex for a GFM pipe table (merged or ragged "
                    "cells) and extract_figures rasterised no copy of it, so the "
                    "table is omitted from the section.",
                    {"doc_slug": doc_slug, "page": item["page"],
                     "table_index": block.get("index", 0)}))
                continue
            errors.append(_error_dict(
                "TableDemoted",
                "Table has merged or ragged cells; rendered as its rasterised "
                "image plus caption instead of a pipe table.",
                {"doc_slug": doc_slug, "page": item["page"], "figure": figure["id"]}))
            parts.append({"page": item["page"], "text": _figure_markdown(figure)})
            captions.add(_caption_key(item["page"], figure.get("caption") or ""))
            assets.append(f"{figure['id']}.webp")

    body = "\n\n".join(
        part["text"] for part in parts
        if not (part.get("caption_candidate")
                and _caption_key(part["page"], part["text"]) in captions))
    return body, assets


def coverage(pages_by_section: dict, page_count: int, empty_sections: list,
             raw_content_pages=(), intentional_empty_pages=()) -> dict:
    """The publication gate. `covered` is every page that contributed content
    to some section; a `gap` is a page that contributed to none (content that
    vanished); an `overlap` is a page claimed by two or more sections, which
    the contract, §7 forbids — every page must be covered by exactly one
    section.

    A gap page is `furniture` instead of a blocking gap only when BOTH the
    override names it AND it produced zero raw blocks/figures
    (`raw_content_pages`) — a page that failed the override's second half is
    left as a real gap, fail-safe against a stale override hiding actual
    content loss. See docs/superpowers/plans — assemble_sections/override.json,
    and pipelines/document_pipeline/steps/assemble_sections/README.md."""
    covered = sorted({page for pages in pages_by_section.values() for page in pages})
    all_gaps = [n for n in range(1, int(page_count) + 1) if n not in covered]
    furniture_pages = sorted(
        page for page in all_gaps
        if page in intentional_empty_pages and page not in raw_content_pages)
    gaps = [page for page in all_gaps if page not in furniture_pages]
    claims: dict = {}
    for pages in pages_by_section.values():
        for page in pages:
            claims[page] = claims.get(page, 0) + 1
    overlaps = sorted(page for page, count in claims.items() if count > 1)
    return {"page_count": int(page_count), "covered": covered, "gaps": gaps,
            "overlaps": overlaps, "empty_sections": sorted(empty_sections),
            "furniture_pages": furniture_pages}


def _error_dict(error_type: str, message: str, context: dict) -> dict:
    return {"step": STEP_NAME,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_type": error_type,
            "error_message": message,
            "context": context}


def build(structure: dict, figures: dict, clean: dict, doc_slug: str, doc_title: str,
          source_url: str, public_body_id=None,
          intentional_empty_pages: "list | None" = None) -> AssembleResult:
    """Cut one document's cleaned blocks into sections and render them."""
    nodes = list(structure.get("nodes") or [])
    by_slug = {n["slug"]: n for n in nodes}
    boundaries = _boundaries(nodes)
    page_count = int(structure.get("page_count") or len(clean.get("pages") or []))
    errors: list = []

    for page in sorted(p for p in (intentional_empty_pages or []) if not (1 <= p <= page_count)):
        errors.append(_error_dict(
            "OverridePageOutOfRange",
            f"override.json lists page {page} but this document has only "
            f"{page_count} pages; the entry cannot apply to this build.",
            {"doc_slug": doc_slug, "page": page, "page_count": page_count}))

    items = []
    for page in clean.get("pages") or []:
        for block in page.get("blocks") or []:
            items.append({"page": int(page["number"]), "y": float(block["y"]),
                          "kind": "block", "block": block})
    all_figures = list(figures.get("figures") or [])
    for figure in all_figures:
        if figure.get("kind") != "figure":
            # `table` figures are the demotion target for a complex table, not
            # standalone illustrations; they are placed by the table block.
            continue
        figure_page, figure_y = int(figure["page"]), float(figure["y"])
        if not (1 <= figure_page <= page_count) or figure_y < 0:
            # A bogus (page, y) — wherever it came from — must not silently
            # corrupt reading order here; extract_figures already filters
            # these, but this is the one place that consumes the coordinates,
            # so it gets its own check rather than trusting the producer.
            errors.append(_error_dict(
                "FigureOutOfBounds",
                "Figure page/y falls outside the document's page range; "
                "excluded from section ordering instead of risking a "
                "misplaced insertion.",
                {"doc_slug": doc_slug, "figure": figure.get("id"),
                 "page": figure_page, "y": figure_y, "page_count": page_count}))
            continue
        items.append({"page": figure_page, "y": figure_y,
                      "kind": "figure", "block": figure})
    items.sort(key=lambda item: (item["page"], item["y"]))
    figures_by_id = {f["id"]: f for f in all_figures}
    raw_content_pages = {item["page"] for item in items}
    override_pages = set(intentional_empty_pages or [])

    # One candidate section per boundary. A level-1 node that owns content
    # directly (a chapter preamble) becomes that chapter's `overview` section.
    keys = []
    owned: dict = {}
    for node in boundaries:
        chapter = _chapter_node(node, by_slug)
        slug = OVERVIEW if node is chapter else node["slug"]
        key = f"{chapter['slug']}/{slug}"
        keys.append((key, node, chapter, slug))
        owned[key] = []

    front_matter_items = []
    for item in items:
        index = owner_index(item["page"], item["y"], boundaries)
        if index < 0:
            # Before the first boundary: no section boundary owns it, so it
            # is assembled into the synthetic front-matter section below
            # rather than surfacing as a coverage gap.
            front_matter_items.append(item)
            continue
        owned[keys[index][0]].append(item)

    sections, pages_by_section, empty_sections = [], {}, []
    for key, node, chapter, slug in keys:
        content = [item for item in owned[key] if not _is_own_heading(item, node)]
        if not content:
            # A chapter with no preamble between its heading and its first
            # section is normal; a section heading that owns nothing is not.
            if node is not chapter:
                empty_sections.append(node["slug"])
            continue

        chapter_title = _titled(chapter)
        title = _titled(node)
        order = int(node["order"])
        pages = sorted({item["page"] for item in content})
        source_pages = [pages[0], pages[-1]]
        body, assets = _render(content, figures_by_id, errors, doc_slug)
        head = frontmatter({
            "title": title,
            "doc": doc_slug,
            "doc_title": doc_title,
            "chapter": chapter["slug"],
            "chapter_title": chapter_title,
            "section": slug,
            "order": order,
            "source_pages": source_pages,
            "source_url": source_url,
            "public_body_id": public_body_id,
            "assets": assets,
        })
        sections.append(Section(
            slug=slug, chapter=chapter["slug"], chapter_title=chapter_title,
            title=title, order=order,
            file=f"sections/{doc_slug}/{chapter['slug']}/{slug}.md",
            source_pages=source_pages, word_count=len(body.split()),
            assets=assets, markdown=f"{head}\n\n{body}\n"))
        pages_by_section[f"{chapter['slug']}/{slug}"] = pages

    if front_matter_items:
        # Content before the first detected boundary — a title page, a table
        # of contents — has no heading of its own to draw a title from, so it
        # gets a fixed one. `order: 0` sorts it ahead of every real chapter.
        pages = sorted({item["page"] for item in front_matter_items})
        source_pages = [pages[0], pages[-1]]
        body, assets = _render(front_matter_items, figures_by_id, errors, doc_slug)
        head = frontmatter({
            "title": FRONT_MATTER_TITLE,
            "doc": doc_slug,
            "doc_title": doc_title,
            "chapter": FRONT_MATTER,
            "chapter_title": FRONT_MATTER_TITLE,
            "section": FRONT_MATTER,
            "order": 0,
            "source_pages": source_pages,
            "source_url": source_url,
            "public_body_id": public_body_id,
            "assets": assets,
        })
        sections.append(Section(
            slug=FRONT_MATTER, chapter=FRONT_MATTER, chapter_title=FRONT_MATTER_TITLE,
            title=FRONT_MATTER_TITLE, order=0,
            file=f"sections/{doc_slug}/{FRONT_MATTER}/{FRONT_MATTER}.md",
            source_pages=source_pages, word_count=len(body.split()),
            assets=assets, markdown=f"{head}\n\n{body}\n"))
        pages_by_section[f"{FRONT_MATTER}/{FRONT_MATTER}"] = pages

    sections.sort(key=lambda s: (s.order, s.slug))

    chapters = []
    for chapter_slug in dict.fromkeys(s.chapter for s in sections):
        members = [s for s in sections if s.chapter == chapter_slug]
        chapter_pages = [p for s in members for p in s.source_pages]
        chapters.append({
            "slug": chapter_slug,
            "title": members[0].chapter_title,
            "order": int(by_slug[chapter_slug]["order"]) if chapter_slug in by_slug
                     else members[0].order,
            "source_pages": [min(chapter_pages), max(chapter_pages)],
            "sections": [{"slug": s.slug, "title": s.title, "order": s.order,
                          "file": s.file, "source_pages": s.source_pages,
                          "word_count": s.word_count, "assets": s.assets}
                         for s in members],
        })
    chapters.sort(key=lambda c: c["order"])

    report = coverage(pages_by_section, page_count, empty_sections,
                      raw_content_pages=raw_content_pages,
                      intentional_empty_pages=override_pages)
    for page in sorted(override_pages - set(report["furniture_pages"])):
        errors.append(_error_dict(
            "StaleFurnitureOverride",
            "This page is listed in override.json as an intentionally-empty "
            "furniture page, but is not a furniture-only gap for this build "
            "— either it now has content, or it was never actually a gap. "
            "Informational: does not block publication, but the override "
            "entry should be re-verified and removed if it no longer applies.",
            {"doc_slug": doc_slug, "page": page}))
    for page in report["gaps"]:
        errors.append(_error_dict(
            "CoverageGap",
            f"Page {page} contributed no content to any section. Content that "
            "reached no section is content that vanished — usually a "
            "structure-detection miss, or a page with no extractable content "
            "(pages before the first detected heading are covered by the "
            "synthetic front-matter section instead, so a gap there means the "
            "page had no blocks or figures at all). The document is not "
            "publishable.",
            {"doc_slug": doc_slug, "page": page, "gaps": report["gaps"]}))
    for page in report["overlaps"]:
        claimants = sorted(key for key, pages in pages_by_section.items() if page in pages)
        errors.append(_error_dict(
            "CoverageOverlap",
            f"Page {page} is claimed by {len(claimants)} sections; the contract "
            "requires every page to be covered by exactly one. The document is "
            "not publishable.",
            {"doc_slug": doc_slug, "page": page, "sections": claimants}))
    for slug in report["empty_sections"]:
        errors.append(_error_dict(
            "EmptySection",
            "Section boundary owns no text or figures. Informational: an empty "
            "section does not by itself block publication.",
            {"doc_slug": doc_slug, "section": slug}))

    return AssembleResult(
        sections=sections, chapters=chapters, coverage=report, errors=errors,
        publishable=not report["gaps"] and not report["overlaps"])


# --------------------------------------------------------------------------
# Step
# --------------------------------------------------------------------------

def _index_by_doc(path: Path) -> dict:
    if not Path(path).exists():
        return {}
    return {record["doc_slug"]: record
            for record in read_json(path).get("results", [])
            if "doc_slug" in record}


def _load_overrides(step_dir: Path) -> dict:
    """`{doc_slug: [page, ...]}` — pages a human has verified produce zero raw
    blocks/figures by design (a chapter-divider art page, not a
    structure-detection miss). See `coverage()` for the fail-safe: an entry
    here only suppresses a gap when the page is *also* actually raw-content-
    empty for this build."""
    path = Path(step_dir) / "override.json"
    if not path.exists():
        return {}
    return read_json(path)


def process(clean_records, structures, figures, meta, step_dir, writer,
            doc_slug=None, verbose=False):
    """Assemble every document's sections and write one Markdown file each."""
    step_dir = Path(step_dir)
    write_json(step_dir / "errors.json", [])
    overrides = _load_overrides(step_dir)

    documents = clean_records
    if doc_slug is not None:
        documents = [r for r in documents if r["doc_slug"] == doc_slug]

    for record in documents:
        slug = record["doc_slug"]
        if writer.is_processed(slug):
            continue
        if verbose:
            print(f"  {slug} ...", end=" ", flush=True)

        try:
            structure = structures.get(slug)
            if structure is None:
                raise ValueError(
                    "no detect_structure record for this document; "
                    "assemble_sections cannot cut sections without boundaries")
            document = meta.get(slug) or {}
            result = build(
                structure, figures.get(slug) or {"figures": []}, record,
                doc_slug=slug,
                doc_title=document.get("doc_title") or slug,
                source_url=document.get("source_url") or "",
                public_body_id=document.get("public_body_id"),
                intentional_empty_pages=overrides.get(slug))

            doc_dir = step_dir / "sections" / slug
            if doc_dir.exists():
                shutil.rmtree(doc_dir)      # never leave a stale section behind
            for section in result.sections:
                target = step_dir / section.file
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(section.markdown, encoding="utf-8")
        except Exception as e:
            # One document whose upstream records are missing, stale or shaped
            # in a way the assembly does not expect must not abort a batch —
            # the same isolation extract_pages, extract_figures and clean_text
            # apply. Not marked processed, so a later run retries it.
            append_error(step_dir, _error_dict(
                "AssembleSectionsFailed", str(e), {"doc_slug": slug}))
            writer.append([])
            if verbose:
                print("[error]", flush=True)
            continue

        for error in result.errors:
            append_error(step_dir, error)

        writer.append([{
            "doc_slug": slug,
            "doc_title": document.get("doc_title") or slug,
            "source_url": document.get("source_url") or "",
            "page_count": result.coverage["page_count"],
            "public_body_id": document.get("public_body_id"),
            "detection_method": structure.get("detection_method"),
            "sections_dir": f"sections/{slug}",
            "chapters": result.chapters,
            "coverage": result.coverage,
            "publishable": result.publishable,
        }])
        if verbose:
            state = "publishable" if result.publishable else "NOT publishable"
            print(f"{len(result.sections)} section(s), {state}", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Cut each document's cleaned blocks into per-section Markdown, "
                    "interleave figures, render tables, and assert page coverage")
    parser.add_argument("--input", required=True, help="Path to clean_text/output.json")
    parser.add_argument("--output", default=None, help="Path to write output.json")
    parser.add_argument("--force", action="store_true", help="Re-assemble every document")
    parser.add_argument("--verbose", action="store_true", help="Print progress")
    add_doc_arg(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output) if args.output else step_dir / "output.json"

    input_path = Path(args.input)
    clean_records = read_json(input_path).get("results", [])

    # Fan-in: the blocks come from --input, the section boundaries, the figures
    # and the document's provenance from sibling step directories. The shared
    # runner passes exactly one --input, so further upstreams are resolved by
    # path, the way export_status does in foi_pipeline.
    steps_dir = input_path.resolve().parents[1]
    structures = _index_by_doc(steps_dir / "detect_structure" / "output.json")
    figures = _index_by_doc(steps_dir / "extract_figures" / "output.json")
    # `doc_title`, `source_url` and `public_body_id` are contract frontmatter
    # keys and exist nowhere upstream of fetch_pdfs, so its record is the
    # document's provenance of record.
    fetched = _index_by_doc(steps_dir / "fetch_pdfs" / "output.json")
    meta = {slug: {"doc_title": record.get("title") or slug,
                   "source_url": record.get("url") or "",
                   "public_body_id": record.get("public_body_id")}
            for slug, record in fetched.items()}

    writer = IncrementalWriter(output_path, STEP_NAME, key_field="doc_slug",
                               force=args.force, target_key=args.doc)
    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")

    process(clean_records, structures, figures, meta, step_dir, writer,
            doc_slug=args.doc, verbose=args.verbose)

    count = writer.finalize()
    write_status(step_dir, count)
    unpublishable = [r["doc_slug"] for r in read_json(output_path).get("results", [])
                     if not r.get("publishable")]
    print(f"Wrote {count} of {len(clean_records)} document section record(s) "
          f"to {output_path}")
    if unpublishable:
        print(f"NOT publishable ({len(unpublishable)}): {', '.join(unpublishable)} "
              f"— see errors.json for the coverage gaps/overlaps")


if __name__ == "__main__":
    main()
