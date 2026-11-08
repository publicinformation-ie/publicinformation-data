import json
from pathlib import Path

from documents import SLUG_RE
from steps.detect_structure.process import (
    Node,
    _below_score_floor,
    _legacy_cascade,
    _parse_toc_page,
    _supplement_numbered_nodes,
    _heading_continuation,
    body_size,
    clean_title,
    from_font_hierarchy,
    from_numbering,
    build_occurrence_index,
    detect_structure,
    find_occurrences,
    is_heading_candidate,
    merge_overrides,
    normalize_heading_text,
    page_lines,
    reading_order_lines,
    parse_toc,
    process,
    running_header_texts,
    score_occurrence,
    validate_split,
)
from steps.detect_structure.process import READING_ORDER_Y_GRID, resolve_outline_positions
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
    nodes, method, _ = detect_structure(load_pages("pages_numbered.json"), outline, 4)

    assert method == "outline"
    assert [n.slug for n in nodes] == ["1-first-chapter", "1-1-introduction"]
    assert nodes[0].number == "1"
    assert nodes[1].title == "Introduction"
    assert all(n.confidence == 1.0 for n in nodes)


def test_the_numbering_strategy_detects_chapters_sections_and_parents():
    nodes, method, _ = detect_structure(load_pages("pages_numbered.json"), [], 4)

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
    nodes, _, _ = detect_structure(load_pages("pages_numbered.json"), [], 4)

    assert not any("trips" in node.title for node in nodes)


def test_the_font_strategy_ranks_larger_styles_into_levels():
    nodes, method, _ = detect_structure(load_pages("pages_font.json"), [], 2)

    assert method == "font"
    assert [n.title for n in nodes] == ["Introduction", "Methodology", "A sub point",
                                        "Conclusions"]
    assert [n.level for n in nodes] == [1, 1, 2, 1]
    assert all(n.confidence == 0.6 for n in nodes)


def test_the_flat_fallback_fires_when_there_is_no_signal_and_is_logged(tmp_path, make_writer):
    upstream, records = write_upstream(tmp_path, load_pages("pages_flat.json"))
    nodes, method, _ = detect_structure(load_pages("pages_flat.json"), [], 3)

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
    nodes, _, _ = detect_structure(load_pages("pages_numbered.json"), [], 4)
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
    nodes, _, _ = detect_structure(load_pages("pages_numbered.json"), [], 4)

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

    nodes, _, _ = detect_structure(pages, [], 2)

    assert [n.slug for n in nodes] == ["1-first-chapter", "1-1-introduction",
                                       "1-1-introduction-2"]


# --- override merge --------------------------------------------------------

def test_merge_overrides_replaces_a_title_and_leaves_other_nodes_alone():
    nodes, _, _ = detect_structure(load_pages("pages_numbered.json"), [], 4)
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
    nodes, method, _ = detect_structure([], outline, 5)
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
    nodes, _, _ = detect_structure(load_pages("pages_numbered.json"), [], 4)

    merged, errors = merge_overrides(nodes, [{"slug": "1-9-mystery", "title": "Mystery"}], 4)

    assert [n.slug for n in merged] == [n.slug for n in nodes]
    assert [e["error_type"] for e in errors] == ["UnknownOverrideSlug"]
    assert "1-9-mystery" in errors[0]["error_message"]


def test_the_fixture_pdf_detects_as_two_chapters_with_one_section_each():
    """The fixture's tree is a fixed contract: every later step's golden output
    is written against exactly these four nodes."""
    doc = pymupdf.open(FIXTURES / "fixture.pdf")
    pages = [extract_page(doc[i], i + 1) for i in range(doc.page_count)]

    nodes, method, _ = detect_structure(pages, [], doc.page_count)

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


# --- TOC-name helpers ------------------------------------------------------

def test_normalize_heading_text_strips_control_chars_and_punctuation():
    assert normalize_heading_text("  Executive\u2009Summary\x08  ") == "executive summary"
    assert normalize_heading_text("Introduction .....") == "introduction"
    assert normalize_heading_text("Glossary\u2026") == "glossary"
    assert normalize_heading_text("1.1 Purpose of National Roads 2040") == \
        "1.1 purpose of national roads 2040"


def test_is_heading_candidate_rejects_junk():
    assert is_heading_candidate("Introduction")
    assert not is_heading_candidate("")
    assert not is_heading_candidate("123")
    assert not is_heading_candidate("x")
    assert not is_heading_candidate("Intro....")
    assert not is_heading_candidate("\u2022 bullet")
    assert not is_heading_candidate("\u20ac100 million")


def test_running_header_texts_threshold():
    pages = []
    for i in range(5):
        spans = [span("Running Header", size=8.0, block=0, line=0, y0=10.0)]
        if i == 0:
            spans.append(span("One-off title", size=12.0, block=1, line=0, y0=50.0))
        pages.append(page(spans, number=i + 1))
    running = running_header_texts(pages)
    assert "running header" in running
    assert "one-off title" not in running


def test_parse_toc_detects_page_and_parses_entries():
    body = 10.0
    toc_page = page([
        span("Contents", size=16.0, y0=40.0, block=0),
        span("Introduction", size=12.0, y0=80.0, block=1),
        span("3", size=12.0, y0=80.0, x0=540.0, block=2),
        span("Methodology", size=12.0, y0=95.0, block=3),
        span("5", size=12.0, y0=95.0, x0=540.0, block=4),
        span("Abbreviations", size=12.0, y0=110.0, block=5),
        span("12", size=12.0, y0=110.0, x0=540.0, block=6),
    ], number=2)
    entries, toc_pages, level_signal, flags = parse_toc([toc_page], body)

    assert toc_pages == [2]
    assert [e["title"] for e in entries] == ["Introduction", "Methodology", "Abbreviations"]
    assert [e["furniture"] for e in entries] == [False, False, True]
    assert flags["right_page_number"] is True


def test_parse_toc_infers_levels_from_numbering():
    body = 10.0
    toc_page = page([
        span("Contents", size=16.0, y0=40.0, block=0),
        span("1 Introduction", size=12.0, y0=80.0, block=1),
        span("1.1 Background", size=12.0, y0=95.0, block=2),
        span("2 Method", size=12.0, y0=110.0, block=3),
    ], number=2)
    entries, _, level_signal, _ = parse_toc([toc_page], body)

    assert level_signal == "numbering"
    assert [e["level"] for e in entries] == [1, 2, 1]


def test_find_occurrences_number_tolerant_alias():
    body = 10.0
    pages = [
        page([span("1.1 Introduction", size=14.0, y0=80.0, block=0)], number=3),
        page([span("Introduction", size=14.0, y0=80.0, block=0)], number=4),
    ]
    index = build_occurrence_index(pages, set(), set(), body)
    occs = find_occurrences(index, "Introduction")
    assert sorted(o["page"] for o in occs) == [3, 4]


def test_build_occurrence_index_excludes_toc_pages_and_running_headers():
    body = 10.0
    pages = [
        page([span("Introduction", size=14.0, y0=80.0, block=0)], number=2),
        page([span("Introduction", size=14.0, y0=80.0, block=0)], number=3),
    ]
    running = running_header_texts(pages)
    assert "introduction" in running  # on both pages
    index = build_occurrence_index(pages, {2}, running, body)
    assert find_occurrences(index, "Introduction") == []


def test_score_occurrence_and_floor():
    body = 10.0
    assert score_occurrence({"size": 14.0, "bold": False, "isolated": True}, body) == \
        14.0 / 10.0 + 0.3
    assert score_occurrence({"size": 14.0, "bold": True, "isolated": True}, body) == \
        14.0 / 10.0 + 0.5 + 0.3

    assert _below_score_floor({"size": 10.0, "bold": False}, body) is True
    assert _below_score_floor({"size": 10.5, "bold": False}, body) is False
    assert _below_score_floor({"size": 8.0, "bold": True}, body) is False


def test_validate_split_flags_junk_duplicate_and_gap():
    junk = Node(level=1, number=None, title="", slug="empty",
                start_page=4, start_y=80.0, end_page=4)
    assert any("empty" in i for i in validate_split([junk], 4))

    a = Node(level=1, number=None, title="A", slug="a", start_page=2, start_y=80.0, end_page=4)
    b = Node(level=1, number=None, title="B", slug="b", start_page=2, start_y=80.0, end_page=4)
    assert any("duplicate" in i for i in validate_split([a, b], 4))

    early = Node(level=1, number=None, title="Intro", slug="intro",
                 start_page=2, start_y=1.0, end_page=2)
    late = Node(level=1, number=None, title="End", slug="end",
                start_page=5, start_y=1.0, end_page=5)
    gaps = [i for i in validate_split([early, late], 5) if "gap" in i]
    assert len(gaps) == 2  # pages 3 and 4; page 1 is front matter, not a gap


def test_validate_split_valid_tree_has_no_issues():
    a = Node(level=1, number=None, title="Intro", slug="intro",
             start_page=2, start_y=1.0, end_page=3)
    b = Node(level=2, number=None, title="Detail", slug="detail",
             start_page=4, start_y=1.0, end_page=5)
    assert validate_split([a, b], 5) == []


# --- reading order ---------------------------------------------------------

def test_reading_order_puts_header_then_title_then_body_then_footer():
    """SMP foreword page 6: raw span order is header, footer, body, then the
    40pt `Foreword` title last. Reading order is top to bottom."""
    lines = reading_order_lines(load_pages("pages_two_column.json")[0])
    texts = [l.text for l in lines]

    assert texts[0].startswith("National Sustainable Mobility Policy")
    assert texts[-1] == "4"  # footer page number, bottom-most and left-most
    assert texts.index("Foreword") < texts.index(
        next(t for t in texts if t.startswith("The National Sustainable Mobility Policy provides")))
    # y is monotonically non-decreasing up to the grid, so nothing is out of order
    ys = [round(l.y0 / READING_ORDER_Y_GRID) for l in lines]
    assert ys == sorted(ys)


def test_reading_order_sorts_same_baseline_lines_left_to_right():
    """The two columns of page 6 share baselines; the left column's line
    precedes the right column's line at the same y."""
    lines = reading_order_lines(load_pages("pages_two_column.json")[0])
    texts = [l.text for l in lines]
    left = texts.index(next(t for t in texts if t.startswith("The National Sustainable")))
    right = texts.index(next(t for t in texts if t.startswith("in rural areas and that")))

    assert left + 1 == right


def test_reading_order_ignores_sub_grid_baseline_noise():
    spans = [span("right", y0=100.2, x0=300.0, block=0, line=0),
             span("left", y0=100.0, x0=72.0, block=1, line=0),
             span("below", y0=140.0, x0=72.0, block=2, line=0)]
    assert [l.text for l in reading_order_lines(page(spans))] == ["left", "right", "below"]


# --- toc_filtering ---------------------------------------------------------

def _smp_toc_parse():
    """SMP page 4 (the TOC), page 6, and eight further body pages (copies of
    page 28 renumbered) so the running-header lead repeats on enough pages,
    and `Foreword`, which appears on pages 4 and 6, stays below the
    running-header fraction as it does in the full 60-page document."""
    pages = load_pages("pages_smp_toc.json") + load_pages("pages_two_column.json")
    for number in range(10, 18):
        pages.append({**load_pages("pages_smp_quote.json")[0], "number": number})
    return parse_toc(pages, 10.0)


def test_toc_filtering_skips_the_footer_number_and_the_running_header():
    entries, toc_pages, _signal, _flags = _smp_toc_parse()
    titles = [e["title"] for e in entries]

    assert toc_pages == [4]
    assert not any(e["number"] == "2" for e in entries)  # footer `2` is not a section number
    assert not any("National Sustainable Mobility Policy" in t for t in titles)


def test_toc_filtering_starts_at_foreword_and_the_title_line_is_not_an_entry():
    entries, _pages, _signal, _flags = _smp_toc_parse()
    titles = [e["title"] for e in entries]

    assert titles[:3] == ["Foreword", "Summary", "Chapter 1 – Introduction"]
    assert not any(t.lower() in ("table of contents", "contents") for t in titles)


def test_toc_filtering_skipped_footer_adds_no_indent_bucket_so_levels_are_flat():
    """The footer line (x0 ~ 43) used to become a bogus entry whose x0 made
    `_infer_levels` see two indent buckets and push every real entry to
    level 2. With it skipped, all entries share one left edge."""
    entries, _pages, signal, _flags = _smp_toc_parse()

    assert signal == "none"
    assert entries and {e["level"] for e in entries} == {1}


def test_toc_filtering_skips_a_bare_page_number_at_the_left_edge():
    spans = [span("Contents", size=20.0, y0=60.0, block=0),
             span("First Chapter", y0=120.0, block=1),
             span("5", y0=120.0, x0=500.0, block=1, line=1),
             span("Second Chapter", y0=140.0, block=2),
             span("9", y0=140.0, x0=500.0, block=2, line=1),
             span("3", y0=800.0, x0=40.0, block=3)]  # footer, left edge
    entries, flags = _parse_toc_page(page(spans))

    assert [e["title"] for e in entries] == ["First Chapter", "Second Chapter"]


# --- toc_page_exclusion ----------------------------------------------------

def _body_page(number, heading, size=18.0):
    """A body page: one bold numbered heading and 9pt prose, so 9pt is body."""
    spans = [span(heading, size=size, font="Helvetica-Bold", y0=60.0, block=0)]
    for row in range(12):
        spans.append(span("Prose set at nine points runs on for a good while here.",
                          size=9.0, y0=100.0 + row * 12.0, block=1 + row))
    return page(spans, number=number)


def test_toc_page_exclusion_numbering_and_font_skip_a_dot_leader_toc_page():
    emra = load_pages("pages_emra_toc.json")[0]  # real emra page 2: dot-leader TOC lines

    assert from_numbering([emra], 9.0), "sanity: the TOC lines are heading-like at this body size"
    assert from_numbering([emra], 9.0, skip_pages={2}) == []
    assert from_font_hierarchy([emra], 9.0, skip_pages={2}) == []


def test_toc_page_exclusion_applies_on_the_fallback_path():
    """TOC detected but nothing in the body matches it: match rate 0, below the
    gate, so the cascade falls back — and must still skip the TOC page."""
    pages = [load_pages("pages_emra_toc.json")[0],
             _body_page(3, "1 Alpha Chapter"),
             _body_page(4, "2 Beta Chapter")]

    nodes, method, report = detect_structure(pages, [], 4)

    assert report is not None and report["match_rate"] < 0.6  # the fallback fired
    assert method == "numbering"
    assert [n.title for n in nodes] == ["Alpha Chapter", "Beta Chapter"]
    assert all(n.start_page != 2 for n in nodes)
    assert not any("...." in n.title for n in nodes)


def test_toc_page_exclusion_legacy_cascade_takes_the_toc_page_set():
    emra = load_pages("pages_emra_toc.json")[0]
    pages = [emra, _body_page(3, "1 Alpha Chapter"), _body_page(4, "2 Beta Chapter")]

    with_toc, _ = _legacy_cascade(pages, 9.0)
    without_toc, _ = _legacy_cascade(pages, 9.0, {2})

    assert any(n.start_page == 2 for n in with_toc)
    assert not any(n.start_page == 2 for n in without_toc)


def test_toc_page_exclusion_supplement_adds_nothing_from_a_toc_page():
    toc_page = page([span("Contents", size=20.0, font="Helvetica-Bold", y0=60.0, block=0),
                     span("9.9 Orphan Heading", size=14.0, font="Helvetica-Bold", y0=120.0, block=1)],
                    number=2)
    body = _body_page(3, "1 Alpha Chapter")

    assert [n.title for n in _supplement_numbered_nodes([toc_page, body], 9.0, [], [], set(), {2})] \
        == ["Alpha Chapter"]
    assert "Orphan Heading" in [n.title for n in
                                _supplement_numbered_nodes([toc_page, body], 9.0, [], [], set())]


# --- title_cleanup ---------------------------------------------------------

def test_title_cleanup_strips_the_leading_pipe_from_a_real_nifti_toc_page():
    """Nifti page 3 lists `1.2 | Investing in Transport`. The running header
    (`National Investment Framework … | Overview`) repeats, so a second copy of
    the page gives it the two pages it needs to be recognised."""
    toc = load_pages("pages_nifti_toc.json")[0]
    header = toc["spans"][:2]  # the two spans that make up the running header
    # Nine further pages carrying only the same running header, so it repeats
    # on enough pages to be recognised while the TOC entries do not.
    fillers = [page([{**header[0], "block": 0, "line": 0, "span": 0},
                     {**header[1], "block": 0, "line": 0, "span": 1},
                     span("Body text on a later page.", size=10.0, y0=120.0, block=1)],
                    number=number)
               for number in range(10, 19)]
    entries, toc_pages, _signal, _flags = parse_toc([toc] + fillers, 10.0)
    titles = [e["title"] for e in entries]

    assert toc_pages == [3]
    assert "Investing in Transport" in titles
    assert not any("|" in t for t in titles)


def test_title_cleanup_strips_control_characters_from_a_matched_heading():
    nodes = from_numbering(load_pages("pages_ev_heading.json"), 10.0)
    by_number = {n.number: n for n in nodes}

    assert by_number["1.1"].title.startswith("National and international")
    assert all("\x07" not in n.title and "\x07" not in n.slug for n in nodes)
    assert by_number["1.1"].slug.startswith("1-1-national-and-international")


def test_title_cleanup_helper_handles_each_fragment():
    assert clean_title("| Investing in Transport") == "Investing in Transport"
    assert clean_title("-Moving towards") == "Moving towards"
    assert clean_title("1.1 \x07National") == "1.1 National"
    assert clean_title("  Spaced   out  ") == "Spaced out"


def test_title_cleanup_does_not_launder_a_bullet_into_a_title():
    """`- 21.3 metres length` is a bullet; cleanup must leave it for the
    heading-candidate guard to reject, not turn it into a passing title."""
    assert clean_title("- 21.3 metres length") == "- 21.3 metres length"
    assert not is_heading_candidate(clean_title("- 21.3 metres length"))


def test_title_cleanup_interior_dot_leaders_are_rejected_not_cleaned():
    leader = page([span("1.1 Landscape and Visual ......... 23", size=14.0, font="Helvetica-Bold",
                        y0=60.0, block=0),
                   span("Prose set at nine points runs on for a good while here.", size=9.0,
                        y0=100.0, block=1)], number=5)

    assert clean_title("Landscape and Visual ......... 23") == "Landscape and Visual ......... 23"
    assert from_numbering([leader], 9.0) == []
    assert from_font_hierarchy([leader], 9.0) == []


# --- cascade_guard ---------------------------------------------------------

def _titles(nodes):
    return [n.title for n in nodes]


def test_cascade_guard_a_lone_chapter_numeral_makes_no_node_but_the_title_survives():
    """SMP page 9: a 119pt `1`, a 32pt `CHAPTER`, and the real 37pt title."""
    nodes = from_font_hierarchy(load_pages("pages_smp_opener.json"), 10.0)

    assert "1" not in _titles(nodes)
    assert "Introduction" in _titles(nodes)


def test_cascade_guard_a_pull_quote_glyph_makes_no_node():
    """SMP page 28: a 70pt quote glyph followed by the real `Targets` heading."""
    pages = load_pages("pages_smp_quote.json")
    nodes = from_font_hierarchy(pages, 10.0)

    assert not [t for t in _titles(nodes) if t.strip(' "\u201d\u201c') == ""]
    assert "Targets" in _titles(nodes)


def test_cascade_guard_cover_text_numeral_makes_no_node():
    """Action plan cover: `2040` (the Project Ireland logo) is set at heading size."""
    nodes = from_font_hierarchy(load_pages("pages_actionplan_cover.json"), 10.0)

    assert "2040" not in _titles(nodes)
    assert not any(t.isdigit() for t in _titles(nodes))


def test_cascade_guard_a_map_glyph_makes_no_node():
    pages = load_pages("pages_gda_glyph.json")
    nodes = from_font_hierarchy(pages, body_size(pages))

    assert nodes, "sanity: the map page still yields real headings"
    assert not [t for t in _titles(nodes) if len(t) == 1]


def test_cascade_guard_joins_a_wrapped_heading_into_one_node():
    """Action plan page 3: `Safe and Green` / `Mobility`, both 33.4pt bold."""
    nodes = from_font_hierarchy(load_pages("pages_actionplan_join.json"), 10.0)

    assert "Safe and Green Mobility" in _titles(nodes)
    assert "Safe and Green" not in _titles(nodes)
    assert "Mobility" not in _titles(nodes)


def test_cascade_guard_joins_the_cover_title_lines():
    nodes = from_font_hierarchy(load_pages("pages_actionplan_cover.json"), 10.0)

    assert "National Sustainable Mobility Policy" in _titles(nodes)


def test_cascade_guard_numbering_joins_a_wrapped_numbered_heading():
    nodes = from_numbering(load_pages("pages_ev_heading.json"), 10.0)
    by_number = {n.number: n for n in nodes}

    assert by_number["1.1"].title == "National and international policy context"


def test_cascade_guard_does_not_join_lines_in_separate_columns():
    """SMP page 6: two body columns share a baseline and a type size. Their
    lines sit next to each other in reading order, but are never continuations
    of one another: a continuation is the line directly below, in-column."""
    lines = reading_order_lines(load_pages("pages_two_column.json")[0])
    left = next(l for l in lines if l.text.startswith("The National Sustainable"))
    right = next(l for l in lines if l.text.startswith("in rural areas and that"))

    assert abs(left.y0 - right.y0) < 1.0  # same baseline, different column
    follow = _heading_continuation(left, lines)
    assert follow is None or lines[follow] is not right
    assert follow is not None and lines[follow].bbox[0] == left.bbox[0]  # the in-column line below


def test_cascade_guard_join_is_bounded_by_the_gap_constant():
    near = [span("Wrapped", size=20.0, font="Helvetica-Bold", y0=100.0, block=0),
            span("Heading", size=20.0, font="Helvetica-Bold", y0=124.0, block=1)]
    far = [span("Wrapped", size=20.0, font="Helvetica-Bold", y0=100.0, block=0),
           span("Heading", size=20.0, font="Helvetica-Bold", y0=170.0, block=1)]
    different_style = [span("Wrapped", size=20.0, font="Helvetica-Bold", y0=100.0, block=0),
                       span("Heading", size=20.0, font="Helvetica", y0=124.0, block=1)]
    sentence = [span("A full sentence.", size=20.0, font="Helvetica-Bold", y0=100.0, block=0),
                span("Heading", size=20.0, font="Helvetica-Bold", y0=124.0, block=1)]

    def joins(spans):
        lines = reading_order_lines(page(spans))
        return _heading_continuation(lines[0], lines) is not None

    assert joins(near)
    assert not joins(far)
    assert not joins(different_style)
    assert not joins(sentence)


# --- validate_split: level invariant (6.1) ----------------------------------

def _n(slug, level, start, end, title="A heading"):
    return Node(level=level, number=None, title=title, slug=slug,
                start_page=start, start_y=1.0, end_page=end)


def test_validate_split_flags_a_tree_with_no_level_1_node():
    """The `sustainable-mobility-policy` failure: every node is level 2, so
    the tree has a single level — a 'more than one level' condition would
    miss it. The invariant is unconditional."""
    tree = [_n("a", 2, 1, 2, "Alpha"), _n("b", 2, 3, 4, "Beta")]

    issues = validate_split(tree, 4)

    assert len(issues) == 1 and "no level-1 node" in issues[0]


def test_validate_split_flags_a_deeper_tree_with_no_level_1_node():
    tree = [_n("a", 2, 1, 2, "Alpha"), _n("b", 3, 3, 4, "Beta")]
    assert any("no level-1 node" in i for i in validate_split(tree, 4))


def test_validate_split_accepts_a_flat_all_level_1_tree():
    tree = [_n("a", 1, 1, 2, "Alpha"), _n("b", 1, 3, 4, "Beta")]
    assert validate_split(tree, 4) == []


def test_validate_split_an_empty_tree_has_no_level_issue():
    assert validate_split([], 4) == []


# --- validation_gate (6.2) ---------------------------------------------------

def _run_process(tmp_path, make_writer, outline=None, overrides=None, pages="pages_numbered.json"):
    upstream, records = write_upstream(tmp_path, load_pages(pages), outline=outline)
    step_dir = tmp_path / "detect_structure"
    step_dir.mkdir()
    writer = make_writer("detect_structure")
    process(records, upstream, step_dir, writer, overrides=overrides or {})
    writer.finalize()
    (record,) = json.loads((tmp_path / "output.json").read_text())["results"]
    errors = json.loads((step_dir / "errors.json").read_text())
    return record, [e for e in errors if e["error_type"] == "InvalidStructure"]


def test_validation_gate_flags_an_invalid_tree_and_still_writes_it(tmp_path, make_writer):
    outline = [{"level": 2, "title": "Alpha", "page": 2, "y": 76.0},
               {"level": 2, "title": "Beta", "page": 3, "y": 76.0}]

    record, flagged = _run_process(tmp_path, make_writer, outline=outline)

    assert [n["level"] for n in record["nodes"]] == [2, 2]  # written unaltered
    assert len(flagged) == 1
    assert flagged[0]["context"]["doc_slug"] == "fixture-doc"
    assert flagged[0]["context"]["check"] == "no-level-1-node"
    assert flagged[0]["context"]["value"] == [2]


def test_validation_gate_runs_after_overrides(tmp_path, make_writer):
    """A junk title introduced by an override is still caught."""
    overrides = {"fixture-doc": [{"slug": "1-1-introduction", "title": "1"}]}

    record, flagged = _run_process(tmp_path, make_writer, overrides=overrides)

    assert record["overridden"] is True
    assert [f["context"]["check"] for f in flagged] == ["non-heading-title"]
    assert flagged[0]["context"]["value"] == "1"


def test_validation_gate_a_valid_tree_records_nothing(tmp_path, make_writer):
    _record, flagged = _run_process(tmp_path, make_writer)

    assert flagged == []


def test_validation_gate_flags_a_duplicate_boundary(tmp_path, make_writer):
    outline = [{"level": 1, "title": "Alpha", "page": 2, "y": 76.0},
               {"level": 1, "title": "Beta", "page": 2, "y": 76.0}]

    _record, flagged = _run_process(tmp_path, make_writer, outline=outline)

    assert [f["context"]["check"] for f in flagged] == ["duplicate-boundary"]


def test_page_lines_keeps_the_raw_span_order_other_steps_rely_on():
    """`clean_text` and `extract_figures` share `page_lines`; it must not sort."""
    raw = page_lines(load_pages("pages_two_column.json")[0])
    ordered = reading_order_lines(load_pages("pages_two_column.json")[0])

    assert [l.text for l in raw][:2] == ["National Sustainable Mobility Policy | Foreword", "4"]
    assert [l.text for l in ordered][-1] == "4"
    assert sorted(l.text for l in raw) == sorted(l.text for l in ordered)


# --- joined runs in columns -------------------------------------------------

def _index_for(pages):
    body = body_size(pages)
    return build_occurrence_index(pages, set(), running_header_texts(pages), body), body


def test_joined_runs_join_two_spans_emitted_on_one_baseline():
    """All-island page 139: `Appendix C |` and `Mitigation and Monitoring
    Measures` are separate line groups on one baseline. Raw adjacency used to
    join them; reading order must still join them, across a tiny horizontal gap."""
    pages = load_pages("pages_allisland_appendix.json")
    index, _body = _index_for(pages)

    occurrences = index.get(normalize_heading_text("Appendix C | Mitigation and Monitoring Measures"), [])

    assert occurrences and occurrences[0]["page"] == 139


def test_joined_runs_join_a_wrapped_heading_across_an_interleaved_column():
    """Moving Together page 26: `Economic and Financial` / `Sustainability`
    wrap down the left column while right-column body lines interleave in
    reading order. The run follows the column, not the row."""
    pages = load_pages("pages_moving_together_column.json")
    index, _body = _index_for(pages)

    occurrences = index.get(normalize_heading_text("Economic and Financial Sustainability"), [])

    assert occurrences and occurrences[0]["page"] == 26


def test_joined_runs_do_not_join_two_columns_on_one_baseline():
    """SMP page 6 is one visual row of two columns; no run may splice them."""
    page_record = {**load_pages("pages_two_column.json")[0], "number": 1}
    index, body = _index_for([page_record])
    lines = reading_order_lines(page_record)
    left = next(l for l in lines if l.text.startswith("The National Sustainable"))
    right = next(l for l in lines if l.text.startswith("in rural areas and that"))

    assert abs(left.y0 - right.y0) < 1.0
    assert normalize_heading_text(f"{left.text} {right.text}") not in index


def test_toc_pages_are_read_column_by_column():
    """Emra page 2 is a two-column contents page: the left column's chapters
    come before the right column's, not interleaved row by row."""
    from steps.detect_structure.process import _toc_reading_order

    lines = _toc_reading_order(load_pages("pages_emra_toc.json")[0])
    texts = [l.text for l in lines]
    chapter_1 = texts.index("CHAPTER 1:")
    chapter_4 = texts.index("CHAPTER 4:")

    assert chapter_1 < chapter_4
    assert all(i < chapter_4 for i, t in enumerate(texts) if t.startswith(("1.", "2.", "3.")))


def test_outline_resolve_positions_uses_title_line_y_and_reports_misses():
    pg = page([span("1. Overview", y0=80.0, index=0, line=0),
               span("body text here", y0=120.0, index=1, line=1),
               span("2. Wrapped", y0=300.0, index=2, line=2, block=1),
               span("Heading Title", y0=316.0, index=3, line=3, block=1)], number=5)
    outline = [{"level": 1, "title": "1.\tOverview", "page": 5},
               {"level": 1, "title": "2. Wrapped Heading Title", "page": 5},
               {"level": 1, "title": "Missing", "page": 5},
               {"level": 1, "title": "Given", "page": 5, "y": 42.0}]
    resolved, problems = resolve_outline_positions(outline, [pg])
    assert resolved[0]["y"] == 80.0
    assert resolved[1]["y"] == 300.0
    assert not resolved[2].get("y")
    assert resolved[3]["y"] == 42.0
    assert [p["error_type"] for p in problems] == ["OutlineEntryUnresolved"]
    assert problems[0]["context"] == {"title": "Missing", "page": 5}
