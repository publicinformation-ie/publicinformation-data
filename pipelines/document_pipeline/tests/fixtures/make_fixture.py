#!/usr/bin/env python3
"""Generate the deterministic fixture PDF used by document_pipeline's tests.

Committed alongside its output. Regenerate with:
    uv run python pipelines/document_pipeline/tests/fixtures/make_fixture.py

Deliberate properties, relied on by tests in later steps:
  * no PDF outline, so detect_structure falls through to the numbering strategy
  * three distinct font sizes above body size, so the font-hierarchy strategy
    also has something to find
  * a decoy numeric line ("2.4 million trips…") at body size, which numbering
    detection must reject
  * a word hyphenated across a line break, for the dehyphenation test
  * running header and page number, for furniture stripping

Ported from pdf2site's tests/fixtures/make_fixture.py (source plan Task 4,
lines 1046-1299), swapped from PyMuPDF (fitz) construction to reportlab so
this repo doesn't pick up a new generator-only dependency, and made
byte-identical across regenerations via reportlab's `invariant` mode (fixes
the document's timestamp and avoids any wall-clock-derived output).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
from PIL import Image, ImageDraw

OUT = Path(__file__).parent / "fixture.pdf"

TITLE_SIZE, H1_SIZE, H2_SIZE, BODY_SIZE, SMALL_SIZE = 24.0, 18.0, 14.0, 10.0, 8.0
SANS, SANS_BOLD = "Helvetica", "Helvetica-Bold"
LEFT, RIGHT = 72.0, 523.0
PAGE_WIDTH, PAGE_HEIGHT = 595.0, 842.0


def _fy(y: float) -> float:
    """Convert a top-down y (origin top-left, increasing downward) to
    reportlab's bottom-up canvas coordinate (origin bottom-left)."""
    return PAGE_HEIGHT - y


def _text(c: Canvas, x: float, y: float, text: str, size: float, font: str = SANS) -> None:
    c.setFont(font, size)
    c.setFillColorRGB(0, 0, 0)
    c.drawString(x, _fy(y), text)


def _furniture(c: Canvas, number: int) -> None:
    _text(c, LEFT, 40.0, "Fixture Transport Strategy", SMALL_SIZE)
    _text(c, LEFT, 800.0, str(number), SMALL_SIZE)


def _page_one(c: Canvas) -> None:
    _text(c, LEFT, 120.0, "Fixture Transport Strategy", TITLE_SIZE, SANS_BOLD)
    _text(c, LEFT, 160.0, "A deterministic test document", 12.0)


def _page_two(c: Canvas) -> None:
    _furniture(c, 2)
    _text(c, LEFT, 90.0, "1 First Chapter", H1_SIZE, SANS_BOLD)
    _text(c, LEFT, 130.0, "1.1 Introduction", H2_SIZE, SANS_BOLD)
    body = [
        "Walking is the most universally available mode of transport, and",
        "improving the pedestrian environment therefore improves accessi-",
        "bility for every other mode as well.",
    ]
    for i, line in enumerate(body):
        _text(c, LEFT, 170.0 + i * 14.0, line, BODY_SIZE)
    _text(c, LEFT, 230.0, "2.4 million trips are made each day.", BODY_SIZE)
    for i, item in enumerate(["Walking", "Cycling", "Public transport"]):
        _text(c, LEFT + 12.0, 260.0 + i * 14.0, f"• {item}", BODY_SIZE)


def _page_three(c: Canvas) -> None:
    _furniture(c, 3)
    # Deliberately unnumbered: the plan's fixture spec is four numbered
    # headings (1, 1.1, 2, 2.1), giving two chapters with one section each.
    # A numbered "1.2 Figures" here would make chapter 1 two sections deep and
    # detach page 3's figures from section 1.1, which every later task's
    # golden output is written against. It still exercises the font-hierarchy
    # strategy, which does not require numbering.
    _text(c, LEFT, 90.0, "Figures", H2_SIZE, SANS_BOLD)

    # Rect(LEFT, 130.0, 320.0, 300.0) in top-down (x0, y0, x1, y1) form.
    c.setStrokeColorRGB(0.2, 0.2, 0.2)
    c.setLineWidth(1.0)
    c.rect(LEFT, _fy(300.0), 320.0 - LEFT, 300.0 - 130.0, stroke=1, fill=0)

    c.setStrokeColorRGB(0.8, 0.1, 0.1)
    c.setLineWidth(2.0)
    c.line(LEFT + 10, _fy(280.0), 310.0, _fy(150.0))

    c.setStrokeColorRGB(0.1, 0.3, 0.8)
    c.setLineWidth(1.5)
    c.circle(200.0, _fy(215.0), 40.0, stroke=1, fill=0)

    _text(c, LEFT, 315.0, "Figure 1.1 A vector diagram", 9.0)

    image = Image.new("RGB", (120, 90), (200, 220, 240))
    ImageDraw.Draw(image).rectangle([10, 10, 59, 49], fill=(40, 90, 160))
    # Rect(LEFT, 350.0, 300.0, 480.0) in top-down (x0, y0, x1, y1) form.
    c.drawImage(
        ImageReader(image),
        LEFT,
        _fy(480.0),
        width=300.0 - LEFT,
        height=480.0 - 350.0,
    )
    _text(c, LEFT, 495.0, "Figure 1.2 A raster image", 9.0)


def _page_four(c: Canvas) -> None:
    _furniture(c, 4)
    _text(c, LEFT, 90.0, "2 Second Chapter", H1_SIZE, SANS_BOLD)
    _text(c, LEFT, 130.0, "2.1 Methods", H2_SIZE, SANS_BOLD)

    rows = [("Mode", "Share"), ("Walk", "25%"), ("Cycle", "10%")]
    top, row_h, col_w = 160.0, 30.0, 164.0

    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.8)
    for r in range(len(rows) + 1):
        y = top + r * row_h
        c.line(LEFT, _fy(y), LEFT + 2 * col_w, _fy(y))
    for col in range(3):
        x = LEFT + col * col_w
        c.line(x, _fy(top), x, _fy(top + len(rows) * row_h))

    for r, row in enumerate(rows):
        for col, cell in enumerate(row):
            _text(c, LEFT + col * col_w + 8.0, top + r * row_h + 20.0, cell, BODY_SIZE)
    _text(c, LEFT, top + len(rows) * row_h + 20.0, "Table 2.1 Mode share", 9.0)


def build(path: Path = OUT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    c = Canvas(str(path), pagesize=(PAGE_WIDTH, PAGE_HEIGHT), invariant=1)
    c.setTitle("Fixture Transport Strategy")
    c.setAuthor("document_pipeline tests")
    c.setSubject("")
    c.setKeywords("")
    c.setCreator("document_pipeline make_fixture")
    c.setProducer("document_pipeline make_fixture")

    builders = (_page_one, _page_two, _page_three, _page_four)
    for i, builder in enumerate(builders):
        builder(c)
        if i < len(builders) - 1:
            c.showPage()
    c.save()
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT, help="Path to write the fixture PDF to.")
    args = parser.parse_args()
    print(build(args.output))


if __name__ == "__main__":
    main()
