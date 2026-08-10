import subprocess
import sys
from pathlib import Path

import pymupdf

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURE_PDF = FIXTURES / "fixture.pdf"


def test_fixture_pdf_exists_and_has_four_pages():
    doc = pymupdf.open(FIXTURE_PDF)
    assert doc.page_count == 4


def test_fixture_pdf_carries_the_known_headings():
    doc = pymupdf.open(FIXTURE_PDF)
    text = "\n".join(page.get_text() for page in doc)
    for heading in ("1 First Chapter", "1.1 Introduction",
                    "2 Second Chapter", "2.1 Methods"):
        assert heading in text


def test_fixture_pdf_has_a_text_layer_on_every_page():
    doc = pymupdf.open(FIXTURE_PDF)
    assert all(page.get_text().strip() for page in doc)


def test_fixture_pdf_has_a_detectable_table():
    doc = pymupdf.open(FIXTURE_PDF)
    tables = [t for page in doc for t in page.find_tables().tables]
    assert len(tables) >= 1


def test_regenerating_the_fixture_is_byte_identical(tmp_path):
    out = tmp_path / "fixture.pdf"
    subprocess.run([sys.executable, str(FIXTURES / "make_fixture.py"),
                    "--output", str(out)], check=True)
    assert out.read_bytes() == FIXTURE_PDF.read_bytes()
