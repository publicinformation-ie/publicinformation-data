#!/usr/bin/env python3
"""Annotation helper: render a document's contents pages and draft a gold file.

Gold must not be produced from detector output — a reviewer shown the detector's
answer tends to accept it, which biases the gold toward the thing it measures.
So this helper reads only the **PDF's text layer**:

* it finds the first contents listing and renders those pages to PNG;
* it transcribes the top-level entries into a draft (`reviewed: false`);
* it locates each entry's body page by searching the text layer after the
  contents pages, and renders that page too.

Everything goes to a gitignored scratch directory. The reviewer checks each
entry against the images, fills in the fields the draft cannot know, and only
then moves the file to `eval/gold/<doc_slug>.json` with `reviewed: true`.

    cd pipelines/document_pipeline
    PYTHONPATH=".:../../src" python steps/detect_structure/eval/annotate.py <doc_slug>
    # → .scratch/detect-structure-gold/<doc_slug>/draft.json and page-*.png

Rules for the finished file are in `eval/gold/GUIDELINE.md`.
"""
import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

_HERE = Path(__file__).parent
_DOC_PIPELINE = _HERE.parents[2]
REPO_ROOT = _DOC_PIPELINE.parents[1]
sys.path.insert(0, str(_HERE))

try:  # imported as a module from the test suite
    from .gold import normalise_title, strip_leading_number
except ImportError:  # run as a script, as the docstring says
    from gold import normalise_title, strip_leading_number

FETCH_PDFS_OUTPUT = _DOC_PIPELINE / "steps" / "fetch_pdfs" / "output.json"
PDF_DIR = _DOC_PIPELINE / "steps" / "fetch_pdfs" / "pdfs"
SCRATCH_DIR = REPO_ROOT / ".scratch" / "detect-structure-gold"
GOLD_DIR = _HERE / "gold"

TOC_TITLE_RE = re.compile(r"(?:^|\|)\s*(?:table of\s+)?contents\s*$", re.I)
_LIST_OF_RE = re.compile(r"^list of (figures|tables|maps|boxes|photographs|appendices|"
                         r"abbreviations|acronyms)", re.I)
# A page label: arabic or a valid roman numeral.
_ROMAN_RE = re.compile(r"^(?=[ivxlcdm])m{0,4}(?:cm|cd|d?c{0,3})(?:xc|xl|l?x{0,3})"
                       r"(?:ix|iv|v?i{0,3})$", re.I)
# A title and its page label on one line, joined by dot leaders (`. . . .`).
_LEADER_LABEL_RE = re.compile(
    r"^(?P<title>.*?\S)\s*(?:[.\u2026\u00b7]\s*){2,}(?P<page>\d{1,4}|[ivxlcdm]{1,7})$",
    re.I)
_INDENT_TOLERANCE = 2.5    # points; this close to a column's leftmost is top level
_ROW_TOLERANCE = 2.0       # points; lines this close share a baseline (one TOC row)
_LABEL_GAP = 25.0          # points; a bare number this far from the title is its page
_COLUMN_GAP = 0.25         # share of page width separating two TOC columns


def _clean(text: str) -> str:
    """Collapse extraction artifacts: control characters, thin spaces, runs."""
    value = re.sub(r"[\x00-\x1f\x7f]", " ", text or "")
    value = re.sub(r"\s+", " ", value).strip()
    # A leading `|` is a coloured-bar artifact from the TOC's design, not text.
    return re.sub(r"^[|\s]+", "", value)


def _is_page_label_text(text: str) -> bool:
    text = (text or "").strip()
    return bool(text) and (text.isdigit() or bool(_ROMAN_RE.match(text)))


def _is_toc_heading(text: str) -> bool:
    norm = _clean(text).casefold()
    if not norm or len(norm) > 80:
        return False
    return bool(TOC_TITLE_RE.search(norm)) or norm.startswith("contents ")


def _is_furniture(text: str, repeated: set) -> bool:
    """Lines that are page furniture, not part of an entry's title."""
    text = text.strip()
    if not text or text in repeated:
        return True
    if _is_toc_heading(text) or _LIST_OF_RE.match(text):
        return True
    # A lone number/roman numeral is a page label or the contents page's own
    # folio, never a title.
    return _is_page_label_text(text)


def _rows(lines: list) -> list:
    """Group lines sharing a baseline into rows, each sorted left to right."""
    rows = []
    for line in sorted(lines, key=lambda item: (item["y0"], item["x0"])):
        if rows and abs(line["y0"] - rows[-1][0]["y0"]) <= _ROW_TOLERANCE:
            rows[-1].append(line)
        else:
            rows.append([line])
    for row in rows:
        row.sort(key=lambda item: item["x0"])
    return rows


def _row_entry(row: list, page_width: float, repeated: set):
    """Turn one contents row into `{title, printed_page, x0, y0}`, or None.

    Handles the three layouts PDFs actually use: a separate right-hand page
    label column, a label inside the same line after dot leaders, and a
    two-column listing where the page number follows the title across a gap.
    """
    if not row:
        return None
    page_label = None
    title_segments = row
    last = row[-1]
    if len(row) > 1 and _is_page_label_text(last["text"]):
        gap = last["x0"] - row[-2]["x1"]
        if last["x0"] >= page_width * 0.6 or gap >= _LABEL_GAP:
            page_label = last["text"].strip()
            title_segments = row[:-1]

    title = _clean(" ".join(segment["text"] for segment in title_segments))
    if page_label is None:
        match = _LEADER_LABEL_RE.match(title)
        if match and _is_page_label_text(match.group("page")):
            title = _clean(match.group("title"))
            page_label = match.group("page")

    title = _clean(title.rstrip(" .\u00b7\u2026"))
    if not title or _is_furniture(title, repeated) or page_label is None:
        # An entry without a readable page label is either a title fragment
        # (joined to the row below by _page_entries) or a TOC line the
        # extraction lost. The reviewer adds the rare genuinely unnumbered
        # entry from the image.
        return None
    return {"title": title, "printed_page": page_label,
            "x0": row[0]["x0"], "y0": row[0]["y0"]}


def _page_entries(page: dict, repeated: set) -> list:
    """Every entry-shaped row on one contents page, before the top-level filter.

    A title may wrap onto the next row while its page number sits only on the
    last one, so a row that produced no entry is held and prepended to the next
    entry in the same column (a `CHAPTER 1:` label row above `Introduction 6`,
    or a long heading split over two lines).
    """
    entries = []
    pending = []
    for row in _rows(page["lines"]):
        entry = _row_entry(row, page["width"], repeated)
        if entry is None:
            text = _clean(" ".join(segment["text"] for segment in row))
            if not text or _is_furniture(text, repeated):
                pending = []   # furniture breaks a wrapped title
            else:
                pending.append({"text": text, "x0": row[0]["x0"], "y0": row[0]["y0"]})
            continue
        parts = [part for part in pending
                 if abs(part["x0"] - entry["x0"]) <= 40.0
                 and 0 <= entry["y0"] - part["y0"] <= 35]
        if parts:
            entry["title"] = _clean(" ".join([part["text"] for part in parts]
                                             + [entry["title"]]))
            entry["x0"] = min(entry["x0"], parts[0]["x0"])
        pending = []
        entries.append(entry)
    return entries


def _columns(entries: list, page_width: float) -> list:
    """Cluster entries into columns by left edge (a two-column TOC has two)."""
    columns = []
    for x0 in sorted({entry["x0"] for entry in entries}):
        if not columns or x0 - columns[-1] > page_width * _COLUMN_GAP:
            columns.append(x0)
    return columns


def _top_level(entries: list, page_width: float) -> list:
    """Keep, per column, the entries in that column's leftmost indent."""
    columns = _columns(entries, page_width)
    kept = []
    for index, column in enumerate(columns):
        upper = columns[index + 1] if index + 1 < len(columns) else float("inf")
        in_column = [entry for entry in entries if column <= entry["x0"] < upper]
        if not in_column:
            continue
        leftmost = min(entry["x0"] for entry in in_column)
        kept.extend(entry for entry in in_column
                    if entry["x0"] <= leftmost + _INDENT_TOLERANCE)
    return kept


def parse_entries(pages: list) -> list:
    """Top-level entries from a contents listing, transcribed from its text layer.

    `pages` are layout dicts (`width`, `lines`) in TOC order. Within a page,
    entries are returned column by column, then top to bottom, so the result is
    the printed reading order and the draft's pages stay increasing.
    """
    counts = {}
    for page in pages:
        for text in {line["text"].strip() for line in page["lines"]}:
            counts[text] = counts.get(text, 0) + 1
    repeated = {text for text, count in counts.items() if count >= 2}

    entries = []
    for page in pages:
        page_entries = _page_entries(page, repeated)
        page_entries = _top_level(page_entries, page["width"])
        columns = _columns(page_entries, page["width"])
        page_entries.sort(key=lambda entry: (
            _column_of(entry["x0"], columns), entry["y0"], entry["x0"]))
        entries.extend(page_entries)
    return [{"title": entry["title"], "printed_page": entry["printed_page"]}
            for entry in entries]


def _column_of(x0: float, columns: list) -> int:
    index = 0
    for position, column in enumerate(columns):
        if x0 >= column:
            index = position
    return index


def _page_layout(page) -> dict:
    """A rendered PDF page's text lines with position, in reading order."""
    lines = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            text = "".join(span.get("text") or "" for span in line.get("spans", [])).strip()
            if text:
                lines.append({"text": text,
                              "x0": float(line["bbox"][0]),
                              "x1": float(line["bbox"][2]),
                              "y0": float(line["bbox"][1])})
    return {"width": float(page.rect.width), "height": float(page.rect.height),
            "lines": lines}


def find_toc_pages(pages: list) -> list:
    """The first contiguous block of contents pages, 1-indexed.

    The block starts at the page whose top carries a Contents/Table of Contents
    heading and continues while pages still carry entry-shaped rows. A List of
    Figures/Tables page ends the block, so it cannot leak entries in.
    """
    start = None
    for page in pages:
        for line in page["lines"]:
            if line["y0"] <= page["height"] * 0.25 and _is_toc_heading(line["text"]):
                start = page["number"]
                break
        if start is not None:
            break
    if start is None:
        return []

    by_number = {page["number"]: page for page in pages}
    toc_pages = [start]
    for number in range(start + 1, start + 10):
        page = by_number.get(number)
        if page is None:
            break
        head = sorted(page["lines"], key=lambda line: (line["y0"], line["x0"]))[:4]
        if any(_LIST_OF_RE.match(_clean(line["text"])) for line in head):
            break
        if len(_page_entries(page, set())) < 3:
            break
        toc_pages.append(number)
    return toc_pages


def find_start_page(page_layouts: list, title: str, after_page: int, min_page: int = 0):
    """First body page where the title is set as a heading-like line.

    Matches a whole line (or two consecutive lines, for a wrapped heading)
    after normalisation — not a substring of a paragraph, which would latch
    onto a prose mention or a cross-reference. `min_page` keeps the draft
    monotonic: each chapter is searched for after the previous one, so an
    identical subheading earlier in the document cannot win twice.
    """
    want = normalise_title(title)
    if not want:
        return None
    for page in page_layouts:
        number = page["number"]
        if number <= after_page or number < min_page:
            continue
        lines = sorted(page["lines"], key=lambda line: (line["y0"], line["x0"]))
        for index, line in enumerate(lines):
            if normalise_title(line["text"]) == want:
                return number
            following = lines[index + 1]["text"] if index + 1 < len(lines) else ""
            if following and normalise_title(f"{line['text']} {following}") == want:
                return number
    return None


def read_pdf(doc_slug: str, pdf_path=None):
    """Open the document's PDF, from fetch_pdfs output or the cache directory."""
    import pymupdf

    if pdf_path is None:
        record = None
        if FETCH_PDFS_OUTPUT.exists():
            records = json.loads(FETCH_PDFS_OUTPUT.read_text(encoding="utf-8"))["results"]
            record = next((r for r in records if r["doc_slug"] == doc_slug), None)
        pdf_path = (FETCH_PDFS_OUTPUT.parent / record["pdf_path"]) if record else \
            PDF_DIR / f"{doc_slug}.pdf"
    path = Path(pdf_path)
    if not path.exists():
        raise SystemExit(f"{path} is missing — run the fetch_pdfs step for {doc_slug!r}")
    return pymupdf.open(str(path)), path


def source_sha256(doc_slug: str) -> str:
    if not FETCH_PDFS_OUTPUT.exists():
        raise SystemExit(f"{FETCH_PDFS_OUTPUT} is missing — run the fetch_pdfs step first")
    records = json.loads(FETCH_PDFS_OUTPUT.read_text(encoding="utf-8"))["results"]
    record = next((r for r in records if r["doc_slug"] == doc_slug), None)
    if not record or not record.get("source_sha256"):
        raise SystemExit(f"fetch_pdfs output has no source_sha256 for {doc_slug!r}")
    return record["source_sha256"]


def _render(doc, numbers: list, out_dir: Path, prefix: str, dpi: int = 110) -> list:
    written = []
    for number in sorted(set(numbers)):
        pix = doc[number - 1].get_pixmap(dpi=dpi)
        path = out_dir / f"{prefix}-{number:03d}.png"
        pix.save(str(path))
        written.append(path)
    return written


def annotate(doc_slug: str, pdf_path=None, scratch_dir=SCRATCH_DIR, today=None) -> dict:
    """Draft a gold file and render the pages needed to review it."""
    doc, path = read_pdf(doc_slug, pdf_path)
    try:
        pages = [{"number": number, **_page_layout(doc[number - 1])}
                 for number in range(1, min(doc.page_count, 40) + 1)]
        toc_pages = find_toc_pages(pages)
        if not toc_pages:
            raise SystemExit(
                f"{doc_slug}: no contents page found in the first {len(pages)} pages. "
                "If it truly has none, add it to eval/gold/no_toc.json with a reason.")

        entries = parse_entries([page for page in pages if page["number"] in toc_pages])
        if not entries:
            raise SystemExit(f"{doc_slug}: contents pages {toc_pages} produced no top-level entries")

        body_pages = [{"number": number, **_page_layout(doc[number - 1])}
                      for number in range(1, doc.page_count + 1)]
        last_toc = max(toc_pages)
        unresolved = []
        chapters = []
        previous_page = 0
        for entry in entries:
            title = strip_leading_number(entry["title"])
            page = find_start_page(body_pages, title, last_toc, min_page=previous_page + 1)
            if page is None:
                unresolved.append(title)
            else:
                previous_page = page
            chapters.append({"title": title,
                             "printed_page": entry["printed_page"],
                             "pdf_page": page})

        out_dir = Path(scratch_dir) / doc_slug
        out_dir.mkdir(parents=True, exist_ok=True)
        _render(doc, toc_pages, out_dir, "toc")
        _render(doc, [c["pdf_page"] for c in chapters if c["pdf_page"]], out_dir, "page")

        draft = {
            "doc_slug": doc_slug,
            "pdf_sha256": source_sha256(doc_slug),
            "toc_pdf_pages": toc_pages,
            "annotator": "",
            "annotated_on": (today or date.today()).isoformat(),
            "reviewed": False,
            "notes": ("DRAFT from the contents pages' text layer. Every pdf_page is a "
                      "text search after the contents pages, not a verified position: check "
                      "each chapter start on page-*.png, correct titles and pages, and only "
                      "then set reviewed to true."),
            "chapters": chapters,
        }
        draft_path = out_dir / "draft.json"
        draft_path.write_text(json.dumps(draft, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")
    finally:
        doc.close()

    print(f"{doc_slug}: {len(chapters)} chapters from contents pages {toc_pages}")
    print(f"  images: {out_dir}")
    print(f"  draft:  {draft_path}  (reviewed: false)")
    if unresolved:
        print(f"  {len(unresolved)} title(s) not found in the body text layer — set their "
              "pdf_page by hand:")
        for title in unresolved:
            print(f"    - {title}")
    print(f"  When reviewed, move it to {GOLD_DIR / (doc_slug + '.json')}")
    return draft


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Render contents/candidate pages and draft a gold chapter list")
    parser.add_argument("doc_slug", help="document slug, as in documents.yml")
    parser.add_argument("--pdf", help="PDF path (default: from fetch_pdfs output)")
    parser.add_argument("--scratch", default=str(SCRATCH_DIR),
                        help=f"gitignored output directory (default: {SCRATCH_DIR})")
    args = parser.parse_args(argv)
    annotate(args.doc_slug, pdf_path=args.pdf, scratch_dir=Path(args.scratch))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
