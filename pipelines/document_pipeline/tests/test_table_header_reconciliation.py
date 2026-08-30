"""Regression coverage for extract_pages' table-header reconciliation.

Real SMP progress reports have annex tables whose header text has no PDF
fill-rectangle tying it to PyMuPDF's detected grid, so find_tables() never
includes it as row 0 (see extract_action_status's docstring and the
"Known limitations" section this fix removed from its README). These tests
build minimal synthetic PDFs with reportlab — not the shared fixture.pdf,
which other steps' golden-output tests depend on staying byte-identical —
to exercise that reconciliation directly against `extract_tables`.
"""
from pathlib import Path

import pymupdf
from reportlab.pdfgen.canvas import Canvas

from steps.extract_pages.process import extract_tables

PAGE_WIDTH, PAGE_HEIGHT = 595.0, 842.0


def _fy(y: float) -> float:
    return PAGE_HEIGHT - y


def _grid(c: Canvas, xs, top: float, row_h: float, n_rows: int) -> None:
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.8)
    for r in range(n_rows + 1):
        y = top + r * row_h
        c.line(xs[0], _fy(y), xs[-1], _fy(y))
    for x in xs:
        c.line(x, _fy(top), x, _fy(top + n_rows * row_h))


def _first_page(path: Path) -> pymupdf.Page:
    doc = pymupdf.open(str(path))
    return doc[0]


def test_a_floating_header_above_the_grid_is_reconstructed(tmp_path):
    path = tmp_path / "floating.pdf"
    c = Canvas(str(path), pagesize=(PAGE_WIDTH, PAGE_HEIGHT))
    xs = [72.0, 200.0, 320.0, 440.0]
    # Header text floats a few points above the grid — no fill rectangle or
    # line ties it to the table, matching the real corpus's Year Two/Three/
    # Final reports.
    c.setFont("Helvetica", 10)
    c.drawString(80.0, _fy(292.0), "No.")
    c.drawString(210.0, _fy(292.0), "Action")
    c.drawString(330.0, _fy(292.0), "Status")
    _grid(c, xs, top=300.0, row_h=30.0, n_rows=1)
    c.drawString(80.0, _fy(315.0), "1")
    c.drawString(210.0, _fy(315.0), "Do it")
    c.drawString(330.0, _fy(315.0), "Complete")
    c.save()

    tables = extract_tables(_first_page(path))
    assert len(tables) == 1
    assert tables[0]["rows"] == 2
    assert tables[0]["text"][0] == ["No.", "Action", "Status"]
    assert tables[0]["text"][1] == ["1", "Do it", "Complete"]
    # The reconstructed header is folded into the table's own bbox, not left
    # as free-floating prose for a later step to garble.
    assert tables[0]["bbox"][1] < 300.0


def test_a_header_already_inside_the_grid_is_not_duplicated(tmp_path):
    path = tmp_path / "merged.pdf"
    c = Canvas(str(path), pagesize=(PAGE_WIDTH, PAGE_HEIGHT))
    xs = [72.0, 200.0, 320.0, 440.0]
    _grid(c, xs, top=300.0, row_h=30.0, n_rows=2)
    c.setFont("Helvetica", 10)
    c.drawString(80.0, _fy(320.0), "No.")
    c.drawString(210.0, _fy(320.0), "Action")
    c.drawString(330.0, _fy(320.0), "Status")
    c.drawString(80.0, _fy(350.0), "1")
    c.drawString(210.0, _fy(350.0), "Do it")
    c.drawString(330.0, _fy(350.0), "Complete")
    c.save()

    tables = extract_tables(_first_page(path))
    assert len(tables) == 1
    assert tables[0]["rows"] == 2
    assert tables[0]["text"][0] == ["No.", "Action", "Status"]


def test_a_single_line_of_prose_above_a_table_is_not_mistaken_for_a_header(tmp_path):
    path = tmp_path / "prose.pdf"
    c = Canvas(str(path), pagesize=(PAGE_WIDTH, PAGE_HEIGHT))
    xs = [72.0, 200.0, 320.0, 440.0]
    c.setFont("Helvetica", 10)
    # One continuous sentence, not column-aligned labels: it only ever
    # populates a single column bucket, however wide it visually runs.
    c.drawString(72.0, _fy(292.0), "See the notes below for further detail.")
    _grid(c, xs, top=300.0, row_h=30.0, n_rows=1)
    c.drawString(80.0, _fy(315.0), "1")
    c.drawString(210.0, _fy(315.0), "Do it")
    c.drawString(330.0, _fy(315.0), "Complete")
    c.save()

    tables = extract_tables(_first_page(path))
    assert len(tables) == 1
    assert tables[0]["rows"] == 1
    assert tables[0]["text"][0] == ["1", "Do it", "Complete"]
