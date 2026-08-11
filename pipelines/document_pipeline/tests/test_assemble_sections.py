"""Tests for the assemble_sections step.

The coverage assertion is the most valuable test in this pipeline: without it
a structure-detection miss silently drops a whole chapter while the resulting
site still looks perfectly fine. Everything here that touches `publishable`
exists to make that failure loud.
"""

import copy
import json
import re
from pathlib import Path

import pytest

from lib.file_utils import IncrementalWriter
from steps.assemble_sections.process import (
    FRONT_MATTER,
    FRONTMATTER_KEYS,
    build,
    process,
    render_table,
    table_figure_id,
)

DOC = "fixture-doc"
DOC_TITLE = "Fixture Transport Strategy"
SOURCE_URL = "https://example.org/fixture.pdf"
PUBLIC_BODY_ID = 1570

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def node(slug, level, number, title, page, y, order, parent=None, end_page=None):
    return {"level": level, "number": number, "title": title, "slug": slug,
            "start_page": page, "start_y": y, "end_page": end_page or page,
            "confidence": 0.9, "parent": parent, "order": order}


@pytest.fixture
def structure():
    """Two chapters, three sections, four pages, every page owned by exactly
    one section — the shape a document must have to be publishable."""
    return {
        "doc_slug": DOC,
        "detection_method": "numbering",
        "page_count": 4,
        "nodes": [
            node("1-first-chapter", 1, "1", "First Chapter", 1, 70.0, 100),
            node("1-1-introduction", 2, "1.1", "Introduction", 1, 110.0, 101,
                 "1-first-chapter", end_page=2),
            node("1-2-figures", 2, "1.2", "Figures", 3, 70.0, 102, "1-first-chapter"),
            node("2-second-chapter", 1, "2", "Second Chapter", 4, 70.0, 200),
            node("2-1-tables", 2, "2.1", "Tables", 4, 110.0, 201, "2-second-chapter"),
        ],
    }


@pytest.fixture
def clean():
    return {
        "doc_slug": DOC,
        "body_size": 10.0,
        "pages": [
            {"number": 1, "blocks": [
                {"type": "heading", "level": 1, "text": "1 First Chapter", "y": 70.0},
                {"type": "heading", "level": 2, "text": "1.1 Introduction", "y": 110.0},
                {"type": "paragraph", "text": "Walking is available.", "y": 150.0},
                {"type": "list", "ordered": False, "items": ["Walking", "Cycling"],
                 "y": 200.0}]},
            {"number": 2, "blocks": [
                {"type": "paragraph", "text": "The introduction continues.", "y": 90.0}]},
            {"number": 3, "blocks": [
                {"type": "heading", "level": 2, "text": "1.2 Figures", "y": 70.0},
                {"type": "paragraph", "text": "Before the figure.", "y": 110.0},
                {"type": "paragraph", "text": "After the figure.", "y": 200.0}]},
            {"number": 4, "blocks": [
                {"type": "heading", "level": 1, "text": "2 Second Chapter", "y": 70.0},
                {"type": "heading", "level": 2, "text": "2.1 Tables", "y": 110.0},
                {"type": "table", "index": 0, "y": 150.0,
                 "text": [["Mode", "Share"], ["Walk", "25%"], ["Cycle", "10%"]]}]},
        ],
    }


@pytest.fixture
def figures():
    return {"doc_slug": DOC, "figures": [
        {"id": "p003-f01", "kind": "figure", "page": 3, "bbox": [72, 130, 320, 300],
         "y": 150.0, "asset": f"assets/{DOC}/p003-f01.webp",
         "caption": "Figure 1.1 A vector diagram", "alt": "Figure 1.1 A vector diagram",
         "width": 496, "height": 340},
        {"id": "p004-t01", "kind": "table", "page": 4, "bbox": [72, 150, 400, 280],
         "y": 150.0, "asset": f"assets/{DOC}/p004-t01.webp",
         "caption": "Table 2.1 Mode share", "alt": "Table 2.1 Mode share",
         "width": 656, "height": 240},
    ]}


def assemble(structure, figures, clean):
    return build(structure, figures, clean, doc_slug=DOC, doc_title=DOC_TITLE,
                 source_url=SOURCE_URL, public_body_id=PUBLIC_BODY_ID)


def section_by_slug(result, slug):
    return next(s for s in result.sections if s.slug == slug)


def frontmatter_block(section) -> str:
    match = FRONTMATTER_RE.match(section.markdown)
    assert match, f"no frontmatter at the top of {section.slug}"
    return match.group(1)


def body_of(section) -> str:
    return FRONTMATTER_RE.sub("", section.markdown)


# --- section cutting --------------------------------------------------------

def test_blocks_are_cut_at_section_boundaries_by_start_page_and_start_y(
        structure, figures, clean):
    """A block belongs to the last boundary at or before its (page, y): the
    paragraph above `1.1 Introduction`'s y goes to the chapter that opened the
    page, the one below it goes to the section."""
    clean = copy.deepcopy(clean)
    clean["pages"][0]["blocks"].insert(
        2, {"type": "paragraph", "text": "Chapter preamble.", "y": 90.0})

    result = assemble(structure, figures, clean)
    chapter_overview = section_by_slug(result, "overview")
    introduction = section_by_slug(result, "1-1-introduction")

    assert "Chapter preamble." in body_of(chapter_overview)
    assert "Walking is available." not in body_of(chapter_overview)
    assert "Walking is available." in body_of(introduction)
    assert "Chapter preamble." not in body_of(introduction)
    # The page-3 boundary cuts too: page 3's prose is not in section 1.1.
    assert "Before the figure." not in body_of(introduction)


def test_a_figure_between_two_paragraphs_is_emitted_between_them(
        structure, figures, clean):
    body = body_of(section_by_slug(assemble(structure, figures, clean), "1-2-figures"))
    assert body.index("Before the figure.") < body.index("![Figure 1.1 A vector diagram]")
    assert body.index("![Figure 1.1 A vector diagram]") < body.index("After the figure.")
    assert "*Figure 1.1 A vector diagram*" in body


def test_a_figures_caption_is_not_also_left_behind_as_a_stray_paragraph(
        structure, figures, clean):
    """clean_text has no knowledge of figures, so a caption line arrives here
    as an ordinary paragraph as well. It must appear once, italicised under
    its image — not twice."""
    clean = copy.deepcopy(clean)
    clean["pages"][2]["blocks"].append(
        {"type": "paragraph", "text": "Figure 1.1 A vector diagram", "y": 180.0})

    body = body_of(section_by_slug(assemble(structure, figures, clean), "1-2-figures"))
    assert body.count("Figure 1.1 A vector diagram") == 2   # alt text + caption
    assert "*Figure 1.1 A vector diagram*" in body
    assert "\nFigure 1.1 A vector diagram\n" not in body
    # A paragraph that merely mentions a figure is not a caption and stays.
    assert "After the figure." in body


def test_the_sections_own_heading_is_not_repeated_in_the_body(structure, figures, clean):
    body = body_of(section_by_slug(assemble(structure, figures, clean), "1-1-introduction"))
    assert "1.1 Introduction" not in body
    assert "#" not in body.split("Walking is available.")[0]


# --- tables -----------------------------------------------------------------

def test_a_simple_three_by_two_table_renders_as_a_gfm_pipe_table(
        structure, figures, clean):
    body = body_of(section_by_slug(assemble(structure, figures, clean), "2-1-tables"))
    assert "| Mode | Share |" in body
    assert "| --- | --- |" in body
    assert "| Walk | 25% |" in body
    assert "| Cycle | 10% |" in body


def test_a_table_with_merged_cells_is_demoted_to_its_table_image_plus_caption(
        structure, figures, clean):
    """Merged cells arrive from extract_pages as ragged rows. There is no
    honest pipe-table rendering of those, so the rasterised `kind: "table"`
    figure stands in for it."""
    clean = copy.deepcopy(clean)
    clean["pages"][3]["blocks"][-1]["text"] = [["Mode", "Share"], ["Walk"]]

    result = assemble(structure, figures, clean)
    body = body_of(section_by_slug(result, "2-1-tables"))
    assert "![Table 2.1 Mode share](assets/p004-t01.webp)" in body
    assert "*Table 2.1 Mode share*" in body
    assert "| Mode | Share |" not in body
    assert any(e["error_type"] == "TableDemoted" for e in result.errors)


def test_render_table_refuses_ragged_and_single_row_tables():
    assert render_table([["a", "b"], ["c"]]) is None
    assert render_table([["a", "b"]]) is None


def test_table_figure_id_is_the_join_key_to_the_rasterised_copy():
    assert table_figure_id(4, 0) == "p004-t01"
    assert table_figure_id(94, 2) == "p094-t03"


def test_a_cell_containing_a_newline_does_not_emit_raw_html():
    """The contract's Markdown subset forbids raw HTML, so no `<br>`."""
    rendered = render_table([["a|b", "c\nd"], ["e", "f"]])
    assert r"a\|b" in rendered
    assert "<" not in rendered
    assert "c d" in rendered


# --- frontmatter ------------------------------------------------------------

def test_frontmatter_contains_exactly_the_eleven_contract_keys(structure, figures, clean):
    """The web repo writes a strict schema against exactly this set; an extra
    or renamed key breaks its build."""
    section = section_by_slug(assemble(structure, figures, clean), "1-1-introduction")
    keys = [line.split(":", 1)[0] for line in frontmatter_block(section).splitlines()]
    assert keys == [
        "title", "doc", "doc_title", "chapter", "chapter_title", "section",
        "order", "source_pages", "source_url", "public_body_id", "assets"]
    assert list(FRONTMATTER_KEYS) == keys


def test_order_is_chapter_times_one_hundred_plus_section(structure, figures, clean):
    result = assemble(structure, figures, clean)
    assert section_by_slug(result, "1-1-introduction").order == 101
    assert section_by_slug(result, "2-1-tables").order == 201
    assert "order: 101" in frontmatter_block(section_by_slug(result, "1-1-introduction"))
    assert [c["order"] for c in result.chapters] == [100, 200]


def test_source_pages_are_first_and_last_inclusive(structure, figures, clean):
    result = assemble(structure, figures, clean)
    introduction = section_by_slug(result, "1-1-introduction")
    assert introduction.source_pages == [1, 2]
    assert "source_pages: [1, 2]" in frontmatter_block(introduction)
    assert section_by_slug(result, "2-1-tables").source_pages == [4, 4]


def test_image_paths_are_bundle_relative_and_listed_in_the_assets_frontmatter(
        structure, figures, clean):
    section = section_by_slug(assemble(structure, figures, clean), "1-2-figures")
    body = body_of(section)
    assert "](assets/p003-f01.webp)" in body
    assert "](/" not in body
    assert ".." not in body
    assert section.assets == ["p003-f01.webp"]
    assert 'assets: ["p003-f01.webp"]' in frontmatter_block(section)


# --- coverage ---------------------------------------------------------------

def test_full_coverage_of_pages_one_to_n_is_publishable(structure, figures, clean):
    result = assemble(structure, figures, clean)
    assert result.coverage == {"page_count": 4, "covered": [1, 2, 3, 4], "gaps": [],
                               "overlaps": [], "empty_sections": []}
    assert result.publishable is True


def test_a_dropped_page_is_a_coverage_gap_that_blocks_publication(
        structure, figures, clean, tmp_path):
    """A page whose content reached no section is content that vanished —
    exactly what a structure-detection miss looks like from downstream."""
    clean = copy.deepcopy(clean)
    clean["pages"][2]["blocks"] = []          # page 3's content disappears
    figures = {"doc_slug": DOC, "figures": []}

    result = assemble(structure, figures, clean)
    assert result.coverage["gaps"] == [3]
    assert result.publishable is False

    record, errors = run_process(tmp_path, structure, figures, clean)
    assert record["publishable"] is False
    gaps = [e for e in errors if e["error_type"] == "CoverageGap"]
    assert [e["context"]["page"] for e in gaps] == [3]


def test_two_sections_claiming_the_same_page_is_a_coverage_overlap(
        structure, figures, clean, tmp_path):
    structure = copy.deepcopy(structure)
    figures_node = next(n for n in structure["nodes"] if n["slug"] == "1-2-figures")
    figures_node["start_page"], figures_node["start_y"] = 2, 120.0
    clean = copy.deepcopy(clean)
    clean["pages"][1]["blocks"].append(
        {"type": "paragraph", "text": "Now inside 1.2.", "y": 160.0})
    clean["pages"][2]["blocks"] = [
        {"type": "paragraph", "text": "Still inside 1.2.", "y": 90.0}]

    result = assemble(structure, figures, clean)
    assert result.coverage["overlaps"] == [2]
    assert result.coverage["gaps"] == []
    assert result.publishable is False

    record, errors = run_process(tmp_path, structure, figures, clean)
    assert record["publishable"] is False
    overlaps = [e for e in errors if e["error_type"] == "CoverageOverlap"]
    assert [e["context"]["page"] for e in overlaps] == [2]


def test_an_empty_section_is_listed_but_does_not_block_publication(
        structure, figures, clean):
    """A heading that owns no prose is worth reporting, but it is not content
    loss the way a coverage gap is — every page still reached a section."""
    structure = copy.deepcopy(structure)
    structure["nodes"].append(
        node("2-2-orphan", 2, "2.2", "Orphan", 4, 700.0, 202, "2-second-chapter"))

    result = assemble(structure, figures, clean)
    assert result.coverage["empty_sections"] == ["2-2-orphan"]
    assert result.coverage["gaps"] == []
    assert result.coverage["overlaps"] == []
    assert result.publishable is True
    assert not any(s.slug == "2-2-orphan" for s in result.sections)


# --- step -------------------------------------------------------------------

def run_process(tmp_path, structure, figures, clean, extra_clean=None,
                structures=None, meta=None):
    """Run the step's process() over one document and return (record, errors)."""
    step_dir = tmp_path / "assemble_sections"
    step_dir.mkdir(exist_ok=True)
    writer = IncrementalWriter(step_dir / "output.json", "assemble_sections",
                               key_field="doc_slug", force=True)
    clean_records = [clean] + list(extra_clean or [])
    process(clean_records,
            structures if structures is not None else {DOC: structure},
            {DOC: figures},
            meta if meta is not None else {
                DOC: {"doc_title": DOC_TITLE, "source_url": SOURCE_URL,
                      "public_body_id": PUBLIC_BODY_ID}},
            step_dir, writer)
    writer.finalize()
    results = json.loads((step_dir / "output.json").read_text())["results"]
    errors = json.loads((step_dir / "errors.json").read_text())
    return (results[0] if results else None), errors


def test_process_writes_one_markdown_file_per_section_and_a_chapters_tree(
        structure, figures, clean, tmp_path):
    record, _errors = run_process(tmp_path, structure, figures, clean)
    step_dir = tmp_path / "assemble_sections"

    assert [c["slug"] for c in record["chapters"]] == ["1-first-chapter", "2-second-chapter"]
    files = sorted(str(p.relative_to(step_dir))
                   for p in (step_dir / "sections").rglob("*.md"))
    assert files == [
        f"sections/{DOC}/1-first-chapter/1-1-introduction.md",
        f"sections/{DOC}/1-first-chapter/1-2-figures.md",
        f"sections/{DOC}/2-second-chapter/2-1-tables.md",
    ]
    section = record["chapters"][0]["sections"][0]
    assert section["file"] == f"sections/{DOC}/1-first-chapter/1-1-introduction.md"
    assert section["word_count"] > 0
    assert (step_dir / section["file"]).read_text().startswith("---\n")
    assert record["publishable"] is True


def test_one_malformed_document_does_not_prevent_the_others(
        structure, figures, clean, tmp_path):
    """Per-document isolation: a document with no detect_structure record must
    not abort a batch run, and must stay retryable."""
    broken = {"doc_slug": "broken-doc", "body_size": 10.0, "pages": []}
    record, errors = run_process(
        tmp_path, structure, figures, clean, extra_clean=[broken],
        structures={DOC: structure},
        meta={DOC: {"doc_title": DOC_TITLE, "source_url": SOURCE_URL,
                    "public_body_id": PUBLIC_BODY_ID}})

    step_dir = tmp_path / "assemble_sections"
    results = json.loads((step_dir / "output.json").read_text())["results"]
    assert [r["doc_slug"] for r in results] == [DOC]

    failures = [e for e in errors if e["error_type"] == "AssembleSectionsFailed"]
    assert [e["context"]["doc_slug"] for e in failures] == ["broken-doc"]
    assert record["doc_slug"] == DOC


def test_a_rerun_removes_a_stale_section_file(structure, figures, clean, tmp_path):
    step_dir = tmp_path / "assemble_sections"
    stale = step_dir / "sections" / DOC / "1-first-chapter" / "9-9-gone.md"
    stale.parent.mkdir(parents=True)
    stale.write_text("old")
    run_process(tmp_path, structure, figures, clean)
    assert not stale.exists()
    assert (step_dir / "sections" / DOC / "1-first-chapter"
            / "1-1-introduction.md").exists()


def test_the_fixture_documents_page_one_is_covered_by_a_front_matter_section(
        structure, figures, clean, tmp_path):
    """The real fixture PDF's page 1 is a title page that sits before the
    first detected heading. It is assembled into a synthetic front-matter
    section rather than left as a coverage gap — matching the plan's own
    Data Contracts worked example, which shows page 1 as covered and the
    document as publishable."""
    structure = copy.deepcopy(structure)
    for candidate in structure["nodes"]:
        candidate["start_page"] += 1
        candidate["end_page"] += 1
    clean = copy.deepcopy(clean)
    for page in clean["pages"]:
        page["number"] += 1
    clean["pages"].insert(0, {"number": 1, "blocks": [
        {"type": "paragraph", "text": "Fixture Transport Strategy", "y": 120.0}]})
    structure["page_count"] = 5

    result = assemble(structure, figures, clean)
    assert result.coverage["gaps"] == []
    assert 1 in result.coverage["covered"]
    assert result.publishable is True

    front_matter = section_by_slug(result, FRONT_MATTER)
    assert front_matter.chapter == FRONT_MATTER
    assert front_matter.order == 0
    assert front_matter.source_pages == [1, 1]
    assert "Fixture Transport Strategy" in body_of(front_matter)
    assert f"chapter: {FRONT_MATTER}" in frontmatter_block(front_matter)
    assert f"section: {FRONT_MATTER}" in frontmatter_block(front_matter)
    assert "order: 0" in frontmatter_block(front_matter)


def test_front_matter_section_is_excluded_when_nothing_precedes_the_first_boundary(
        structure, figures, clean):
    """The unmodified fixture's first boundary starts at page 1, y=70 — the
    very first block — so there is nothing before it and no front-matter
    section should be manufactured."""
    result = assemble(structure, figures, clean)
    assert not any(s.slug == FRONT_MATTER for s in result.sections)
    assert not any(c["slug"] == FRONT_MATTER for c in result.chapters)


def test_front_matter_section_only_covers_its_own_pre_boundary_pages(
        structure, figures, clean):
    """Front matter spanning several pages reports source_pages as
    [first, last] inclusive, same as any other section, and does not swallow
    pages that belong to a real section."""
    structure = copy.deepcopy(structure)
    for candidate in structure["nodes"]:
        candidate["start_page"] += 2
        candidate["end_page"] += 2
    clean = copy.deepcopy(clean)
    for page in clean["pages"]:
        page["number"] += 2
    clean["pages"][0:0] = [
        {"number": 1, "blocks": [
            {"type": "paragraph", "text": "Cover page.", "y": 120.0}]},
        {"number": 2, "blocks": [
            {"type": "paragraph", "text": "Table of contents.", "y": 120.0}]},
    ]
    structure["page_count"] = 6

    result = assemble(structure, figures, clean)
    front_matter = section_by_slug(result, FRONT_MATTER)
    assert front_matter.source_pages == [1, 2]
    assert "Cover page." in body_of(front_matter)
    assert "Table of contents." in body_of(front_matter)
    introduction = section_by_slug(result, "1-1-introduction")
    assert "Cover page." not in body_of(introduction)
    assert result.coverage["gaps"] == []
    assert result.publishable is True
