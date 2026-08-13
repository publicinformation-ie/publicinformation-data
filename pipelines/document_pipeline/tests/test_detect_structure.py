import json
from pathlib import Path

from documents import SLUG_RE
from steps.detect_structure.process import detect_structure, merge_overrides, process
from steps.extract_pages.process import extract_page

import pymupdf

FIXTURES = Path(__file__).parent / "fixtures"


def load_pages(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def span(text, size=10.0, font="Helvetica", y0=100.0, x0=72.0, block=0, line=0, index=0):
    return {"text": text, "font": font, "size": size,
            "bbox": [x0, y0, x0 + 6.0 * len(text), y0 + size],
            "block": block, "line": line, "span": index}


def page(spans, number=1):
    return {"number": number, "width": 595.0, "height": 842.0, "rotation": 0,
            "spans": spans, "drawings": [], "images": [], "tables": []}


def write_upstream(tmp_path, pages, doc_slug="fixture-doc", outline=None):
    """Lay out an extract_pages step directory the way that step writes it."""
    upstream = tmp_path / "extract_pages"
    (upstream / "pages" / doc_slug).mkdir(parents=True, exist_ok=True)
    index = []
    for record in pages:
        relative = f"pages/{doc_slug}/{record['number']:03d}.json"
        (upstream / relative).write_text(json.dumps(record), encoding="utf-8")
        index.append({"number": record["number"], "file": relative,
                      "width": record["width"], "height": record["height"],
                      "rotation": record["rotation"], "span_count": len(record["spans"])})
    return upstream, [{"doc_slug": doc_slug, "doc_title": "Fixture", "page_count": len(pages),
                       "outline": outline or [], "pages": index}]


def by_slug(nodes):
    return {node.slug: node for node in nodes}


# --- strategy cascade ------------------------------------------------------

def test_the_outline_strategy_wins_when_the_pdf_has_an_outline():
    outline = [{"level": 1, "title": "1 First Chapter", "page": 2, "y": 76.0},
               {"level": 2, "title": "1.1 Introduction", "page": 2, "y": 118.0}]
    nodes, method = detect_structure(load_pages("pages_numbered.json"), outline, 4)

    assert method == "outline"
    assert [n.slug for n in nodes] == ["1-first-chapter", "1-1-introduction"]
    assert nodes[0].number == "1"
    assert nodes[1].title == "Introduction"
    assert all(n.confidence == 1.0 for n in nodes)


def test_the_numbering_strategy_detects_chapters_sections_and_parents():
    nodes, method = detect_structure(load_pages("pages_numbered.json"), [], 4)

    assert method == "numbering"
    assert [n.slug for n in nodes] == ["1-first-chapter", "1-1-introduction", "1-2-figures",
                                       "2-second-chapter", "2-1-methods"]
    assert [n.level for n in nodes] == [1, 2, 2, 1, 2]
    assert all(n.confidence == 0.9 for n in nodes)

    indexed = by_slug(nodes)
    assert indexed["1-first-chapter"].parent is None
    assert indexed["1-1-introduction"].parent == "1-first-chapter"
    assert indexed["1-2-figures"].parent == "1-first-chapter"
    assert indexed["2-1-methods"].parent == "2-second-chapter"


def test_a_numeric_line_at_body_size_is_not_a_heading():
    """`10.5% of trips …` and `2.4 million trips …` are prose. The second one
    even matches the heading pattern; only the font-size guard rejects it."""
    nodes, _ = detect_structure(load_pages("pages_numbered.json"), [], 4)

    assert not any("trips" in node.title for node in nodes)


def test_the_font_strategy_ranks_larger_styles_into_levels():
    nodes, method = detect_structure(load_pages("pages_font.json"), [], 2)

    assert method == "font"
    assert [n.title for n in nodes] == ["Introduction", "Methodology", "A sub point",
                                        "Conclusions"]
    assert [n.level for n in nodes] == [1, 1, 2, 1]
    assert all(n.confidence == 0.6 for n in nodes)


def test_the_flat_fallback_fires_when_there_is_no_signal_and_is_logged(tmp_path, make_writer):
    upstream, records = write_upstream(tmp_path, load_pages("pages_flat.json"))
    nodes, method = detect_structure(load_pages("pages_flat.json"), [], 3)

    assert method == "flat"
    assert [n.slug for n in nodes] == ["page-001", "page-002", "page-003"]
    assert all(n.confidence == 0.2 for n in nodes)

    step_dir = tmp_path / "detect_structure"
    step_dir.mkdir()
    writer = make_writer("detect_structure")
    process(records, upstream, step_dir, writer)
    writer.finalize()

    (record,) = json.loads((tmp_path / "output.json").read_text())["results"]
    assert record["detection_method"] == "flat"
    errors = json.loads((step_dir / "errors.json").read_text())
    assert [e["error_type"] for e in errors] == ["LowConfidenceStructure"]


# --- node fields -----------------------------------------------------------

def test_end_page_stops_before_the_next_same_or_higher_level_node():
    nodes, _ = detect_structure(load_pages("pages_numbered.json"), [], 4)
    indexed = by_slug(nodes)

    # 1.1 ends on page 2 because 1.2 (same level) starts on page 3.
    assert (indexed["1-1-introduction"].start_page, indexed["1-1-introduction"].end_page) == (2, 2)
    # Chapter 1 runs to page 3 because chapter 2 (higher level) starts on page 4.
    assert (indexed["1-first-chapter"].start_page, indexed["1-first-chapter"].end_page) == (2, 3)
    assert (indexed["1-2-figures"].start_page, indexed["1-2-figures"].end_page) == (3, 3)
    # The last nodes run to the document's last page.
    assert indexed["2-second-chapter"].end_page == 4
    assert indexed["2-1-methods"].end_page == 4


def test_slugs_retain_heading_numbers_and_match_the_repo_slug_pattern():
    nodes, _ = detect_structure(load_pages("pages_numbered.json"), [], 4)

    assert by_slug(nodes)["1-1-introduction"].title == "Introduction"
    for node in nodes:
        assert SLUG_RE.match(node.slug), node.slug


def test_a_repeated_heading_gets_a_numeric_suffix():
    pages = [page([span("1 First Chapter", size=18.0, font="Helvetica-Bold", y0=76.0, block=0),
                   span("1.1 Introduction", size=14.0, font="Helvetica-Bold", y0=118.0, block=1),
                   span("Body text about walking and cycling in the city.", y0=160.0, block=2)],
                  number=1),
             page([span("1.1 Introduction", size=14.0, font="Helvetica-Bold", y0=76.0, block=0),
                   span("Body text continued from the preceding page.", y0=118.0, block=1)],
                  number=2)]

    nodes, _ = detect_structure(pages, [], 2)

    assert [n.slug for n in nodes] == ["1-first-chapter", "1-1-introduction",
                                       "1-1-introduction-2"]


# --- override merge --------------------------------------------------------

def test_merge_overrides_replaces_a_title_and_leaves_other_nodes_alone():
    nodes, _ = detect_structure(load_pages("pages_numbered.json"), [], 4)
    before = {n.slug: n.title for n in nodes}

    merged, errors = merge_overrides(
        nodes, [{"slug": "1-1-introduction", "title": "Introduction and context"}], 4)

    assert errors == []
    indexed = by_slug(merged)
    assert indexed["1-1-introduction"].title == "Introduction and context"
    assert indexed["1-1-introduction"].slug == "1-1-introduction"
    assert indexed["1-1-introduction"].start_page == 2
    for slug, title in before.items():
        if slug != "1-1-introduction":
            assert indexed[slug].title == title


def test_merge_overrides_can_flatten_a_staircase_outline():
    """Some PDFs' own bookmark outlines have a 'staircase' bug: each heading
    nested one level deeper than the last, never returning to level 1, even
    though the headings are all the same visual level in the document. The
    override.json escape hatch fixes this by patching `level`, which must
    recompute `parent` for every affected node, not just the patched one."""
    outline = [{"level": 1, "title": "Foreword", "page": 1, "y": 0.0},
               {"level": 2, "title": "Introduction", "page": 2, "y": 0.0},
               {"level": 3, "title": "Safe System Approach", "page": 3, "y": 0.0},
               {"level": 4, "title": "Vision Zero", "page": 4, "y": 0.0},
               {"level": 4, "title": "Abbreviations", "page": 5, "y": 0.0}]
    nodes, method = detect_structure([], outline, 5)
    assert method == "outline"

    merged, errors = merge_overrides(
        nodes,
        [{"slug": slug, "level": 1} for slug in
         ("introduction", "safe-system-approach", "vision-zero", "abbreviations")],
        5)

    assert errors == []
    indexed = by_slug(merged)
    assert all(indexed[slug].level == 1 for slug in
               ("foreword", "introduction", "safe-system-approach", "vision-zero",
                "abbreviations"))
    assert all(indexed[slug].parent is None for slug in
               ("foreword", "introduction", "safe-system-approach", "vision-zero",
                "abbreviations"))
    assert [n.order for n in merged] == sorted(n.order for n in merged)


def test_merge_overrides_reports_a_slug_that_no_longer_exists():
    nodes, _ = detect_structure(load_pages("pages_numbered.json"), [], 4)

    merged, errors = merge_overrides(nodes, [{"slug": "1-9-mystery", "title": "Mystery"}], 4)

    assert [n.slug for n in merged] == [n.slug for n in nodes]
    assert [e["error_type"] for e in errors] == ["UnknownOverrideSlug"]
    assert "1-9-mystery" in errors[0]["error_message"]


def test_the_fixture_pdf_detects_as_two_chapters_with_one_section_each():
    """The fixture's tree is a fixed contract: every later step's golden output
    is written against exactly these four nodes."""
    doc = pymupdf.open(FIXTURES / "fixture.pdf")
    pages = [extract_page(doc[i], i + 1) for i in range(doc.page_count)]

    nodes, method = detect_structure(pages, [], doc.page_count)

    assert method == "numbering"
    assert [(n.level, n.slug, n.start_page, n.end_page) for n in nodes] == [
        (1, "1-first-chapter", 2, 3),
        (2, "1-1-introduction", 2, 3),
        (1, "2-second-chapter", 4, 4),
        (2, "2-1-methods", 4, 4),
    ]


def test_process_applies_the_override_file(tmp_path, make_writer):
    upstream, records = write_upstream(tmp_path, load_pages("pages_numbered.json"))
    step_dir = tmp_path / "detect_structure"
    step_dir.mkdir()
    (step_dir / "override.json").write_text(json.dumps(
        {"fixture-doc": [{"slug": "1-1-introduction", "title": "Introduction and context"}]}),
        encoding="utf-8")

    writer = make_writer("detect_structure")
    process(records, upstream, step_dir, writer)
    writer.finalize()

    (record,) = json.loads((tmp_path / "output.json").read_text())["results"]
    assert record["detection_method"] == "numbering"
    assert record["overridden"] is True
    node = next(n for n in record["nodes"] if n["slug"] == "1-1-introduction")
    assert node["title"] == "Introduction and context"
    assert set(node) == {"level", "number", "title", "slug", "start_page", "start_y",
                         "end_page", "confidence", "parent", "order"}
