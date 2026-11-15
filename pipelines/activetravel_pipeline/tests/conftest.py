import json
import sys
from pathlib import Path

_HERE = Path(__file__).parent
_REPO_ROOT = _HERE
_prev = None
while not (_REPO_ROOT / ".git").exists():
    if _prev == _REPO_ROOT:
        raise RuntimeError(f"Could not find .git root starting from {_HERE}")
    _prev = _REPO_ROOT
    _REPO_ROOT = _REPO_ROOT.parent

sys.path.insert(0, str(_HERE))                 # tests/, for the shared helpers in conftest
sys.path.insert(0, str(_HERE.parent))          # pipelines/activetravel_pipeline/, for `allocations` and `steps.*`
sys.path.insert(0, str(_REPO_ROOT / "src"))     # src/lib/

import pytest

from allocations import classify_row

FIXTURES = _HERE / "fixtures"


@pytest.fixture(scope="session")
def real_pages() -> dict:
    with open(FIXTURES / "real_pages.json", encoding="utf-8") as f:
        return json.load(f)


def page_rows(real_pages: dict, document_id: str, page: int) -> list[list[str]]:
    """One fixture page's rows, verbatim."""
    document = next(d for d in real_pages["documents"] if d["document_id"] == document_id)
    return next(p["rows"] for p in document["pages"] if p["page"] == page)


def make_row(cells: list[str], *, document_id: str = "doc", year: int = 2026,
             page: int = 1, row_index: int = 0) -> dict:
    """A row as `classify_grant_rows` leaves it."""
    kind, detail = classify_row(list(cells))
    return {
        "document_id": document_id,
        "year": year,
        "page": page,
        "row_index": row_index,
        "part": "project_table",
        "cells": list(cells),
        "kind": kind,
        "detail": detail,
    }


def rows_from_pages(real_pages: dict, document_id: str, year: int,
                    pages: list[int]) -> tuple[list[dict], int]:
    """Classified rows for a page subset, in document order, plus a row counter."""
    rows = []
    index = 0
    for page in pages:
        for row_index, cells in enumerate(page_rows(real_pages, document_id, page)):
            rows.append(make_row(cells, document_id=document_id, year=year,
                                 page=page, row_index=row_index))
            index += 1
    return rows, index
