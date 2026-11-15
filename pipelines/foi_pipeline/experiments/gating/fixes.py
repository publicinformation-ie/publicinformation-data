"""Fix registry: a fix yields rows for a PDF. Rows are cached by content sha (extract_cache)."""
import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from experiments.gating.downstream import Gate
from experiments.gating.paths import DOCLING_PAGES, OCR_CACHE, content_sha

from steps.transform_disclosure_files.candidates import CANDIDATE_NAMES, extract_candidate  # noqa: E402
from steps.transform_disclosure_files.process import _merge_page_splits  # noqa: E402

FIX_KINDS = ("baseline", "config", "params", "candidate", "wrapper", "fork", "gate")  # cheapest first
SCOPES = ("routed", "global")
FAMILY = {"pdfplumber": "pdfplumber", "camelot_lattice": "camelot", "camelot_stream": "camelot",
          "pymupdf": "pymupdf", "mistral_cache": "mistral", "docling": "docling"}


class NotExtracted(Exception):
    """The fix's output has not been produced yet (e.g. docling not run)."""


@dataclass(frozen=True)
class Fix:
    name: str
    kind: str
    extract: Callable[[bytes, str], list[list] | None] | None = None
    rows_from: str | None = None
    family: str | None = None
    gate: Gate | None = None
    scope: str = "routed"
    base: str = "current"
    version: str = "1"


REGISTRY: dict[str, Fix] = {}


def register(fix: Fix) -> Fix:
    if fix.name in REGISTRY:
        raise ValueError(f"duplicate fix: {fix.name}")
    if fix.kind not in FIX_KINDS:
        raise ValueError(f"unknown kind {fix.kind!r} for {fix.name}; known: {FIX_KINDS}")
    if fix.scope not in SCOPES:
        raise ValueError(f"unknown scope {fix.scope!r} for {fix.name}; known: {SCOPES}")
    REGISTRY[fix.name] = fix
    return fix


def get(name: str) -> Fix:
    if name not in REGISTRY:
        raise KeyError(f"unknown fix {name!r}; known: {sorted(REGISTRY)}")
    return REGISTRY[name]


def load_round_fixes(path: Path) -> None:
    """Import a round's fixes.py so its register() calls run."""
    spec = importlib.util.spec_from_file_location(f"round_fixes_{abs(hash(str(path)))}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    spec.loader.exec_module(importlib.util.module_from_spec(spec))


def family_of(fix: Fix, stored_item: dict) -> str | None:
    if fix.family is not None:
        return fix.family
    if fix.rows_from is not None:
        return family_of(get(fix.rows_from), stored_item)
    if fix.kind == "baseline":
        return FAMILY.get(stored_item.get("pdf_extractor") or "")
    return None


def _forced(name: str) -> Callable[[bytes, str], list[list] | None]:
    def extract(data: bytes, url: str) -> list[list] | None:
        # mistral_cache only reads OCR_CACHE: read_cached_ocr returns None on a
        # miss and never constructs a client, so no paid call is possible.
        c = extract_candidate(name, data, file_url=url, ocr_cache_dir=OCR_CACHE)
        return c.rows if c else None
    return extract


def _docling(data: bytes, url: str) -> list[list] | None:
    p = Path(DOCLING_PAGES) / f"{content_sha(data)}.json"
    if not p.is_file():
        raise NotExtracted(f"no docling output for {p.name}")
    pages = json.loads(p.read_text())["pages"]
    if not any(pages):
        return None
    return _merge_page_splits(pages)[0]


register(Fix(name="current", kind="baseline"))
for _n in CANDIDATE_NAMES:
    register(Fix(name=f"force:{_n}", kind="config", extract=_forced(_n), family=FAMILY[_n]))
register(Fix(name="docling", kind="candidate", extract=_docling, family="docling"))
