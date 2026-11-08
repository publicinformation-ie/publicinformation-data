#!/usr/bin/env python3
"""Generate ligature_table.pdf: one real page used as a regression fixture.

Copies page 11 of "Sustainable Mobility Policy Action Plan 2026-2030"
(https://assets.gov.ie/static/documents/7da21a41/Sustainable_Mobility_Policy_Action_Plan_2026-2030.pdf,
see documents.yml) from the fetch_pdfs cache. Committed alongside its output.
Regenerate with:
    uv run python pipelines/document_pipeline/tests/fixtures/make_ligature_fixture.py

The page is kept because its Lato `tt` ligature ("battery") reproduces the
table-text bug that steps/extract_pages/ligatures.py repairs.
"""
from pathlib import Path

import pymupdf

HERE = Path(__file__).parent
SRC = (HERE.parents[1] / "steps" / "fetch_pdfs" / "pdfs"
       / "sustainable-mobility-policy-action-plan-2026-2030.pdf")
OUT = HERE / "ligature_table.pdf"

if __name__ == "__main__":
    src = pymupdf.open(SRC)
    dst = pymupdf.open()
    dst.insert_pdf(src, from_page=10, to_page=10)
    dst.save(OUT, garbage=4, deflate=True)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
