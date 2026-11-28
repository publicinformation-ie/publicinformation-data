"""Drift check: re-OCR each committed scanned fixture and compare with the
committed OCR words. Runs only where the tesseract binary is installed; CI
skips it and relies on the committed output."""
import json
import shutil
from pathlib import Path

import pytest

from steps.fetch_spc_minutes import fetching

FIXTURES = Path(__file__).resolve().parent / "fixtures"
OCR_FILES = sorted((FIXTURES / "ocr").glob("*.json"))


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract not installed")
@pytest.mark.parametrize("path", OCR_FILES, ids=lambda p: p.stem)
def test_committed_ocr_matches_a_fresh_run(path):
    committed = json.loads(path.read_text())
    pdf = next(
        (FIXTURES / "pdf" / entry["pdf"]
         for entry in json.loads((FIXTURES / "meetings.json").read_text())["meetings"]
         if entry["sha256"] == committed["sha256"]),
        None,
    )
    assert pdf is not None, f"no manifest entry with sha256 {committed['sha256']}"
    live = fetching.LiveOcr()
    assert live.engine_for(committed["sha256"]) == committed["engine"], (
        "tesseract changed: refresh the OCR fixtures deliberately and review the public/ diff")
    data = pdf.read_bytes()
    # The first OCR'd page of each file keeps the run short (about 1 s a page).
    number = min(int(n) for n in committed["pages"])
    fresh = live.page_words(data, committed["sha256"], number)
    assert [w["text"] for w in fresh] == [w["text"] for w in committed["pages"][str(number)]], (
        f"page {number} no longer OCRs to the committed words")
