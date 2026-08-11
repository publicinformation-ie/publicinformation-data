#!/usr/bin/env python3
"""Step: extract_figures — decide which regions of a page are figures, render
each one to WebP, and give it a caption.

Two halves. The top half is pure geometry over `(x0, y0, x1, y1)` tuples and
line dicts: furniture rejection, proximity clustering to a fixpoint, area
filtering, prose rejection, caption matching. None of it opens a PDF, so it is
tested against hand-written bboxes in milliseconds. The bottom half reopens the
source PDF, but *only* as a rasteriser: it asks the page to draw a rectangle
and never to explain its content — all interpretation happened in
`extract_pages`. Rendering the clipped **page** rather than extracting the
embedded image is deliberate: a map is vectors, raster tiles and text labels
layered together, and only the rendered page has all three.

Every threshold here is empirical and named at module level. The source design
flags them as the thing most likely to need tuning against a real document,
which is also why this step writes a contact sheet: tuning is a visual task,
and a number whose effect you can see is worth more than a number you can
justify. One document's contact sheet is `contact-sheets/<doc_slug>.html`;
open it and look before touching a constant.

Nothing here is fatal to a document or to the run. A cluster that will not
rasterise is one `FigureRenderFailed` entry in errors.json and the rest of the
document still publishes; a figure with no caption near it is one
`MissingCaption` entry and still gets a record, with `Figure from page N` as
its title. A missing caption is a presentation problem, not a reason to drop a
figure out of the document.

Ported from pdf2site's plan (source plan Tasks 9 and 10, lines 2846-3505): the
geometry, the heuristics, the WebP rendering and the contact sheet. Adapted to
keep the pure functions in this step's own process.py rather than a shared
`lib/figures.py`, to loop over documents rather than run once per document, to
namespace assets as `assets/<doc_slug>/` and contact sheets as
`contact-sheets/<doc_slug>.html` (so `publish_bundles` can copy one directory
per document), to use this repo's `errors.json` envelope with the error types
`FigureRenderFailed`/`MissingCaption` in place of the source's `render_failed`/
`caption_missing`, and to reuse `detect_structure`'s line grouping and body
style rather than introduce a second line model.
"""
import argparse
import re
from datetime import datetime, timezone
from html import escape
from pathlib import Path

import pymupdf

from lib.cli_utils import add_doc_arg
from lib.file_utils import IncrementalWriter, append_error, read_json, write_json, write_status
# Aliased so `body_size` stays available as a parameter name in the heuristics
# below without shadowing the function that computes it.
from steps.detect_structure.process import body_size as document_body_size
from steps.detect_structure.process import page_lines

STEP_NAME = "extract_figures"

# --- empirical thresholds --------------------------------------------------
# Tune these against a contact sheet, not against intuition.
CLUSTER_GAP = 8.0          # points; boxes closer than this belong to one figure
MIN_AREA_FRACTION = 0.04   # of page area; below this it is an icon or a bullet
MIN_DIMENSION = 40.0       # points; a figure is not 12pt tall
RULE_THICKNESS = 3.0       # points; thinner than this is a rule, not a graphic
FULL_PAGE_FRACTION = 0.9   # of page area; above this it is a background panel
PROSE_RATIO = 0.6          # share of characters at body size that makes a region text
PROSE_MIN_LINES = 4        # fewer lines than this is a label, not a paragraph
CAPTION_BAND = 90.0        # points above or below the cluster to search for a caption

DPI = 144                  # 2x nominal, so a figure stays sharp on a retina screen
WEBP_QUALITY = 85

# `Figure 1.1 …`, `Fig. 4.2: …`, `Table 2.1 …`, `Map 3 …`. The number is
# required: it is what separates a caption from a sentence that happens to
# start with the word "Figures".
CAPTION_RE = re.compile(
    r"^\s*((?:figure|fig\.?|table|map|chart|exhibit)\s*\d+(?:\.\d+)*)\b[\s:.\-–—]*(.*)$",
    re.IGNORECASE,
)

CONTACT_SHEET_HEAD = """<!doctype html>
<meta charset="utf-8">
<title>{doc} — extracted figures</title>
<style>
  body {{ font: 14px/1.5 system-ui, sans-serif; margin: 2rem; background: #fafafa; }}
  figure {{ margin: 0 0 2.5rem; padding: 1rem; background: #fff; border: 1px solid #ddd; }}
  img {{ max-width: 100%; height: auto; display: block; border: 1px solid #eee; }}
  figcaption {{ margin-top: .5rem; color: #333; }}
  .meta {{ color: #777; font-family: ui-monospace, monospace; font-size: 12px; }}
</style>
<h1>{doc} — {count} extracted region(s)</h1>
<p class="meta">gap {gap}pt · min area {area:.0%} of page · min dimension {dimension}pt
· prose ratio {ratio} · caption band {band}pt · {dpi} dpi</p>
"""


# --------------------------------------------------------------------------
# Geometry over (x0, y0, x1, y1) tuples, y increasing downward
# --------------------------------------------------------------------------

def width(box) -> float:
    return max(0.0, box[2] - box[0])


def height(box) -> float:
    return max(0.0, box[3] - box[1])


def area(box) -> float:
    return width(box) * height(box)


def union(a, b) -> tuple:
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def inflate(box, pad: float) -> tuple:
    return (box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad)


def intersects(a, b) -> bool:
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def near(a, b, gap: float = CLUSTER_GAP) -> bool:
    return intersects(inflate(a, gap / 2.0), inflate(b, gap / 2.0))


def contains(outer, inner, tol: float = 1.0) -> bool:
    return (inner[0] >= outer[0] - tol and inner[1] >= outer[1] - tol
            and inner[2] <= outer[2] + tol and inner[3] <= outer[3] + tol)


def horizontally_overlaps(a, b) -> bool:
    return not (a[2] < b[0] or b[2] < a[0])


# --------------------------------------------------------------------------
# Which regions are figures
# --------------------------------------------------------------------------

def is_page_furniture(box, page_w: float, page_h: float, table_boxes) -> bool:
    """True for the things a page draws that are not figures: full-page
    background panels, hairline rules and borders, and anything already claimed
    by a detected table (tables get their own record; counting them twice would
    put the same region in the document as both a figure and a table)."""
    if area(box) >= FULL_PAGE_FRACTION * page_w * page_h:
        return True
    if height(box) < RULE_THICKNESS or width(box) < RULE_THICKNESS:
        return True
    return any(contains(table, box, tol=2.0) for table in table_boxes)


def cluster_boxes(boxes, gap: float = CLUSTER_GAP) -> list:
    """Union boxes that overlap or sit within `gap`, iterating to a fixpoint.

    Connected components over a proximity graph, computed the naive way:
    merging changes the geometry, which can bring a third box into range, so
    the pass repeats until nothing merges. A chart's axes, plot area and legend
    arrive as dozens of separate drawings and have to come back out as one
    figure.
    """
    clusters = [tuple(float(v) for v in box) for box in boxes]
    merged = True
    while merged:
        merged = False
        result = []
        for box in clusters:
            for i, existing in enumerate(result):
                if near(existing, box, gap):
                    result[i] = union(existing, box)
                    merged = True
                    break
            else:
                result.append(box)
        clusters = result
    return clusters


def filter_clusters(clusters, page_w: float, page_h: float,
                    min_area_fraction: float = MIN_AREA_FRACTION,
                    min_dimension: float = MIN_DIMENSION) -> list:
    """Drop clusters too small to be a figure — icons, bullets, logos, and the
    stray marks left by a line that did not merge with anything."""
    page_area = page_w * page_h
    return [box for box in clusters
            if area(box) >= min_area_fraction * page_area
            and width(box) >= min_dimension
            and height(box) >= min_dimension]


def is_prose(box, lines, body_size: float, ratio: float = PROSE_RATIO,
             min_lines: int = PROSE_MIN_LINES) -> bool:
    """True if the region is body text in reading flow rather than a graphic.

    The discriminator is type size relative to the document's body style, not
    the mere presence of text: map labels, axis ticks and legend keys are text
    *inside* figures, and rejecting a region because it contains words would
    delete every map and every chart in the document. Only a region that is
    mostly set at body size, over enough lines to be a paragraph, is prose.
    """
    inside = [ln for ln in lines if contains(box, ln.bbox, tol=2.0)]
    if len(inside) < min_lines:
        return False
    total = sum(len(ln.text) for ln in inside)
    if not total:
        return False
    body_chars = sum(len(ln.text) for ln in inside if abs(ln.size - body_size) <= 0.6)
    return body_chars / total >= ratio


def _clean_caption(text: str) -> str:
    return " ".join(text.split())


def find_caption(box, lines, band: float = CAPTION_BAND):
    """The nearest `Figure 1.1 …`-style line below the region, else above it.

    Below wins because that is where captions overwhelmingly sit; the
    horizontal-overlap guard stops a caption in the neighbouring column being
    stolen by a figure in this one.
    """
    below = sorted(
        (ln for ln in lines
         if box[3] <= ln.bbox[1] <= box[3] + band and horizontally_overlaps(box, ln.bbox)),
        key=lambda ln: ln.bbox[1])
    above = sorted(
        (ln for ln in lines
         if box[1] - band <= ln.bbox[3] <= box[1] and horizontally_overlaps(box, ln.bbox)),
        key=lambda ln: -ln.bbox[3])
    for candidate in [*below, *above]:
        if CAPTION_RE.match(candidate.text):
            return _clean_caption(candidate.text)
    return None


def candidate_boxes(page: dict) -> list:
    """Every drawn thing on the page that could be part of a figure."""
    boxes = [tuple(image["bbox"]) for image in page.get("images", [])]
    boxes += [tuple(drawing["bbox"]) for drawing in page.get("drawings", [])]
    return boxes


def page_figure_boxes(page: dict, body: float) -> list:
    """The figure regions of one page, in reading order.

    Furniture first (cheapest, and it must happen before clustering or a
    full-page border would swallow the whole page into one cluster), then
    clustering, then the size floor, then prose rejection last — it needs the
    final geometry to know which lines fall inside the region.
    """
    page_w, page_h = page["width"], page["height"]
    table_boxes = [tuple(table["bbox"]) for table in page.get("tables", [])]
    lines = page_lines(page)

    kept = [box for box in candidate_boxes(page)
            if not is_page_furniture(box, page_w, page_h, table_boxes)]
    clusters = filter_clusters(cluster_boxes(kept), page_w, page_h)
    clusters = [box for box in clusters if not is_prose(box, lines, body)]
    clusters.sort(key=lambda box: (box[1], box[0]))
    return clusters


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def render(pdf_page, box, target: Path):
    """Rasterise `box` of an already-open PDF page to WebP; return (w, h) px."""
    target.parent.mkdir(parents=True, exist_ok=True)
    pixmap = pdf_page.get_pixmap(clip=pymupdf.Rect(*box), dpi=DPI)
    pixmap.pil_save(str(target), format="WEBP", quality=WEBP_QUALITY)
    return pixmap.width, pixmap.height


def write_contact_sheet(path: Path, doc_slug: str, records: list) -> None:
    """One page per document showing every rendered region with its id, kind,
    page, bbox and pixel size. This is the affordance for tuning the constants
    at the top of this file; it is regenerated on every run and never
    committed."""
    parts = [CONTACT_SHEET_HEAD.format(
        doc=escape(doc_slug), count=len(records), gap=CLUSTER_GAP, area=MIN_AREA_FRACTION,
        dimension=MIN_DIMENSION, ratio=PROSE_RATIO, band=CAPTION_BAND, dpi=DPI)]
    for record in records:
        bbox = ", ".join(f"{v:.0f}" for v in record["bbox"])
        # Assets live at <step>/assets/<doc>/…; the sheet at <step>/contact-sheets/….
        src = f"../{record['asset']}"
        parts.append(
            f'<figure>\n'
            f'  <img src="{escape(src)}" alt="{escape(record["alt"])}" loading="lazy">\n'
            f'  <figcaption>{escape(record["caption"])}</figcaption>\n'
            f'  <p class="meta">{record["id"]} · {record["kind"]} · page {record["page"]} '
            f'· bbox [{bbox}] · {record["width"]}×{record["height"]}px</p>\n'
            f'</figure>\n')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(parts), encoding="utf-8")


# --------------------------------------------------------------------------
# Step
# --------------------------------------------------------------------------

def load_pages(pages_base_dir: Path, record: dict) -> list:
    """Read a document's per-page JSON sidecars, in page order."""
    return [read_json(Path(pages_base_dir) / entry["file"])
            for entry in sorted(record.get("pages", []), key=lambda e: e["number"])]


def _error(step_dir, error_type: str, message: str, context: dict) -> None:
    append_error(step_dir, {
        "step": STEP_NAME,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "error_type": error_type,
        "error_message": message,
        "context": context,
    })


def clear_assets(assets_dir: Path) -> None:
    """Re-running a document must not leave last run's figures behind: a
    tightened threshold that drops `p003-f02` would otherwise leave its WebP on
    disk for `publish_bundles` to ship."""
    assets_dir.mkdir(parents=True, exist_ok=True)
    for stale in assets_dir.glob("*.webp"):
        stale.unlink()


def document_figures(pages: list, pdf, step_dir: Path, slug: str) -> list:
    """Every figure and rasterised table region of one open document."""
    body = document_body_size(pages)
    records = []

    for page in pages:
        number = page["number"]
        lines = page_lines(page)
        pdf_page = pdf[number - 1]

        items = [("figure", index, box)
                 for index, box in enumerate(page_figure_boxes(page, body), start=1)]
        items += [("table", index, tuple(table["bbox"]))
                  for index, table in enumerate(page.get("tables", []), start=1)]

        for kind, index, box in items:
            figure_id = f"p{number:03d}-{'f' if kind == 'figure' else 't'}{index:02d}"
            asset = f"assets/{slug}/{figure_id}.webp"
            try:
                asset_width, asset_height = render(pdf_page, box, step_dir / asset)
            except Exception as e:
                # One region that will not rasterise must not cost the document
                # its other figures, let alone abort the run.
                _error(step_dir, "FigureRenderFailed", str(e),
                       {"doc_slug": slug, "page": number, "figure_id": figure_id,
                        "bbox": [round(v, 2) for v in box]})
                continue

            caption = find_caption(box, lines)
            if caption is None:
                caption = f"Figure from page {number}"
                _error(step_dir, "MissingCaption",
                       "No Figure/Table/Map caption found near the region; "
                       "using a positional fallback title.",
                       {"doc_slug": slug, "page": number, "figure_id": figure_id,
                        "bbox": [round(v, 2) for v in box]})

            records.append({
                "id": figure_id,
                "kind": kind,
                "page": number,
                "bbox": [round(v, 2) for v in box],
                "y": round(box[1], 2),
                "asset": asset,
                "caption": caption,
                "alt": caption,
                "width": asset_width,
                "height": asset_height,
            })
    return records


def process(upstream_records, pages_base_dir, pdf_paths, step_dir, writer,
            doc_slug=None, verbose=False):
    """Extract, render and caption every document's figures.

    `pdf_paths` maps doc_slug to the source PDF; main() builds it from the
    sibling `fetch_pdfs` step, which is where the PDFs actually live —
    `extract_pages`, this step's `--input`, deliberately records no PDF path
    because nothing downstream of it is supposed to need one.
    """
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

        pdf_path = pdf_paths.get(slug)
        if pdf_path is None or not Path(pdf_path).exists():
            _error(step_dir, "SourcePdfMissing",
                   f"No source PDF for {slug!r}; run fetch_pdfs first.",
                   {"doc_slug": slug, "pdf_path": str(pdf_path) if pdf_path else None})
            writer.append([])
            if verbose:
                print("[error]", flush=True)
            continue

        clear_assets(step_dir / "assets" / slug)
        pages = load_pages(pages_base_dir, record)

        pdf = None
        try:
            pdf = pymupdf.open(str(pdf_path))
            figures = document_figures(pages, pdf, step_dir, slug)
        finally:
            if pdf is not None:
                pdf.close()

        write_contact_sheet(step_dir / "contact-sheets" / f"{slug}.html", slug, figures)
        writer.append([{"doc_slug": slug, "figures": figures}])
        if verbose:
            print(f"{len(figures)} region(s)", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Cluster each document's page geometry into figures, render them to "
                    "WebP, and write a contact sheet per document")
    parser.add_argument("--input", required=True, help="Path to extract_pages/output.json")
    parser.add_argument("--output", default=None, help="Path to write output.json")
    parser.add_argument("--force", action="store_true", help="Re-extract every document")
    parser.add_argument("--verbose", action="store_true", help="Print progress")
    add_doc_arg(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output) if args.output else step_dir / "output.json"

    input_path = Path(args.input)
    upstream_records = read_json(input_path).get("results", [])
    pages_base_dir = input_path.parent

    # Fan-in: the geometry comes from --input, the PDFs from the sibling
    # fetch_pdfs step. The shared runner passes one --input, so a second
    # upstream is resolved by path, the way export_status does in foi_pipeline.
    fetch_dir = step_dir.parent / "fetch_pdfs"
    fetch_output = fetch_dir / "output.json"
    pdf_paths = {}
    if fetch_output.exists():
        for record in read_json(fetch_output).get("results", []):
            if record.get("pdf_path"):
                pdf_paths[record["doc_slug"]] = fetch_dir / record["pdf_path"]

    writer = IncrementalWriter(output_path, STEP_NAME, key_field="doc_slug",
                               force=args.force, target_key=args.doc)
    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")

    process(upstream_records, pages_base_dir, pdf_paths, step_dir, writer,
            doc_slug=args.doc, verbose=args.verbose)

    count = writer.finalize()
    write_status(step_dir, count)
    print(f"Wrote {count} of {len(upstream_records)} document figure record(s) "
          f"to {output_path}")


if __name__ == "__main__":
    main()
