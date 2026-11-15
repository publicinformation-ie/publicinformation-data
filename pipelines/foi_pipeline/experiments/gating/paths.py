"""Paths, cached-bytes lookup and loaders for the gating harness. Never downloads."""
import hashlib
import json
import os
import sys
from pathlib import Path

FOI = Path(__file__).resolve().parents[2]
for _p in (FOI, FOI.parents[1] / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

STEPS = FOI / "steps"
PDF_CACHE = STEPS / "verify_disclosure_files" / "cache"
OCR_CACHE = STEPS / "transform_disclosure_files" / "ocr_cache"
BAKEOFF = FOI / "experiments" / "2026-11-14-pdf-extractor-bakeoff"
GOLD_DIR = BAKEOFF / "gold"
GATING = FOI / "experiments" / "gating"
CACHE = GATING / "cache"
SCRATCH = GATING / "scratch"
DOCLING_PAGES = GATING / "docling_pages"
SNAPSHOT = Path(os.environ.get(
    "FOI_GATING_SNAPSHOT", "/Volumes/ext/dev/publicinformation/foi-before-role-aware-2026-11-14"))


def pdf_bytes(file_url: str, cache_dir: Path = PDF_CACHE) -> bytes | None:
    p = Path(cache_dir) / f"{hashlib.sha256(file_url.encode('utf-8')).hexdigest()}.bytes"
    return p.read_bytes() if p.is_file() else None


def content_sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_results(path: Path) -> list[dict]:
    p = Path(path)
    if not p.is_file() or not p.read_text().strip():
        return []
    d = json.loads(p.read_text())
    return d.get("results", []) if isinstance(d, dict) else d


def settings() -> dict:
    return json.loads((GATING / "settings.json").read_text())
