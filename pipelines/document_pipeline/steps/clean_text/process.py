#!/usr/bin/env python3
"""Step: clean_text — turn each document's raw positioned spans back into
readable prose.

A PDF has no paragraphs, only glyphs at coordinates. Everything in the top
half of this file is the inverse of a typesetting decision: undo the line
breaking, undo the hyphenation, remove the furniture the typesetter added
(running headers, page numbers), drop marginalia (anything outside the main
text column), and recover the list structure the bullets or numbers imply.
The bottom half is the twenty-line step shim that loops over documents.

Reads only `extract_pages`'s JSON; it never opens a PDF. Block ordering is
delegated entirely to PyMuPDF's own block/line enumeration — solving complex
multi-column layouts is explicitly out of scope. Where that ordering looks
wrong (spans running backward in y by more than `READING_ORDER_TOLERANCE`
within a single block), the page is logged as `SuspectReadingOrder` and
otherwise left alone: it is informational, not a defect this step attempts
to fix.

Ported from pdf2site's plan (source plan Task 11, lines 3506-4020): the line
joining, dehyphenation, running-header/footer detection, marginalia
dropping, list detection and block ordering. Adapted to:

  * keep the pure reflow functions in this step's own process.py rather than
    a separate `textflow.py` module, matching the convention `detect_structure`
    and `extract_figures` already established of self-contained per-step pure
    functions instead of a shared `pipeline/lib/*.py`;
  * reuse `steps.detect_structure.process`'s `Line`, `page_lines`, `body_size`
    and `heading_levels` rather than introduce a third line/body-style model —
    the same reuse `extract_figures` already established for its own line
    grouping and body style;
  * reuse `lib.text_utils.normalize_text` for whitespace collapsing and
    `(cid:N)` glyph-mapping artefact cleanup, rather than writing a second,
    slightly different normalizer;
  * compute `body_size` and heading levels **per document**, not globally
    across a batch run — a mixed batch of a large-type poster and a dense
    report must not let one document's typography set the other's heading
    threshold;
  * treat a per-document failure (a missing page sidecar, a page shaped in a
    way the reflow does not expect) as a `CleanTextFailed` errors.json entry
    that skips the document rather than aborting the run, the same isolation
    `extract_pages` and `extract_figures` apply to their own per-document
    failure modes.
"""
import argparse
import re
import statistics
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from lib.cli_utils import add_doc_arg
from lib.file_utils import IncrementalWriter, append_error, read_json, write_json, write_status
from lib.text_utils import normalize_text
from steps.detect_structure.process import Line, body_size, heading_levels, page_lines

STEP_NAME = "clean_text"

# --------------------------------------------------------------------------
# Reflow: pure functions over Line objects and plain strings
# --------------------------------------------------------------------------

FURNITURE_BAND = 0.12       # top/bottom share of the page where furniture lives
FURNITURE_MIN_PAGES = 3     # never call something furniture from one sighting
FURNITURE_RATIO = 0.5       # must repeat on at least half the pages
MARGIN_TOLERANCE = 20.0     # points outside the text column before it is marginalia
COLUMN_GAP = 60.0           # points; a horizontal gap this wide between consecutive
                             # body-sized lines (sorted by left edge) starts a new column
COLUMN_MIN_LINES = 2        # a cluster needs at least this many lines to count as its
                             # own column; smaller clusters fold away as marginalia
                             # rather than becoming a phantom one-line "column"
Y_BAND = 10.0                # points; furniture must recur at a consistent height
READING_ORDER_TOLERANCE = 50.0  # points; a backward y jump within one block this
                                 # large is a suspected PyMuPDF reading-order failure

BULLET_RE = re.compile(r"^\s*[•·▪◦‣※∙]\s*(.+)$")
DASH_BULLET_RE = re.compile(r"^\s*[\-–—*]\s+(.+)$")
ORDERED_RE = re.compile(r"^\s*\(?(\d{1,2}|[a-z])[.)]\s+(.+)$")
PAGE_NUMBER_RE = re.compile(r"^\s*[\-–—|]?\s*\d{1,4}\s*[\-–—|]?\s*$")
_DIGITS = re.compile(r"\d")

# Word/InDesign-style bullet lists sometimes set their bullet glyph in a
# dingbat font (Wingdings, Wingdings2/3, Webdings, Symbol) on its own
# PyMuPDF line, separate from the item's text line. PyMuPDF decodes that
# glyph via the font's own cmap, which for a dingbat font is not Unicode —
# a Wingdings2 bullet character routinely decodes to an ordinary ASCII
# letter (`y` is the one this pipeline has actually seen, on a real 244-page
# government strategy PDF: 486 occurrences, one per bullet). None of the
# regexes above can recognise that as a bullet marker; left alone, it reads
# as a real word and is joined straight into the surrounding prose —
# `"single route every 15 minutes y carrying less than 400..."` — silent
# content corruption, not a missing bullet glyph. `is_dingbat_marker` drops
# these lines the same way furniture is dropped, so the corruption doesn't
# reach a paragraph. It does not attempt to reconstruct a real `list` block
# from them: the glyph line and its item text arrive as separate PyMuPDF
# lines (sometimes even reordered by `blocks_for_page`'s y-then-x sort,
# since a dingbat glyph's baseline metrics differ from the surrounding
# font), and stitching that back into `ordered`/`items` correctly is a
# bigger, separate piece of work. A clean paragraph with no bullet
# character is a smaller data-quality problem than a stray letter injected
# mid-sentence, so this is the deliberately narrow fix.
_DINGBAT_FONT_RE = re.compile(r"wingdings|webdings|symbol", re.IGNORECASE)


def is_dingbat_marker(line: Line) -> bool:
    return bool(_DINGBAT_FONT_RE.search(line.font or "")) and len(line.text.strip()) <= 3


def _key(line: Line) -> tuple:
    return (_DIGITS.sub("#", line.text.strip().lower()), int(line.y0 // Y_BAND))


def _in_band(line: Line, page_h: float) -> bool:
    return line.y0 < page_h * FURNITURE_BAND or line.bbox[3] > page_h * (1.0 - FURNITURE_BAND)


def _normalized_lines(page: dict) -> list:
    """Group a page's spans into lines via detect_structure's line grouping,
    then run each line's text through `normalize_text` to strip `(cid:N)`
    glyph-mapping artefacts and collapse internal whitespace — the same
    normalization every other PDF-reading step in this repo already uses,
    rather than a second implementation here."""
    lines = []
    for raw in page_lines(page):
        text = normalize_text(raw.text, file_type="pdf")
        if text:
            lines.append(replace(raw, text=text))
    return lines


def _suspect_reading_order(lines: list) -> bool:
    """True when, within a single block, a later line's y sits more than
    `READING_ORDER_TOLERANCE` points above an earlier one — spans "wildly
    out of y-order", suggesting PyMuPDF's own reading order is wrong for
    this page. Detection only: complex multi-column layout solving is out
    of scope, so this never tries to reorder anything, only flag it."""
    by_block: dict = {}
    for line in lines:
        by_block.setdefault(line.block, []).append(line)
    for block_lines in by_block.values():
        previous_y = None
        for line in block_lines:
            if previous_y is not None and previous_y - line.y0 > READING_ORDER_TOLERANCE:
                return True
            previous_y = line.y0
    return False


def repeated_keys(pages: list) -> set:
    """Keys of lines that recur at a consistent height on many pages."""
    counts: Counter = Counter()
    for page in pages:
        page_h = page["height"]
        for line in _normalized_lines(page):
            if _in_band(line, page_h):
                counts[_key(line)] += 1
    threshold = max(FURNITURE_MIN_PAGES, int(len(pages) * FURNITURE_RATIO))
    return {key for key, count in counts.items() if count >= threshold}


def is_furniture(line: Line, page_h: float, repeated: set) -> bool:
    if not _in_band(line, page_h):
        return False
    if PAGE_NUMBER_RE.match(line.text):
        return True
    return _key(line) in repeated


def text_columns(lines: list) -> list:
    """Cluster body-sized lines into one or more column spans.

    A single page-wide median column (the original approach) is correct for
    single-column pages but silently treats an entire secondary column — a
    highlighted call-out sidebar, for example — as marginalia on a two-column
    page, discarding real content rather than a stray caption. Clustering by
    horizontal gap lets both cases coexist: pages that are genuinely one
    column still collapse to a single cluster.
    """
    if not lines:
        return [(0.0, 0.0)]
    ordered = sorted(lines, key=lambda ln: ln.bbox[0])
    clusters = [[ordered[0]]]
    for ln in ordered[1:]:
        if ln.bbox[0] - clusters[-1][-1].bbox[0] > COLUMN_GAP:
            clusters.append([ln])
        else:
            clusters[-1].append(ln)
    kept = [c for c in clusters if len(c) >= COLUMN_MIN_LINES]
    if not kept:
        kept = [max(clusters, key=len)]
    return [(statistics.median([ln.bbox[0] for ln in c]),
             statistics.median([ln.bbox[2] for ln in c])) for c in kept]


def is_marginalia(line: Line, columns: list, tolerance: float = MARGIN_TOLERANCE) -> bool:
    for left, right in columns:
        if line.bbox[2] >= left - tolerance and line.bbox[0] <= right + tolerance:
            return False
    return True


def dehyphenate(first: str, second: str) -> str:
    """Join two wrapped lines, healing a word split across the break.

    Only a lowercase continuation counts: "park-\\nand-ride" is a real
    compound and keeps its hyphen, and "Section 3 -\\nDublin" is a dash, not
    a break.
    """
    first, second = first.rstrip(), second.lstrip()
    if first.endswith("-") and second[:1].islower():
        stem = first[:-1]
        if stem.endswith("-") or not stem or not stem[-1].isalpha():
            return f"{first} {second}"
        return f"{stem}{second}"
    return f"{first} {second}"


def join_lines(texts: list) -> str:
    if not texts:
        return ""
    result = texts[0].strip()
    for text in texts[1:]:
        result = dehyphenate(result, text)
    return " ".join(result.split())


def classify_list(texts: list):
    """Return (ordered, items) if every line is a list item, else None."""
    if len(texts) < 2:
        return None
    bullets, ordered_items = [], []
    for text in texts:
        bullet = BULLET_RE.match(text) or DASH_BULLET_RE.match(text)
        number = ORDERED_RE.match(text)
        if bullet:
            bullets.append(bullet.group(1).strip())
        elif number:
            ordered_items.append(number.group(2).strip())
        else:
            return None
    if bullets and not ordered_items:
        return (False, bullets)
    if ordered_items and not bullets:
        return (True, ordered_items)
    return None


def _intersects(a, b) -> bool:
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def _column_index(x: float, columns: list) -> int:
    """Index of the column span whose left edge `x` falls into, or is closest to."""
    for index, (left, right) in enumerate(columns):
        if left <= x <= right:
            return index
    return min(range(len(columns)), key=lambda i: abs(x - columns[i][0]))


def blocks_for_page(page: dict, body: float, repeated: set, levels: dict):
    """Reflow one page's lines into typed blocks, ordered by ascending y.

    On multi-column pages, blocks sort column-major (all of one column's
    blocks, top-to-bottom, before the next column's) rather than purely by
    `y`, which would otherwise interleave left- and right-column blocks that
    happen to share a vertical band.

    Returns `(blocks, reading_order_suspect)`.
    """
    page_h = page["height"]
    table_boxes = [tuple(table["bbox"]) for table in page.get("tables", [])]

    all_lines = _normalized_lines(page)
    suspect = _suspect_reading_order(all_lines)

    kept = [line for line in all_lines if not is_furniture(line, page_h, repeated)]
    kept = [line for line in kept if not is_dingbat_marker(line)]
    columns = text_columns([line for line in kept if abs(line.size - body) <= 0.6] or kept)
    kept = [line for line in kept if not is_marginalia(line, columns)]
    kept = [line for line in kept
            if not any(_intersects(box, line.bbox) for box in table_boxes)]

    grouped: dict = {}
    for line in kept:
        grouped.setdefault(line.block, []).append(line)

    blocks = []
    for block_lines in grouped.values():
        block_lines = sorted(block_lines, key=lambda line: (line.y0, line.bbox[0]))
        texts = [line.text for line in block_lines]
        top = round(min(line.y0 for line in block_lines), 2)
        left = min(line.bbox[0] for line in block_lines)

        listed = classify_list(texts)
        if listed is not None:
            ordered, items = listed
            blocks.append({"type": "list", "ordered": ordered, "items": items,
                           "y": top, "x": left})
            continue

        joined = join_lines(texts)
        level = levels.get(block_lines[0].size)
        if level is not None and len(joined) <= 120:
            blocks.append({"type": "heading", "level": level, "text": joined,
                           "y": top, "x": left})
            continue

        if joined:
            blocks.append({"type": "paragraph", "text": joined, "y": top, "x": left})

    for index, table in enumerate(page.get("tables", [])):
        blocks.append({"type": "table", "index": index, "text": table["text"],
                       "y": round(float(table["bbox"][1]), 2),
                       "x": float(table["bbox"][0])})

    if len(columns) > 1:
        blocks.sort(key=lambda block: (_column_index(block["x"], columns), block["y"]))
    else:
        blocks.sort(key=lambda block: block["y"])
    for block in blocks:
        block.pop("x", None)
    return blocks, suspect


# --------------------------------------------------------------------------
# Step
# --------------------------------------------------------------------------

def load_pages(pages_base_dir: Path, record: dict) -> list:
    """Read a document's per-page JSON sidecars, in page order."""
    pages = []
    for entry in sorted(record.get("pages", []), key=lambda e: e["number"]):
        pages.append(read_json(Path(pages_base_dir) / entry["file"]))
    return pages


def _error(step_dir, error_type: str, message: str, context: dict) -> None:
    append_error(step_dir, {
        "step": STEP_NAME,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "error_type": error_type,
        "error_message": message,
        "context": context,
    })


def clean_document(pages: list):
    """Reflow one document's pages into blocks.

    `body_size` and heading levels are computed from this document's pages
    alone: a batch run over many documents must not let one document's
    typography set another document's heading threshold.

    Returns `(body_size, cleaned_pages, suspect_page_numbers)`.
    """
    body = body_size(pages)
    levels = heading_levels(pages, body)
    repeated = repeated_keys(pages)

    cleaned, suspect_pages = [], []
    for page in pages:
        blocks, suspect = blocks_for_page(page, body, repeated, levels)
        cleaned.append({"number": page["number"], "blocks": blocks})
        if suspect:
            suspect_pages.append(page["number"])
    return body, cleaned, suspect_pages


def process(upstream_records, pages_base_dir, step_dir, writer, doc_slug=None, verbose=False):
    """Reflow every document's extracted spans into typed blocks per page."""
    step_dir = Path(step_dir)
    pages_base_dir = Path(pages_base_dir)
    write_json(step_dir / "errors.json", [])

    documents = upstream_records
    if doc_slug is not None:
        documents = [r for r in documents if r["doc_slug"] == doc_slug]

    for record in documents:
        slug = record["doc_slug"]
        if writer.is_processed(slug):
            continue
        if verbose:
            print(f"  {record.get('doc_title') or slug} ...", end=" ", flush=True)

        try:
            pages = load_pages(pages_base_dir, record)
            body, cleaned, suspect_pages = clean_document(pages)
        except Exception as e:
            # A missing page sidecar, corrupted page JSON, or a page shaped in
            # a way this step's reflow does not expect must not abort a
            # twenty-document run — log it and move on, the same isolation
            # extract_pages applies with PageExtractionFailed and
            # extract_figures applies with DocumentFigureExtractionFailed.
            _error(step_dir, "CleanTextFailed", str(e), {"doc_slug": slug})
            writer.append([])
            if verbose:
                print("[error]", flush=True)
            continue

        for number in suspect_pages:
            # Informational, not fatal, and not something this step tries to
            # fix: complex multi-column layout solving is explicitly out of
            # scope, and PyMuPDF's own ordering is trusted as-is otherwise.
            _error(step_dir, "SuspectReadingOrder",
                   "Spans within a block run backward in y by more than "
                   f"{READING_ORDER_TOLERANCE}pt; PyMuPDF's own reading order "
                   "may be wrong for this page (e.g. a complex multi-column "
                   "layout). Not corrected — informational only.",
                   {"doc_slug": slug, "page": number})

        total_blocks = sum(len(p["blocks"]) for p in cleaned)
        writer.append([{"doc_slug": slug, "body_size": body, "pages": cleaned}])
        if verbose:
            print(f"{total_blocks} block(s)", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Reflow each document's extracted spans into readable blocks: "
                     "headings, paragraphs, lists and tables")
    parser.add_argument("--input", required=True,
                        help="Path to extract_pages/output.json")
    parser.add_argument("--output", default=None, help="Path to write output.json")
    parser.add_argument("--force", action="store_true", help="Re-clean every document")
    parser.add_argument("--verbose", action="store_true", help="Print progress")
    add_doc_arg(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output) if args.output else step_dir / "output.json"

    input_path = Path(args.input)
    upstream_records = read_json(input_path).get("results", [])
    pages_base_dir = input_path.parent

    writer = IncrementalWriter(output_path, STEP_NAME, key_field="doc_slug",
                               force=args.force, target_key=args.doc)
    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")

    process(upstream_records, pages_base_dir, step_dir, writer,
            doc_slug=args.doc, verbose=args.verbose)

    count = writer.finalize()
    write_status(step_dir, count)
    print(f"Wrote {count} of {len(upstream_records)} document block record(s) "
          f"to {output_path}")


if __name__ == "__main__":
    main()
