#!/usr/bin/env python3
"""Step: extract_pages — the only step in document_pipeline that interprets
PDF content. Every step downstream of this one reads only the JSON written
here and never opens a PDF again (except extract_figures, which reopens it
purely as a rasteriser, never to ask what its content means).

For each document, opens its source PDF exactly once, walks every page
collecting text spans, vector drawings, images, and tables, and writes one
`pages/<doc_slug>/NNN.json` file per page plus a summary record — with a
`file`/`width`/`height`/`rotation`/`span_count` index entry per page — to
output.json. Coordinates are rounded to 2 decimal places on write so the
per-page JSON files stay small, diffable, and hand-inspectable, which matters
because every later task treats them as an intermediate representation.

A document where every page's text is empty or whitespace-only (i.e. a
scanned document with no text layer) is not a per-page problem: it is logged
as one `NoTextLayer` error and the whole document is skipped, with no partial
record written to output.json. OCR is out of scope for this pipeline.

Nothing here is process-fatal except a malformed documents.yml (caught
upstream). A PDF can pass fetch_pdfs's shallow open()-and-inspect check yet
have a content stream malformed enough that pymupdf raises deep inside
get_text, get_drawings, get_images, or find_tables; that failure is caught
per document, logged to errors.json as `PageExtractionFailed`, and the
document is skipped so one bad PDF can't abort the rest of the batch.

Ported from pdf2site's plan (source plan Task 6, lines 1592-1973): the span,
drawing, image, and table extraction, and the find_tables() handling. Adapted
to write per-document `pages/<doc_slug>/` directories instead of a flat
`pages/`, to treat "no text layer" as a per-document errors.json entry and
skip rather than a fatal exit, to round every coordinate (not just spans) to
2 decimal places, and to open each PDF exactly once regardless of page count.
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path

import pymupdf

from lib.cli_utils import add_doc_arg
from lib.file_utils import IncrementalWriter, append_error, read_json, write_json, write_status

STEP_NAME = "extract_pages"


def _round_seq(values) -> list:
    return [round(float(v), 2) for v in values]


def extract_spans(page: pymupdf.Page) -> list:
    spans = []
    text = page.get_text("dict")
    for b_index, block in enumerate(text.get("blocks", [])):
        for l_index, line in enumerate(block.get("lines", [])):
            for s_index, span in enumerate(line.get("spans", [])):
                if not span["text"].strip():
                    continue
                spans.append({
                    "text": span["text"],
                    "font": span["font"],
                    "size": round(float(span["size"]), 2),
                    "bbox": _round_seq(span["bbox"]),
                    "block": b_index,
                    "line": l_index,
                    "span": s_index,
                })
    return spans


def extract_drawings(page: pymupdf.Page) -> list:
    drawings = []
    for drawing in page.get_drawings():
        rect = drawing.get("rect")
        if rect is None or rect.is_empty:
            continue
        drawings.append({
            "bbox": _round_seq(rect),
            "fill": drawing.get("fill") is not None,
            "width": round(float(drawing.get("width") or 0.0), 2),
        })
    return drawings


def extract_images(page: pymupdf.Page) -> list:
    images = []
    for info in page.get_images(full=True):
        xref, width, height = info[0], info[2], info[3]
        for rect in page.get_image_rects(xref):
            images.append({
                "xref": int(xref),
                "bbox": _round_seq(rect),
                "width": int(width),
                "height": int(height),
            })
    return images


# A table's true header sometimes sits just above PyMuPDF's detected grid: the
# header text has no fill-rectangle tying it to the body, so find_tables()
# never includes it as row 0 and it leaks into the ordinary text stream
# instead (see extract_action_status's "Known limitations" — this is that
# root cause, fixed at its source). Reconstructed from column-aligned text
# spans directly above the grid, never from content further away, so a
# caption or narrative paragraph above a table isn't mistaken for its header.
_HEADER_GAP_MAX = 50.0   # max distance (pt) from a candidate span to the grid top
_HEADER_TOUCH_MAX = 10.0  # max gap (pt) between the candidate block and the grid — contiguity
_HEADER_CELL_MAX_LEN = 40  # a genuine header cell is a short label, not a sentence


def _column_ranges(cells) -> list:
    xs = sorted({(round(c[0], 2), round(c[2], 2)) for c in cells if c})
    return xs


def _reconstruct_header_row(page: pymupdf.Page, table, other_bboxes) -> "tuple | None":
    """(header_row, top_y) reconstructed from text floating above `table`'s
    grid, or None if no plausible header is found there."""
    columns = _column_ranges(table.cells)
    min_columns = max(2, (len(columns) + 1) // 2)
    x0_tbl, y0_tbl, x1_tbl = table.bbox[0], table.bbox[1], table.bbox[2]

    candidates = []
    text_dict: dict = page.get_text("dict")  # type: ignore[assignment]
    for block in text_dict.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span["text"].strip()
                if not text:
                    continue
                sx0, sy0, sx1, sy1 = span["bbox"]
                if sy1 > y0_tbl or y0_tbl - sy0 > _HEADER_GAP_MAX:
                    continue
                if sx1 < x0_tbl - 1 or sx0 > x1_tbl + 1:
                    continue
                if any(bx0 <= sx0 <= bx1 and by0 <= sy0 <= by1
                       for bx0, by0, bx1, by1 in other_bboxes):
                    continue  # belongs to a different table on the page
                candidates.append((sy0, sy1, sx0, sx1, text))
    if not candidates:
        return None

    nearest_bottom = max(c[1] for c in candidates)
    if y0_tbl - nearest_bottom > _HEADER_TOUCH_MAX:
        return None

    by_column = {}
    for sy0, sy1, sx0, sx1, text in candidates:
        mid = (sx0 + sx1) / 2
        col = next((i for i, (cx0, cx1) in enumerate(columns) if cx0 - 1 <= mid <= cx1 + 1), None)
        if col is not None:
            by_column.setdefault(col, []).append((sy0, text))
    if len(by_column) < min_columns:
        return None

    row = [" ".join(text for _, text in sorted(by_column.get(i, [])))
           for i in range(len(columns))]
    if not any(row):
        return None
    if any(len(cell) > _HEADER_CELL_MAX_LEN for cell in row):
        return None  # a caption sentence, not a header label
    return row, min(c[0] for c in candidates)


def extract_tables(page: pymupdf.Page) -> list:
    tables = []
    try:
        found = page.find_tables()
    except Exception:  # pragma: no cover - pymupdf can bail on odd pages
        return tables
    all_bboxes = [t.bbox for t in found.tables]
    for table in found.tables:
        bbox = _round_seq(table.bbox)
        rows = int(table.row_count)
        text = [[("" if cell is None else str(cell)) for cell in row]
                for row in table.extract()]

        other_bboxes = [b for b in all_bboxes if b != table.bbox]
        reconstructed = _reconstruct_header_row(page, table, other_bboxes)
        if reconstructed is not None:
            header_row, top_y = reconstructed
            text = [header_row] + text
            rows += 1
            bbox[1] = round(min(bbox[1], top_y), 2)

        tables.append({
            "bbox": bbox,
            "rows": rows,
            "cols": int(table.col_count),
            "cells": [_round_seq(cell) for cell in table.cells if cell],
            "text": text,
        })
    return tables


def extract_outline(doc: pymupdf.Document) -> list:
    outline = []
    for entry in doc.get_toc(simple=False):
        level, title, page_number = entry[0], entry[1], entry[2]
        if page_number < 1:
            continue
        dest = entry[3] if len(entry) > 3 else {}
        point = dest.get("to") if isinstance(dest, dict) else None
        outline.append({
            "level": int(level),
            "title": str(title).strip(),
            "page": int(page_number),
            "y": round(float(point.y), 2) if point is not None else 0.0,
        })
    return outline


def extract_page(page: pymupdf.Page, number: int) -> dict:
    """Extract everything this step records about one page. Module-level so
    tests can monkeypatch it (e.g. to simulate a page with no text spans,
    without needing a real scanned-PDF fixture)."""
    return {
        "number": number,
        "width": round(float(page.rect.width), 2),
        "height": round(float(page.rect.height), 2),
        "rotation": int(page.rotation),
        "spans": extract_spans(page),
        "drawings": extract_drawings(page),
        "images": extract_images(page),
        "tables": extract_tables(page),
    }


def _page_filename(page_number: int, page_count: int) -> str:
    width = 4 if page_count > 999 else 3
    return f"{page_number:0{width}d}.json"


def process(upstream_records, pdf_base_dir, step_dir, writer, doc_slug=None, verbose=False):
    """Extract every document's pages to `pages/<doc_slug>/NNN.json` plus a
    summary record in output.json. A document with no text layer on any page
    logs one NoTextLayer error and is skipped entirely — no partial record."""
    step_dir = Path(step_dir)
    pdf_base_dir = Path(pdf_base_dir)
    write_json(step_dir / "errors.json", [])
    pages_root = step_dir / "pages"
    pages_root.mkdir(parents=True, exist_ok=True)

    documents = upstream_records
    if doc_slug is not None:
        documents = [r for r in documents if r["doc_slug"] == doc_slug]

    for doc in documents:
        slug = doc["doc_slug"]
        if writer.is_processed(slug):
            continue
        if verbose:
            print(f"  {doc['title']} ...", end=" ", flush=True)

        pdf_path = pdf_base_dir / doc["pdf_path"]
        pdf_doc = None
        try:
            try:
                pdf_doc = pymupdf.open(str(pdf_path))
                page_count = pdf_doc.page_count
                page_records = [extract_page(pdf_doc[i], i + 1) for i in range(page_count)]
                outline = extract_outline(pdf_doc)
            finally:
                if pdf_doc is not None:
                    pdf_doc.close()
        except Exception as e:
            # A PDF can pass fetch_pdfs's shallow open()-and-inspect check yet have a
            # content stream malformed enough that pymupdf raises deep inside get_text,
            # get_drawings, get_images, or find_tables. One bad document must not abort
            # a twenty-document run — log it and move on, same as every other per-document
            # failure mode in this pipeline.
            append_error(step_dir, {
                "step": STEP_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": "PageExtractionFailed",
                "error_message": str(e),
                "context": {"doc_slug": slug, "url": doc.get("url")},
            })
            writer.append([])
            if verbose:
                print("[error]", flush=True)
            continue

        total_spans = sum(len(record["spans"]) for record in page_records)
        if total_spans == 0:
            append_error(step_dir, {
                "step": STEP_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": "NoTextLayer",
                "error_message": ("Document appears to be scanned (no text layer on "
                                   "any page); OCR is out of scope."),
                "context": {"doc_slug": slug, "url": doc.get("url")},
            })
            writer.append([])
            if verbose:
                print("[error]", flush=True)
            continue

        doc_pages_dir = pages_root / slug
        doc_pages_dir.mkdir(parents=True, exist_ok=True)

        index = []
        for record in page_records:
            filename = _page_filename(record["number"], page_count)
            relative = f"pages/{slug}/{filename}"
            write_json(step_dir / relative, record)
            index.append({
                "number": record["number"],
                "file": relative,
                "width": record["width"],
                "height": record["height"],
                "rotation": record["rotation"],
                "span_count": len(record["spans"]),
            })

        writer.append([{
            "doc_slug": slug,
            "doc_title": doc.get("title"),
            "page_count": page_count,
            "outline": outline,
            "pages": index,
        }])
        if verbose:
            print("[ok]", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Extract page-level text spans, drawings, images, and tables from "
                     "each document's PDF")
    parser.add_argument("--input", required=True, help="Path to fetch_pdfs/output.json")
    parser.add_argument("--output", default=None, help="Path to write output.json")
    parser.add_argument("--force", action="store_true", help="Re-extract every document")
    parser.add_argument("--verbose", action="store_true", help="Print progress")
    add_doc_arg(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output) if args.output else step_dir / "output.json"

    input_path = Path(args.input)
    upstream = read_json(input_path)
    upstream_records = upstream.get("results", [])
    pdf_base_dir = input_path.parent

    writer = IncrementalWriter(output_path, STEP_NAME, key_field="doc_slug",
                               force=args.force, target_key=args.doc)
    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")

    process(upstream_records, pdf_base_dir, step_dir, writer,
            doc_slug=args.doc, verbose=args.verbose)

    count = writer.finalize()
    write_status(step_dir, count)
    print(f"Wrote {count} of {len(upstream_records)} document page-index record(s) "
          f"to {output_path}")


if __name__ == "__main__":
    main()
