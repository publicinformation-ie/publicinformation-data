"""Candidate PDF table extractors for the structure-based extraction bake-off.

Each candidate returns per-page rows that are passed through
``process._merge_page_splits`` so that page-split and repeated-header handling
is identical across extractors. No candidate makes a network or paid call:
``mistral_cache`` only reads the on-disk OCR cache.
"""
from __future__ import annotations

import io
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from steps.transform_disclosure_files.mistral_ocr import markdown_to_pages, read_cached_ocr
from steps.transform_disclosure_files.process import (
    _DEFAULT_PDF_TABLE_SETTINGS,
    _merge_page_splits,
    serialise_cell,
)

CANDIDATE_NAMES = (
    "pdfplumber",
    "pdfplumber_lines",
    "camelot_lattice",
    "pymupdf",
    "camelot_stream",
    "mistral_cache",
)


@dataclass
class Candidate:
    name: str
    rows: list[list]
    sheet_name: str
    merge_stats: dict
    has_multiple: bool


def _sheet_name(n_pages: int) -> str:
    return "page 1" if n_pages == 1 else f"pages 1-{n_pages}"


def _finish(name: str, pages_rows: list[list[list]], n_tables: int, n_pages: int) -> Candidate | None:
    if n_tables == 0 or not any(pages_rows):
        return None
    rows, stats = _merge_page_splits(pages_rows)
    return Candidate(name, rows, _sheet_name(n_pages), stats, n_tables > 1)


def _pdfplumber(name: str, file_bytes: bytes, settings: dict) -> Candidate | None:
    import pdfplumber

    pages_rows: list[list[list]] = []
    n_tables = 0
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        n_pages = len(pdf.pages)
        for page in pdf.pages:
            tables = page.extract_tables(table_settings=settings)
            n_tables += len(tables)
            pages_rows.append(
                [[serialise_cell(c)[0] for c in row] for table in tables for row in table]
            )
    return _finish(name, pages_rows, n_tables, n_pages)


class _PyMuPDFImageBackend:
    """Camelot lattice image backend rendering with pymupdf.

    Camelot's own backends need the ``ghostscript`` python package or the
    ``pdftopng`` binary, neither of which is a pipeline dependency.
    """

    def convert(self, pdf_path, png_path, resolution=300):
        import pymupdf

        with pymupdf.open(pdf_path) as doc:
            doc[0].get_pixmap(dpi=resolution).save(png_path)


def _camelot(name: str, flavor: str, file_bytes: bytes) -> Candidate | None:
    import camelot  # type: ignore[import-untyped]
    import pymupdf

    with pymupdf.open(stream=file_bytes, filetype="pdf") as doc:
        n_pages = doc.page_count
    kwargs = {"backend": _PyMuPDFImageBackend()} if flavor == "lattice" else {}
    fd, path = tempfile.mkstemp(suffix=".pdf")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(file_bytes)
        tables = camelot.read_pdf(path, flavor=flavor, pages="all", **kwargs)
        by_page: dict[int, list[list]] = {}
        for t in tables:
            rows = by_page.setdefault(int(t.page), [])
            for row in t.df.values.tolist():
                rows.append([serialise_cell(c if c != "" else None)[0] for c in row])
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    pages_rows = [by_page.get(p, []) for p in range(1, n_pages + 1)]
    return _finish(name, pages_rows, len(tables), n_pages)


def _camelot_lattice(file_bytes: bytes) -> Candidate | None:
    return _camelot("camelot_lattice", "lattice", file_bytes)


def _pymupdf(file_bytes: bytes) -> Candidate | None:
    import pymupdf

    pages_rows: list[list[list]] = []
    n_tables = 0
    with pymupdf.open(stream=file_bytes, filetype="pdf") as doc:
        n_pages = doc.page_count
        for page in doc:
            found = page.find_tables(strategy="lines").tables
            n_tables += len(found)
            pages_rows.append(
                [[serialise_cell(c)[0] if c is not None else None for c in row]
                 for t in found for row in t.extract()]
            )
    return _finish("pymupdf", pages_rows, n_tables, n_pages)


def _camelot_stream(file_bytes: bytes) -> Candidate | None:
    """Per-page stream extraction (the production helper flattens pages and swallows errors)."""
    return _camelot("camelot_stream", "stream", file_bytes)


def _mistral_cache(file_bytes: bytes, file_url: str, ocr_cache_dir: Path) -> Candidate | None:
    markdown = read_cached_ocr(file_url, ocr_cache_dir)
    if markdown is None:
        return None
    pages = markdown_to_pages(markdown)
    if not pages:
        return None
    # Markdown "pages" are OCR table chunks, not PDF pages or pdfplumber tables;
    # report like the live Mistral path: sheet "page 1", no multiple tables.
    return _finish("mistral_cache", pages, 1, 1)


def extract_candidate(
    name: str, file_bytes: bytes, *, file_url: str, ocr_cache_dir: Path
) -> Candidate | None:
    """Run one named extractor. None when it finds no table; raises on failure."""
    if name == "pdfplumber":
        return _pdfplumber(name, file_bytes, _DEFAULT_PDF_TABLE_SETTINGS)
    if name == "pdfplumber_lines":
        return _pdfplumber(
            name,
            file_bytes,
            {"vertical_strategy": "lines", "horizontal_strategy": "lines", **_DEFAULT_PDF_TABLE_SETTINGS},
        )
    if name == "camelot_lattice":
        return _camelot_lattice(file_bytes)
    if name == "pymupdf":
        return _pymupdf(file_bytes)
    if name == "camelot_stream":
        return _camelot_stream(file_bytes)
    if name == "mistral_cache":
        return _mistral_cache(file_bytes, file_url, ocr_cache_dir)
    raise ValueError(f"unknown candidate: {name!r}")
