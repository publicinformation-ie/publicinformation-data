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
CAMELOT = {"camelot_lattice", "camelot_stream"}
GEOMETRIC = ["pdfplumber", "pdfplumber_lines", "camelot_lattice", "pymupdf", "camelot_stream"]


@pytest.fixture(scope="module")
def pdf_bytes():
    return FIXTURE.read_bytes()


@pytest.mark.parametrize("name", GEOMETRIC)
def test_each_geometric_candidate_returns_rows_on_ruled_fixture(name, pdf_bytes, tmp_path):
    if name in CAMELOT:
        pytest.importorskip("cv2", reason="camelot needs opencv (absent in CI)")
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


def test_extractor_failure_propagates(pdf_bytes, tmp_path, monkeypatch):
    pytest.importorskip("cv2", reason="camelot needs opencv (absent in CI)")
    import camelot

    def boom(*a, **k):
        raise RuntimeError("camelot exploded")

    monkeypatch.setattr(camelot, "read_pdf", boom)
    for name in ("camelot_stream", "camelot_lattice"):
        with pytest.raises(RuntimeError):
            extract_candidate(name, pdf_bytes, file_url="u", ocr_cache_dir=tmp_path)


def test_mistral_cache_candidate_returns_rows_from_populated_cache(pdf_bytes, tmp_path, monkeypatch):
    import hashlib
    import json

    def boom(*a, **k):
        raise AssertionError("Mistral client constructed")

    monkeypatch.setattr(cand_mod, "Mistral", boom, raising=False)
    url = "https://x/hit.pdf"
    md = "| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n"
    (tmp_path / f"{hashlib.sha256(url.encode()).hexdigest()}.json").write_text(json.dumps({"markdown": md}))
    cand = extract_candidate("mistral_cache", pdf_bytes, file_url=url, ocr_cache_dir=tmp_path)
    assert cand is not None and cand.name == "mistral_cache"
    assert [r for r in cand.rows if r[0] == "3"] == [["3", "4"]]


def test_mistral_cache_candidate_reports_one_page_and_no_multiple_tables(pdf_bytes, tmp_path):
    import hashlib
    import json

    from steps.transform_disclosure_files.mistral_ocr import _PAGE_BREAK_MARKER

    url = "https://x/multi.pdf"
    md = f"| A | B |\n|---|---|\n| 1 | 2 |\n{_PAGE_BREAK_MARKER}\n| A | B |\n|---|---|\n| 3 | 4 |\n"
    (tmp_path / f"{hashlib.sha256(url.encode()).hexdigest()}.json").write_text(json.dumps({"markdown": md}))
    cand = extract_candidate("mistral_cache", pdf_bytes, file_url=url, ocr_cache_dir=tmp_path)
    assert cand is not None
    assert cand.sheet_name == "page 1"
    assert cand.has_multiple is False
