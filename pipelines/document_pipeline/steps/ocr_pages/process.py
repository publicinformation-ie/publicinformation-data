#!/usr/bin/env python3
"""Step: ocr_pages — read curator-listed image-only pages with Tesseract.

Some PDFs contain pages that are a single full-page raster image with no text
layer (a scanned or screenshot page inside an otherwise digital document).
`extract_pages` finds no text there, so the page would be a coverage gap. This
step gives those pages a text layer, and nothing else.

OCR is strictly **opt-in per page**: the curator lists 1-based page numbers
under `ocr_pages` in documents.yml (carried through `fetch_pdfs/output.json`).
Unlisted pages are never OCR'd, however image-like; documents with no
`ocr_pages` pass through without their PDF being opened. A listed page that is
not actually a scanned full-page image (it has a real text layer, no
full-page image, or does not exist) is not OCR'd and is logged as
`OcrPageNotScanned` — the curator listed the wrong page.

Output has the same shape as `extract_pages/output.json`, so `clean_text`
reads it unchanged. `extract_pages/pages/*` is never modified: a page that was
not OCR'd is pointed at the upstream page file (path relative to this step's
directory, since `clean_text` resolves page files against its input's parent);
an OCR'd page is a merged copy (native spans + OCR spans marked
`source: "ocr"`, plus an `ocr` summary) written to `pages/<doc_slug>/NNN.json`
here. OCR spans have the native span shape, one per recognised line.

Empty OCR (`OcrEmpty`) leaves the page without text; low-confidence OCR
(`OcrLowConfidence`, mean word confidence < OCR_MIN_CONFIDENCE) still emits
its text. Both are logged to errors.json for human review.
"""
import argparse
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pymupdf

from lib.cli_utils import add_doc_arg
from lib.file_utils import IncrementalWriter, append_error, read_json, write_json, write_status
from lib.ocr import OCR_DPI, OCR_LANG, OCR_PSM, mean_confidence, ocr_words

STEP_NAME = "ocr_pages"

OCR_MIN_CONFIDENCE = 60.0       # page mean word confidence below this is logged for review
OCR_MIN_IMAGE_COVERAGE = 0.75   # one image must cover this share of the page to count as a scan
OCR_MAX_NATIVE_LETTERS = 20     # native letters above which the page has a real text layer
OCR_FONT = "tesseract-ocr"


def _round_seq(values) -> list:
    return [round(float(v), 2) for v in values]


def is_scanned_page(page: pymupdf.Page, spans: list) -> bool:
    """True for a full-page raster image whose text layer is absent or only
    incidental (a printed page number)."""
    letters = sum(1 for span in spans for ch in span["text"] if ch.isalpha())
    if letters > OCR_MAX_NATIVE_LETTERS:
        return False
    page_area = float(page.rect.width * page.rect.height)
    if page_area <= 0:
        return False
    for info in page.get_images(full=True):
        for rect in page.get_image_rects(info[0]):
            clipped = rect & page.rect
            if (not clipped.is_empty
                    and clipped.width * clipped.height >= OCR_MIN_IMAGE_COVERAGE * page_area):
                return True
    return False


def _contains(bbox, x: float, y: float) -> bool:
    return bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]


def ocr_page_spans(page: pymupdf.Page, native_spans: list) -> "tuple[list, dict]":
    """OCR one page: render at OCR_DPI, run Tesseract (fixed psm/lang), return
    `(spans, summary)`. Spans match the native span shape (one per recognised
    line, bbox in page points) plus `source: "ocr"`; their `block` indices
    start after the native blocks so lines never collide. Words sitting on a
    native span (e.g. a printed page number) are skipped. A pure function of
    the rendered pixels, so output is deterministic."""
    from PIL import Image

    pix = page.get_pixmap(dpi=OCR_DPI)
    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    words = ocr_words(image)
    scale = 72.0 / OCR_DPI
    native_boxes = [s["bbox"] for s in native_spans]

    kept = []
    for w in words:
        x0, y0 = w["left"] * scale, w["top"] * scale
        x1, y1 = (w["left"] + w["width"]) * scale, (w["top"] + w["height"]) * scale
        if any(_contains(b, (x0 + x1) / 2, (y0 + y1) / 2) for b in native_boxes):
            continue
        kept.append((w, (x0, y0, x1, y1)))

    base_block = max((s["block"] for s in native_spans), default=-1) + 1
    lines: dict = {}
    for w, box in kept:
        lines.setdefault((w["block"], w["par"], w["line"]), []).append((w, box))

    spans, block_ids, line_counts = [], {}, {}
    for key in sorted(lines):
        group = sorted(lines[key], key=lambda item: item[0]["word"])
        tess_block = key[0]
        if tess_block not in block_ids:
            block_ids[tess_block] = base_block + len(block_ids)
            line_counts[tess_block] = 0
        heights = sorted(box[3] - box[1] for _, box in group)
        spans.append({
            "text": " ".join(w["text"] for w, _ in group),
            "font": OCR_FONT,
            "size": float(round(heights[len(heights) // 2])),
            "bbox": _round_seq([min(b[0] for _, b in group), min(b[1] for _, b in group),
                                max(b[2] for _, b in group), max(b[3] for _, b in group)]),
            "block": block_ids[tess_block],
            "line": line_counts[tess_block],
            "span": 0,
            "source": "ocr",
        })
        line_counts[tess_block] += 1

    confidence = mean_confidence([w for w, _ in kept])
    summary = {
        "engine": "tesseract",
        "lang": OCR_LANG,
        "psm": OCR_PSM,
        "dpi": OCR_DPI,
        "word_count": len(kept),
        "mean_confidence": None if confidence is None else round(confidence, 1),
    }
    return spans, summary


def _log(step_dir, slug: str, page_number: int, error_type: str, message: str,
         extra: "dict | None" = None) -> None:
    append_error(step_dir, {
        "step": STEP_NAME,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "error_type": error_type,
        "error_message": message,
        "context": {"doc_slug": slug, "page": page_number, **(extra or {})},
    })


def _log_ocr_review(step_dir, slug: str, number: int, ocr: dict) -> None:
    """Flag OCR pages a human should check."""
    if ocr["word_count"] == 0:
        _log(step_dir, slug, number, "OcrEmpty",
             "OCR found no text on this listed page; the page stays uncovered. Review it.")
    elif ocr["mean_confidence"] < OCR_MIN_CONFIDENCE:
        _log(step_dir, slug, number, "OcrLowConfidence",
             f"OCR mean word confidence {ocr['mean_confidence']} is below "
             f"{OCR_MIN_CONFIDENCE}; the text is emitted but needs human review.",
             {"mean_confidence": ocr["mean_confidence"]})


def _upstream_pointer(pages_base_dir: Path, step_dir: Path, entry: dict) -> str:
    """`entry["file"]` re-expressed relative to this step's directory, so a
    consumer joining it onto this step's output.json parent finds the
    unchanged upstream page file."""
    target = Path(pages_base_dir) / entry["file"]
    return Path(os.path.relpath(target, step_dir)).as_posix()


def ocr_document(record, pages_base_dir, pdf_path, listed, step_dir, slug) -> dict:
    """Build this step's record for one document with a non-empty `listed`."""
    pages_base_dir, step_dir = Path(pages_base_dir), Path(step_dir)
    out_dir = step_dir / "pages" / slug
    if out_dir.exists():
        shutil.rmtree(out_dir)      # never leave a stale OCR page behind
    out_dir.mkdir(parents=True, exist_ok=True)

    page_count = int(record["page_count"])
    for number in sorted(n for n in listed if n > page_count):
        _log(step_dir, slug, number, "OcrPageNotScanned",
             f"ocr_pages lists page {number} but the document has only {page_count} "
             f"pages; check documents.yml.")

    entries = []
    pdf = pymupdf.open(str(pdf_path))
    try:
        for entry in record["pages"]:
            number = entry["number"]
            new_entry = dict(entry)
            new_entry["file"] = _upstream_pointer(pages_base_dir, step_dir, entry)
            if number in listed:
                page_json = read_json(pages_base_dir / entry["file"])
                if not is_scanned_page(pdf[number - 1], page_json["spans"]):
                    _log(step_dir, slug, number, "OcrPageNotScanned",
                         "ocr_pages lists this page but it is not a full-page image "
                         "without a text layer, so it was not OCR'd; check documents.yml.")
                else:
                    spans, summary = ocr_page_spans(pdf[number - 1], page_json["spans"])
                    merged = {**page_json, "spans": page_json["spans"] + spans, "ocr": summary}
                    relative = f"pages/{slug}/{Path(entry['file']).name}"
                    write_json(step_dir / relative, merged)
                    new_entry["file"] = relative
                    new_entry["span_count"] = len(merged["spans"])
                    _log_ocr_review(step_dir, slug, number, summary)
            entries.append(new_entry)
    finally:
        pdf.close()
    return {**record, "pages": entries}


def process(upstream_records, pages_base_dir, pdf_paths, ocr_config, step_dir, writer,
            doc_slug=None, verbose=False):
    """`pdf_paths` maps doc_slug -> source PDF; `ocr_config` maps doc_slug ->
    the curator's `ocr_pages` list. Documents without a list pass through."""
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

        listed = set(ocr_config.get(slug) or [])
        try:
            if not listed:
                result = {**record, "pages": [
                    {**e, "file": _upstream_pointer(pages_base_dir, step_dir, e)}
                    for e in record["pages"]]}
                stale = step_dir / "pages" / slug
                if stale.exists():
                    shutil.rmtree(stale)
            else:
                pdf_path = pdf_paths.get(slug)
                if pdf_path is None or not Path(pdf_path).exists():
                    raise FileNotFoundError(f"source PDF not found: {pdf_path}")
                result = ocr_document(record, pages_base_dir, pdf_path, listed, step_dir, slug)
        except Exception as e:
            # Fail closed: no record, so the document cannot publish without
            # the text its curator asked for. Isolated like every other step.
            _log(step_dir, slug, 0, "OcrFailed", str(e))
            writer.append([])
            if verbose:
                print("[error]", flush=True)
            continue

        writer.append([result])
        if verbose:
            print(f"{len(listed)} page(s) requested" if listed else "[pass-through]", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="OCR the pages listed under ocr_pages in documents.yml; "
                    "pass every other page through unchanged")
    parser.add_argument("--input", required=True, help="Path to extract_pages/output.json")
    parser.add_argument("--output", default=None, help="Path to write output.json")
    parser.add_argument("--force", action="store_true", help="Re-process every document")
    parser.add_argument("--verbose", action="store_true", help="Print progress")
    add_doc_arg(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output) if args.output else step_dir / "output.json"

    input_path = Path(args.input)
    upstream_records = read_json(input_path).get("results", [])
    pages_base_dir = input_path.parent

    fetch_dir = step_dir.parent / "fetch_pdfs"
    fetch_output = fetch_dir / "output.json"
    pdf_paths, ocr_config = {}, {}
    if fetch_output.exists():
        for record in read_json(fetch_output).get("results", []):
            if record.get("pdf_path"):
                pdf_paths[record["doc_slug"]] = fetch_dir / record["pdf_path"]
            if record.get("ocr_pages"):
                ocr_config[record["doc_slug"]] = record["ocr_pages"]

    writer = IncrementalWriter(output_path, STEP_NAME, key_field="doc_slug",
                               force=args.force, target_key=args.doc)
    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")

    process(upstream_records, pages_base_dir, pdf_paths, ocr_config, step_dir, writer,
            doc_slug=args.doc, verbose=args.verbose)

    count = writer.finalize()
    write_status(step_dir, count)
    print(f"Wrote {count} of {len(upstream_records)} document page-index record(s) "
          f"to {output_path}")


if __name__ == "__main__":
    main()
