import json
from pathlib import Path

from steps.clean_text import process as clean_text_process
from steps.clean_text.process import (
    blocks_for_page,
    body_size,
    classify_list,
    dehyphenate,
    is_dingbat_marker,
    is_furniture,
    is_marginalia,
    join_lines,
    process,
    repeated_keys,
    text_column,
)
from steps.detect_structure.process import Line

PAGE_H = 842.0


def line(text, x0=72.0, y0=400.0, size=10.0, font="Helvetica", page_no=1, block=0, index=0):
    return Line(text=text, size=size, font=font,
                bbox=(x0, y0, x0 + 6.0 * len(text), y0 + size),
                block=block, index=index, page=page_no)


def span(text, size=10.0, font="Helvetica", y0=100.0, x0=72.0, block=0, line=0, index=0):
    return {"text": text, "font": font, "size": size,
            "bbox": [x0, y0, x0 + 6.0 * len(text), y0 + size],
            "block": block, "line": line, "span": index}


def page(spans, number=1, tables=None):
    return {"number": number, "width": 595.0, "height": PAGE_H, "rotation": 0,
            "spans": spans, "drawings": [], "images": [],
            "tables": tables if tables is not None else []}


def write_upstream(tmp_path, pages, doc_slug="fixture-doc"):
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
                       "outline": [], "pages": index}]


# --- pure functions: dehyphenation and line joining ------------------------

def test_two_spans_on_consecutive_lines_mid_sentence_join_into_one_paragraph():
    p = page([
        span("The strategy sets out a plan for the region and", y0=170.0, block=0, line=0),
        span("commits to walking as the primary mode of travel.", y0=184.0, block=0, line=1),
    ], number=1)
    blocks, _ = blocks_for_page(p, body=10.0, repeated=set(), levels={})
    assert [b["type"] for b in blocks] == ["paragraph"]
    assert blocks[0]["text"] == ("The strategy sets out a plan for the region and commits "
                                 "to walking as the primary mode of travel.")


def test_a_word_split_across_a_line_break_is_dehyphenated():
    assert dehyphenate("acces-", "sible") == "accessible"
    assert join_lines(["acces-", "sible"]) == "accessible"


# --- running headers and footers --------------------------------------------

def test_a_string_repeating_at_the_same_y_across_three_pages_is_stripped_as_a_running_header():
    pages = [page([span("Fixture Transport Strategy", size=8.0, y0=40.0, block=0),
                   span("Body text here.", y0=400.0, block=1)], number=n + 1)
             for n in range(3)]
    repeated = repeated_keys(pages)
    header = line("Fixture Transport Strategy", y0=40.0, size=8.0)
    body = line("Body text here.", y0=400.0)
    assert is_furniture(header, PAGE_H, repeated)
    assert not is_furniture(body, PAGE_H, repeated)


def test_a_page_number_footer_is_stripped():
    repeated = set()
    assert is_furniture(line("4", y0=805.0, size=8.0), PAGE_H, repeated)
    assert not is_furniture(line("4", y0=400.0), PAGE_H, repeated)


# --- marginalia --------------------------------------------------------------

def test_a_span_far_outside_the_main_column_is_dropped_as_marginalia():
    body_lines = [line("Body text of the main column.", x0=150.0, y0=100.0 + i * 14.0)
                  for i in range(6)]
    column = text_column(body_lines)
    assert not is_marginalia(body_lines[0], column)
    assert is_marginalia(line("Side note", x0=20.0, y0=200.0), column)


# --- dingbat bullet markers -----------------------------------------------

def test_a_short_wingdings2_line_is_a_dingbat_marker():
    assert is_dingbat_marker(line("y", font="Wingdings2", size=11.0))


def test_a_short_webdings_or_symbol_line_is_also_a_dingbat_marker():
    assert is_dingbat_marker(line("a", font="Webdings", size=11.0))
    assert is_dingbat_marker(line("F", font="Symbol", size=11.0))


def test_a_long_line_in_a_dingbat_font_is_not_treated_as_a_marker():
    # A whole paragraph is never actually set in a dingbat font in practice,
    # but the length guard keeps this narrow rather than trusting font name
    # alone to decide a multi-word line is a stray glyph.
    assert not is_dingbat_marker(line("Some unexpectedly long run of text", font="Wingdings2"))


def test_an_ordinary_font_is_never_a_dingbat_marker():
    assert not is_dingbat_marker(line("y", font="Gotham-Book"))


def test_a_wingdings2_bullet_glyph_is_dropped_rather_than_joined_into_the_paragraph():
    """Regression test for the real GDA Transport Strategy PDF: a Wingdings2
    bullet glyph decodes to the literal letter 'y' via PyMuPDF's raw text
    extraction (not a Unicode bullet character), and without this filter it
    reads as a real word and gets joined straight into the item's prose —
    silent content corruption, not a missing bullet."""
    spans = [
        span("Public transport services operate on a spectrum.", y0=100.0, block=0, line=0),
        span("y", font="Wingdings2", y0=130.0, block=1, line=0),
        span("Standard Bus Service ", y0=130.0, block=1, line=1),
        span("carrying less than 400 passengers per hour.", y0=145.0, block=1, line=2),
    ]
    blocks, _suspect = blocks_for_page(page(spans), body=10.0, repeated=set(), levels={})
    joined_text = " ".join(b["text"] for b in blocks if b["type"] == "paragraph")
    assert "y Standard Bus Service" not in joined_text
    assert " y " not in f" {joined_text} "
    assert "Standard Bus Service carrying less than 400 passengers per hour." in joined_text


# --- list detection ------------------------------------------------------

def test_bullet_prefixed_lines_become_one_unordered_list_block():
    p = page([
        span("• Walking", y0=240.0, block=0, line=0),
        span("• Cycling", y0=254.0, block=0, line=1),
        span("• Public transport", y0=268.0, block=0, line=2),
    ], number=1)
    blocks, _ = blocks_for_page(p, body=10.0, repeated=set(), levels={})
    assert len(blocks) == 1
    assert blocks[0]["type"] == "list"
    assert blocks[0]["ordered"] is False
    assert blocks[0]["items"] == ["Walking", "Cycling", "Public transport"]


def test_numbered_lines_become_one_ordered_list_block():
    p = page([
        span("1. First", y0=240.0, block=0, line=0),
        span("2. Second", y0=254.0, block=0, line=1),
        span("3. Third", y0=268.0, block=0, line=2),
    ], number=1)
    blocks, _ = blocks_for_page(p, body=10.0, repeated=set(), levels={})
    assert len(blocks) == 1
    assert blocks[0]["type"] == "list"
    assert blocks[0]["ordered"] is True
    assert blocks[0]["items"] == ["First", "Second", "Third"]


def test_classify_list_returns_none_for_prose():
    assert classify_list(["Walking is available.", "Cycling is too."]) is None


# --- tables ------------------------------------------------------------------

def test_a_detected_table_becomes_a_table_block_carrying_index_and_y_not_a_paragraph():
    p = page([span("Mode", y0=170.0, block=0), span("Share", x0=240.0, y0=170.0, block=1),
              span("Outside the table.", y0=500.0, block=2)], number=1,
             tables=[{"bbox": [72.0, 160.0, 400.0, 280.0], "rows": 2, "cols": 2,
                     "cells": [], "text": [["Mode", "Share"], ["Walk", "25%"]]}])
    blocks, _ = blocks_for_page(p, body=10.0, repeated=set(), levels={})
    assert [b["type"] for b in blocks] == ["table", "paragraph"]
    assert blocks[0]["index"] == 0
    assert blocks[0]["y"] == 160.0
    assert blocks[0]["text"] == [["Mode", "Share"], ["Walk", "25%"]]
    assert blocks[1]["text"] == "Outside the table."


# --- ordering ------------------------------------------------------------

def test_blocks_come_back_ordered_by_ascending_y():
    p = page([span("Second, lower down the page.", y0=400.0, block=1),
              span("First, near the top.", y0=100.0, block=0)], number=1)
    blocks, _ = blocks_for_page(p, body=10.0, repeated=set(), levels={})
    assert [b["text"] for b in blocks] == ["First, near the top.", "Second, lower down the page."]


# --- body_size: character-weighted mode, not the mean ------------------------

def test_body_size_is_the_character_weighted_mode_not_the_mean():
    pages = [page([
        span("Title", size=20.0, y0=90.0, block=0),
        span("This is the body text of the document and it repeats many characters "
             "to dominate the weighted histogram of sizes found on this page.",
             size=10.0, y0=170.0, block=1),
    ], number=1)]

    sizes = [s["size"] for p in pages for s in p["spans"]]
    naive_mean = sum(sizes) / len(sizes)
    assert naive_mean != 10.0  # sanity: the (unweighted) mean picks a different answer

    assert body_size(pages) == 10.0


# --- suspected reading-order failures ----------------------------------------

def test_spans_wildly_out_of_y_order_within_a_block_are_flagged_suspect():
    p = page([
        span("A line further down the page.", y0=300.0, block=0, line=0),
        span("A line that jumps far back up.", y0=50.0, block=0, line=1),
    ], number=5)
    _, suspect = blocks_for_page(p, body=10.0, repeated=set(), levels={})
    assert suspect is True


def test_normally_ordered_lines_are_not_flagged_suspect():
    p = page([
        span("First line.", y0=100.0, block=0, line=0),
        span("Second line just below it.", y0=114.0, block=0, line=1),
    ], number=1)
    _, suspect = blocks_for_page(p, body=10.0, repeated=set(), levels={})
    assert suspect is False


def test_suspect_reading_order_is_logged_as_an_informational_error_with_the_page_number(tmp_path):
    p = page([
        span("A line further down the page.", y0=300.0, block=0, line=0),
        span("A line that jumps far back up.", y0=50.0, block=0, line=1),
    ], number=5)
    upstream, records = write_upstream(tmp_path, [p])
    step_dir = tmp_path / "clean_text"
    step_dir.mkdir()
    writer = clean_text_process.IncrementalWriter(step_dir / "output.json", "clean_text",
                                                   key_field="doc_slug", force=True)

    process(records, upstream, step_dir, writer)
    writer.finalize()

    errors = json.loads((step_dir / "errors.json").read_text())
    suspects = [e for e in errors if e["error_type"] == "SuspectReadingOrder"]
    assert len(suspects) == 1
    assert suspects[0]["context"]["page"] == 5
    assert suspects[0]["context"]["doc_slug"] == "fixture-doc"

    # Informational only — the document still publishes normally.
    results = json.loads((step_dir / "output.json").read_text())["results"]
    assert results[0]["doc_slug"] == "fixture-doc"


# --- end-to-end step behaviour -----------------------------------------------

def test_process_writes_body_size_and_blocks_per_page(tmp_path):
    pages = [
        page([span("Fixture Transport Strategy", size=8.0, y0=40.0, block=0),
              span("1.1 Introduction", size=14.0, font="Helvetica-Bold", y0=130.0, block=1),
              span("Walking is the most available mode, and", y0=170.0, block=2, line=0),
              span("it improves accessi-", y0=184.0, block=2, line=1),
              span("bility for everyone.", y0=198.0, block=2, line=2),
              span("2", size=8.0, y0=805.0, block=3)], number=n + 1)
        for n in range(3)
    ]
    upstream, records = write_upstream(tmp_path, pages)
    step_dir = tmp_path / "clean_text"
    step_dir.mkdir()
    writer = clean_text_process.IncrementalWriter(step_dir / "output.json", "clean_text",
                                                   key_field="doc_slug", force=True)

    process(records, upstream, step_dir, writer)
    writer.finalize()

    (record,) = json.loads((step_dir / "output.json").read_text())["results"]
    assert record["body_size"] == 10.0
    assert [p["number"] for p in record["pages"]] == [1, 2, 3]


def test_process_strips_running_header_and_page_number_end_to_end(tmp_path):
    pages = [
        page([span("Fixture Transport Strategy", size=8.0, y0=40.0, block=0),
              span("1.1 Introduction", size=14.0, font="Helvetica-Bold", y0=130.0, block=1),
              span("Walking is the most available mode, and", y0=170.0, block=2, line=0),
              span("it improves accessi-", y0=184.0, block=2, line=1),
              span("bility for everyone.", y0=198.0, block=2, line=2),
              span("2", size=8.0, y0=805.0, block=3)], number=n + 1)
        for n in range(3)
    ]
    upstream, records = write_upstream(tmp_path, pages)
    step_dir = tmp_path / "clean_text"
    step_dir.mkdir()
    writer = clean_text_process.IncrementalWriter(step_dir / "output.json", "clean_text",
                                                   key_field="doc_slug", force=True)

    process(records, upstream, step_dir, writer)
    writer.finalize()

    (record,) = json.loads((step_dir / "output.json").read_text())["results"]
    first_page_blocks = record["pages"][0]["blocks"]
    dump = json.dumps(first_page_blocks)
    assert "Fixture Transport Strategy" not in dump
    assert not any(b.get("text") == "2" for b in first_page_blocks)

    paragraph = next(b for b in first_page_blocks if b["type"] == "paragraph")
    assert "accessibility for everyone" in paragraph["text"]
    assert "accessi-" not in paragraph["text"]

    heading = first_page_blocks[0]
    assert heading["type"] == "heading"
    assert heading["text"] == "1.1 Introduction"


# --- failure isolation: one bad document must not abort the run --------------

def test_one_malformed_document_does_not_prevent_the_others(tmp_path):
    """A document whose page sidecar is missing (a broken extract_pages
    record, or cross-step staleness) must not abort a batch run."""
    good_page = page([span("Some real prose text on this page.", y0=170.0, block=0)], number=1)
    upstream, records = write_upstream(tmp_path, [good_page], doc_slug="good-doc")

    # Corrupt a second document's record by pointing it at a page file that
    # was never written.
    bad_record = {"doc_slug": "bad-doc", "doc_title": "Bad", "page_count": 1,
                  "outline": [], "pages": [{"number": 1, "file": "pages/bad-doc/001.json",
                                            "width": 595.0, "height": 842.0,
                                            "rotation": 0, "span_count": 0}]}
    records = [bad_record, records[0]]

    step_dir = tmp_path / "clean_text"
    step_dir.mkdir()
    writer = clean_text_process.IncrementalWriter(step_dir / "output.json", "clean_text",
                                                   key_field="doc_slug", force=True)

    process(records, upstream, step_dir, writer)
    writer.finalize()

    results = json.loads((step_dir / "output.json").read_text())["results"]
    assert [r["doc_slug"] for r in results] == ["good-doc"]

    errors = json.loads((step_dir / "errors.json").read_text())
    failures = [e for e in errors if e["error_type"] == "CleanTextFailed"]
    assert [e["context"]["doc_slug"] for e in failures] == ["bad-doc"]
    # Not marked processed, so a later run retries it.
    assert "bad-doc" not in writer.processed_keys


# --- real fixture PDF (fetch_pdfs -> extract_pages -> clean_text) ------------

def test_the_fixture_pdf_reflows_into_readable_prose(tmp_path):
    from steps.extract_pages.process import process as extract_pages_process

    fixture_pdf = Path(__file__).parent / "fixtures" / "fixture.pdf"
    pages_dir = tmp_path / "extract_pages"
    pages_dir.mkdir()
    pages_writer = clean_text_process.IncrementalWriter(
        pages_dir / "output.json", "extract_pages", key_field="doc_slug", force=True)
    extract_pages_process(
        [{"doc_slug": "fixture-doc", "title": "Fixture Transport Strategy",
          "url": "https://example.org/fixture.pdf", "page_count": 4,
          "pdf_path": str(fixture_pdf)}],
        tmp_path, pages_dir, pages_writer)
    pages_writer.finalize()
    records = json.loads((pages_dir / "output.json").read_text())["results"]

    step_dir = tmp_path / "clean_text"
    step_dir.mkdir()
    writer = clean_text_process.IncrementalWriter(step_dir / "output.json", "clean_text",
                                                   key_field="doc_slug", force=True)
    process(records, pages_dir, step_dir, writer)
    writer.finalize()

    (record,) = json.loads((step_dir / "output.json").read_text())["results"]
    page_two = next(p for p in record["pages"] if p["number"] == 2)
    dump = json.dumps(page_two["blocks"])

    # The running header and page number are gone.
    assert "Fixture Transport Strategy" not in dump
    assert not any(b.get("text") == "2" for b in page_two["blocks"])

    # The wrapped, hyphenated sentence reads as prose.
    paragraph = next(b for b in page_two["blocks"] if b["type"] == "paragraph"
                     and "Walking" in b.get("text", ""))
    assert paragraph["text"] == (
        "Walking is the most universally available mode of transport, and improving "
        "the pedestrian environment therefore improves accessibility for every other "
        "mode as well.")

    # The three-item bullet list survives as one list block.
    lists = [b for b in page_two["blocks"] if b["type"] == "list"]
    assert len(lists) == 1
    assert lists[0]["items"] == ["Walking", "Cycling", "Public transport"]
