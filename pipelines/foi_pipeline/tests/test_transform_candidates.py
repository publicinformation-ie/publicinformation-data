from pathlib import Path

import pytest

from steps.transform_disclosure_files import candidates as cand_mod
from steps.transform_disclosure_files.candidates import (
    CANDIDATE_NAMES,
    Candidate,
    extract_candidate,
)
from steps.transform_disclosure_files.process import _extract_pdf

FIXTURE = Path(__file__).parent / "fixtures" / "pdf" / "rte_2018_p1.pdf"
GEOMETRIC = ["pdfplumber", "pdfplumber_lines", "camelot_lattice", "pymupdf", "camelot_stream"]


@pytest.fixture(scope="module")
def pdf_bytes():
    return FIXTURE.read_bytes()


@pytest.mark.parametrize("name", GEOMETRIC)
def test_each_geometric_candidate_returns_rows_on_ruled_fixture(name, pdf_bytes, tmp_path):
    cand = extract_candidate(name, pdf_bytes, file_url="https://x/y.pdf", ocr_cache_dir=tmp_path)
    assert isinstance(cand, Candidate)
    assert cand.name == name
    assert len(cand.rows) > 5


def test_pdfplumber_candidate_matches_current_extract_pdf(pdf_bytes, tmp_path):
    _, rows, _, _, _, extractor, _ = _extract_pdf(pdf_bytes)
    assert extractor == "pdfplumber"
    cand = extract_candidate("pdfplumber", pdf_bytes, file_url="u", ocr_cache_dir=tmp_path)
    assert cand is not None
    assert cand.rows == rows


def test_mistral_cache_candidate_none_on_miss_no_client(pdf_bytes, tmp_path, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("Mistral client constructed")

    monkeypatch.setattr("steps.transform_disclosure_files.mistral_ocr.Mistral", boom, raising=False)
    monkeypatch.setattr(cand_mod, "Mistral", boom, raising=False)
    assert extract_candidate(
        "mistral_cache", pdf_bytes, file_url="https://x/miss.pdf", ocr_cache_dir=tmp_path
    ) is None


def test_unknown_candidate_name_raises_value_error(pdf_bytes, tmp_path):
    with pytest.raises(ValueError):
        extract_candidate("nope", pdf_bytes, file_url="u", ocr_cache_dir=tmp_path)


def test_candidate_names_constant():
    assert CANDIDATE_NAMES == (
        "pdfplumber", "pdfplumber_lines", "camelot_lattice", "pymupdf", "camelot_stream", "mistral_cache",
    )
