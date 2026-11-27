"""Download minutes PDFs into a git-ignored cache and record their content.

One record per successfully fetched PDF that yields text. A page's words come
from the PDF's text layer; a page with no text-layer words is read by OCR
(tesseract, via ``lib.ocr``), page by page, so a file may be ``text_layer``,
``ocr`` or ``mixed``. The OCR words have the same shape as text-layer words
(plus ``conf``), so no later step needs to know where a page's words came from.

OCR fails closed: a file with no words at all (``NoTextRecovered``), a page
whose mean confidence is below ``OCR_MIN_PAGE_CONF`` (``OcrLowConfidence``) and
an empty OCR page with no reviewed override (``EmptyOcrPage``) each produce an
error and no record. No individual word is ever dropped or altered.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

import pdfplumber
import requests

from lib.certs import requests_verify

STEP_NAME = "fetch_spc_minutes"

_WORD_FIELDS = ("text", "x0", "x1", "top", "bottom")
_PDF_MAGIC = b"%PDF-"

# A page whose mean OCR word confidence (0-100) is below this is not published.
# Set from the 11 scanned fixtures: real text pages score 90.0 to 95.7, so 80
# leaves a 10 point margin, while scanner speckle on a blank sheet scores far lower.
OCR_MIN_PAGE_CONF = 80.0
OCR_PSM = 4

SOURCE_TEXT_LAYER = "text_layer"
SOURCE_OCR = "ocr"
SOURCE_SKIPPED = "skipped"


class InvalidPdf(ValueError):
    """The downloaded or cached bytes are not a readable PDF."""


class NoTextRecovered(ValueError):
    """Neither the text layer nor OCR yields a word on any page."""


class OcrLowConfidence(ValueError):
    """An OCR'd page's mean word confidence is below ``OCR_MIN_PAGE_CONF``."""

    def __init__(self, page: int, confidence: float):
        self.page = page
        self.confidence = confidence
        super().__init__(
            f"page {page} OCR mean confidence {confidence:.1f} is below "
            f"{OCR_MIN_PAGE_CONF}")


class EmptyOcrPage(ValueError):
    """An OCR'd page has no recognised words and no reviewed override."""

    def __init__(self, page: int):
        self.page = page
        super().__init__(f"page {page} has no text-layer or OCR words "
                         "and no ocr_overrides.json entry")


def cache_path(cache_dir: Path, url: str) -> Path:
    """A stable cache file per URL: readable file name plus a short URL hash."""
    name = unquote(urlparse(url).path.rsplit("/", 1)[-1]) or "minutes.pdf"
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "minutes.pdf"
    if not stem.lower().endswith(".pdf"):
        stem += ".pdf"
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    return Path(cache_dir) / f"{digest}-{stem}"


def sidecar_path(pdf_path: Path) -> Path:
    return pdf_path.with_suffix(pdf_path.suffix + ".json")


def ocr_cache_path(pdf_path: Path) -> Path:
    return pdf_path.with_suffix(pdf_path.suffix + ".ocr.json")


def download(url: str) -> bytes:
    """Fetch a PDF with certificate verification on.

    Verification is never disabled: a certificate failure must fail the step
    rather than be retried insecurely. A response that is not a PDF (an HTML
    error page served with 200, for example) is rejected before it can be
    cached.
    """
    response = requests.get(url, verify=requests_verify(), timeout=120)
    response.raise_for_status()
    data = response.content
    if not _is_pdf(data):
        raise InvalidPdf(f"{url} did not return a PDF")
    return data


def _is_pdf(data: bytes) -> bool:
    return _PDF_MAGIC in data[:1024]


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_pages(data: bytes) -> list[dict]:
    """Per-page text-layer words with coordinates.

    A page with no text-layer words has ``words == []``; reading it by OCR is
    ``read_pages``'s job, not this function's.
    """
    pages: list[dict] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            words = [
                {field: word[field] for field in _WORD_FIELDS}
                for word in page.extract_words()
            ]
            pages.append({
                "page": number,
                "width": round(float(page.width), 2),
                "height": round(float(page.height), 2),
                "words": words,
            })
    return pages


# --- OCR providers -----------------------------------------------------------
#
# A provider has ``engine_for(sha256) -> str`` and
# ``page_words(data, sha256, page_number) -> list[word]``. ``LiveOcr`` runs
# tesseract, ``CachedOcr`` wraps another provider with the on-disk cache and
# ``FixtureOcr`` replays committed OCR output so CI never needs the binary.


class LiveOcr:
    """Run tesseract on the page, rendered at 300 dpi by pymupdf."""

    def __init__(self, psm: int = OCR_PSM):
        self.psm = psm
        self._engine: str | None = None

    def engine_for(self, sha256: str) -> str:
        if self._engine is None:
            from lib.ocr import engine_string

            self._engine = engine_string(psm=self.psm)
        return self._engine

    def page_words(self, data: bytes, sha256: str, page_number: int) -> list[dict]:
        import pymupdf

        from lib.ocr import ocr_page_words

        with pymupdf.open(stream=data, filetype="pdf") as doc:
            return ocr_page_words(doc[page_number - 1], psm=self.psm)


class CachedOcr:
    """Cache OCR words per PDF in ``<pdf>.ocr.json``.

    The key is the PDF sha256, the page number and the engine string (which
    includes language, page segmentation mode and dpi). An entry that does not
    match all three is a miss, never stale data reused.
    """

    def __init__(self, base, path: Path):
        self.base = base
        self.path = Path(path)

    def engine_for(self, sha256: str) -> str:
        return self.base.engine_for(sha256)

    def _load(self, sha256: str, engine: str) -> dict:
        try:
            data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            data = None
        if (isinstance(data, dict) and data.get("sha256") == sha256
                and data.get("engine") == engine
                and isinstance(data.get("pages"), dict)):
            return data
        return {"sha256": sha256, "engine": engine, "pages": {}}

    def page_words(self, data: bytes, sha256: str, page_number: int) -> list[dict]:
        engine = self.engine_for(sha256)
        cached = self._load(sha256, engine)
        key = str(page_number)
        if key in cached["pages"]:
            return cached["pages"][key]
        words = self.base.page_words(data, sha256, page_number)
        cached["pages"][key] = words
        _write_atomic(self.path, json.dumps(cached, indent=1).encode("utf-8"))
        return words


class FixtureOcr:
    """Replay committed OCR output (``tests/fixtures/ocr/*.json``).

    Each file is ``{"sha256", "engine", "pages": {"<n>": [word, ...]}}``, the
    same layout as the on-disk cache. A page or file missing from the
    fixtures is an error: a test must never fall back to a live OCR run.
    """

    def __init__(self, directory: Path):
        self.entries: dict[str, dict] = {}
        for path in sorted(Path(directory).glob("*.json")):
            entry = json.loads(path.read_text())
            self.entries[entry["sha256"]] = entry

    def engine_for(self, sha256: str) -> str:
        return self._entry(sha256)["engine"]

    def _entry(self, sha256: str) -> dict:
        try:
            return self.entries[sha256]
        except KeyError:
            raise KeyError(f"no committed OCR fixture for sha256 {sha256}") from None

    def page_words(self, data: bytes, sha256: str, page_number: int) -> list[dict]:
        pages = self._entry(sha256)["pages"]
        try:
            return pages[str(page_number)]
        except KeyError:
            raise KeyError(f"OCR fixture for {sha256} has no page {page_number}") from None


# --- Overrides ---------------------------------------------------------------


def load_overrides(path: Path) -> list[dict]:
    """Reviewed page skips: ``{file_sha256, page, action: "skip", reason}``."""
    path = Path(path)
    if not path.exists():
        return []
    entries = json.loads(path.read_text())
    if not isinstance(entries, list):
        raise ValueError(f"{path.name} must be a list")
    for entry in entries:
        if (not isinstance(entry, dict)
                or not re.fullmatch(r"[0-9a-f]{64}", str(entry.get("file_sha256", "")))
                or not isinstance(entry.get("page"), int) or entry["page"] < 1
                or entry.get("action") != "skip"
                or not str(entry.get("reason", "")).strip()):
            raise ValueError(
                f"{path.name}: each entry needs file_sha256, page >= 1, "
                f"action 'skip' and a reason; got {entry!r}")
    return entries


def stale_overrides(overrides: list[dict], seen_shas: set[str]) -> list[dict]:
    """Overrides naming a file that was not fetched in this run."""
    return [o for o in overrides if o["file_sha256"] not in seen_shas]


# --- Page reading ------------------------------------------------------------


def _mean_conf(words: list[dict]) -> float:
    return sum(float(w["conf"]) for w in words) / len(words)


def read_pages(data: bytes, sha256: str, ocr, overrides: list[dict] | None = None,
               text_pages: list[dict] | None = None) -> dict:
    """Read every page, falling back to OCR page by page.

    Returns ``{pages, text_source, ocr_engine, skipped_pages}``. Raises
    ``NoTextRecovered``, ``EmptyOcrPage`` or ``OcrLowConfidence``.
    """
    base = text_pages if text_pages is not None else extract_pages(data)
    skips = {o["page"]: o for o in (overrides or [])
             if o["file_sha256"] == sha256 and o["action"] == "skip"}
    engine: str | None = None
    pages: list[dict] = []
    for page in base:
        page = {**page}
        if page["words"]:
            page["source"] = SOURCE_TEXT_LAYER
        else:
            engine = engine or ocr.engine_for(sha256)
            page["words"] = [dict(w) for w in ocr.page_words(data, sha256, page["page"])]
            page["source"] = SOURCE_OCR
        pages.append(page)

    if not any(p["words"] for p in pages):
        raise NoTextRecovered("no text-layer or OCR words on any page")

    skipped = 0
    for page in pages:
        if page["source"] != SOURCE_OCR:
            continue
        confidence = _mean_conf(page["words"]) if page["words"] else None
        failing = confidence is None or confidence < OCR_MIN_PAGE_CONF
        override = skips.get(page["page"])
        if failing and override is not None:
            # A reviewed skip for a page that would fail the gate: a blank sheet
            # (no words) or scanner speckle OCR read as junk (low confidence).
            # Its words are dropped from the record, and counted, so no later
            # step reads them. A page that passes the gate is never skipped.
            page["skipped_word_count"] = len(page["words"])
            page["words"] = []
            page["source"] = SOURCE_SKIPPED
            page["skip_reason"] = override["reason"]
            skipped += 1
            continue
        if confidence is None:
            raise EmptyOcrPage(page["page"])
        page["ocr_mean_confidence"] = round(confidence, 1)
        if failing:
            raise OcrLowConfidence(page["page"], confidence)

    sources = {p["source"] for p in pages if p["source"] != SOURCE_SKIPPED}
    if sources == {SOURCE_TEXT_LAYER}:
        text_source = SOURCE_TEXT_LAYER
    elif sources == {SOURCE_OCR}:
        text_source = SOURCE_OCR
    else:
        text_source = "mixed"
    used_ocr = SOURCE_OCR in sources
    return {
        "pages": pages,
        "text_source": text_source,
        "ocr_engine": engine if used_ocr else None,
        "skipped_pages": skipped,
    }


# --- Fetching ----------------------------------------------------------------


def _read_sidecar(pdf_path: Path) -> dict | None:
    path = sidecar_path(pdf_path)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _write_sidecar(pdf_path: Path, metadata: dict) -> None:
    _write_atomic(sidecar_path(pdf_path),
                  json.dumps(metadata, indent=2).encode("utf-8"))


def _write_atomic(path: Path, data: bytes) -> None:
    """Write through a sibling temp file so a crash cannot leave half a PDF."""
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def _cached_bytes(pdf_path: Path) -> bytes | None:
    """Cached bytes only when the sidecar proves them; otherwise a cache miss."""
    if not pdf_path.exists():
        return None
    metadata = _read_sidecar(pdf_path)
    if not metadata or not metadata.get("sha256"):
        return None
    data = pdf_path.read_bytes()
    if sha256_hex(data) != metadata["sha256"]:
        return None
    return data


def fetch_one(record: dict, cache_dir: Path, downloader=download, ocr=None,
              overrides: list[dict] | None = None,
              seen_shas: set[str] | None = None) -> dict:
    """Return one output record, downloading only on a cold or invalid cache.

    Raises InvalidPdf when the bytes are not a PDF or cannot be parsed, and
    NoTextRecovered, EmptyOcrPage or OcrLowConfidence when no usable text
    results. A corrupt cached PDF is retried once from the source before that
    error is reported, so a bad download cannot stick forever. ``ocr`` is a
    provider (see above); the default runs tesseract through the per-PDF
    cache.
    """
    pdf_path = cache_path(cache_dir, record["file_url"])
    data = _cached_bytes(pdf_path)
    from_cache = data is not None
    text_pages: list[dict] | None = None
    while text_pages is None:
        if data is None:
            data = downloader(record["file_url"])
            if not _is_pdf(data):
                raise InvalidPdf(f"{record['file_url']} did not return a PDF")
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            _write_atomic(pdf_path, data)
            _write_sidecar(pdf_path, {
                "sha256": sha256_hex(data),
                "size_bytes": len(data),
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            })
            from_cache = False
        try:
            text_pages = extract_pages(data)
        except Exception as exc:
            if from_cache:
                data = None
                from_cache = False
                continue
            raise InvalidPdf(f"could not parse the PDF: {exc}") from exc

    sha = sha256_hex(data)
    if seen_shas is not None:
        seen_shas.add(sha)
    provider = ocr if ocr is not None else CachedOcr(LiveOcr(), ocr_cache_path(pdf_path))
    read = read_pages(data, sha, provider, overrides, text_pages=text_pages)

    metadata = _read_sidecar(pdf_path) or {}
    return {
        "committee_id": record["committee_id"],
        "committee_name": record["committee_name"],
        "public_body_id": record["public_body_id"],
        "page_url": record["page_url"],
        "layout": record.get("layout"),
        "file_url": record["file_url"],
        "link_text": record["link_text"],
        "sha256": sha,
        "size_bytes": len(data),
        "retrieved_at": metadata.get("retrieved_at")
        or datetime.fromtimestamp(pdf_path.stat().st_mtime, timezone.utc).isoformat(),
        "page_count": len(read["pages"]),
        "text_source": read["text_source"],
        "ocr_engine": read["ocr_engine"],
        "ocr_skipped_pages": read["skipped_pages"],
        "pages": read["pages"],
    }


def run(input_data: dict, cache_dir: Path, downloader=download, ocr=None,
        overrides: list[dict] | None = None) -> tuple[list[dict], list[dict]]:
    """Fetch every discovered file; return ``(records, errors)``."""
    records: list[dict] = []
    errors: list[dict] = []
    seen: set[str] = set()
    for source in input_data.get("results", []):
        try:
            records.append(fetch_one(source, cache_dir, downloader=downloader,
                                     ocr=ocr, overrides=overrides, seen_shas=seen))
        except NoTextRecovered:
            errors.append(_error(
                "NoTextRecovered",
                f"no text-layer or OCR words in {source['file_url']}",
                source,
            ))
        except OcrLowConfidence as exc:
            errors.append(_error(
                "OcrLowConfidence", f"{source['file_url']}: {exc}", source,
                page=exc.page, mean_confidence=round(exc.confidence, 1),
            ))
        except EmptyOcrPage as exc:
            errors.append(_error(
                "EmptyOcrPage", f"{source['file_url']}: {exc}", source, page=exc.page,
            ))
        except InvalidPdf as exc:
            errors.append(_error(
                "InvalidPdf",
                f"{source['file_url']}: {exc}",
                source,
            ))
        except Exception as exc:
            errors.append(_error(
                "DownloadFailed",
                f"could not download {source['file_url']}: {exc}",
                source,
            ))
    for entry in stale_overrides(overrides or [], seen):
        errors.append({
            "step": STEP_NAME,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_type": "StaleOcrOverride",
            "error_message": (
                f"ocr_overrides.json entry for sha256 {entry['file_sha256']} "
                f"page {entry['page']} matches no fetched file"),
            "context": {"file_sha256": entry["file_sha256"], "page": entry["page"]},
        })
    return records, errors


def _error(error_type: str, message: str, record: dict, **extra) -> dict:
    return {
        "step": STEP_NAME,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "error_type": error_type,
        "error_message": message,
        "context": {
            "committee_id": record.get("committee_id"),
            "public_body_id": record.get("public_body_id"),
            "file_url": record.get("file_url"),
            **extra,
        },
    }
