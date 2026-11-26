"""Download minutes PDFs into a git-ignored cache and record their content.

One record per successfully fetched and text-bearing PDF. A download that
fails produces an error and no record; a PDF with no extractable text on any
page produces a ``NoTextLayer`` error and no record (the pipeline never runs
OCR).
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


class NoTextLayer(ValueError):
    """The PDF yields no extractable text on any page."""


class InvalidPdf(ValueError):
    """The downloaded or cached bytes are not a readable PDF."""


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
    """Per-page words with coordinates. Raises NoTextLayer if no page has text."""
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
    if not any(page["words"] for page in pages):
        raise NoTextLayer("no extractable text on any page")
    return pages


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


def fetch_one(record: dict, cache_dir: Path, downloader=download) -> dict:
    """Return one output record, downloading only on a cold or invalid cache.

    Raises NoTextLayer when the PDF has no text, and InvalidPdf when the bytes
    are not a PDF or cannot be parsed. A corrupt cached PDF is retried once
    from the source before that error is reported, so a bad download cannot
    stick forever.
    """
    pdf_path = cache_path(cache_dir, record["file_url"])
    data = _cached_bytes(pdf_path)
    from_cache = data is not None
    pages: list[dict] | None = None
    while pages is None:
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
            pages = extract_pages(data)
        except NoTextLayer:
            raise
        except Exception as exc:
            if from_cache:
                data = None
                continue
            raise InvalidPdf(f"could not parse the PDF: {exc}") from exc

    metadata = _read_sidecar(pdf_path) or {}
    return {
        "committee_id": record["committee_id"],
        "committee_name": record["committee_name"],
        "public_body_id": record["public_body_id"],
        "page_url": record["page_url"],
        "file_url": record["file_url"],
        "link_text": record["link_text"],
        "sha256": sha256_hex(data),
        "size_bytes": len(data),
        "retrieved_at": metadata.get("retrieved_at")
        or datetime.fromtimestamp(pdf_path.stat().st_mtime, timezone.utc).isoformat(),
        "page_count": len(pages),
        "pages": pages,
    }


def run(input_data: dict, cache_dir: Path, downloader=download) -> tuple[list[dict], list[dict]]:
    """Fetch every discovered file; return ``(records, errors)``."""
    records: list[dict] = []
    errors: list[dict] = []
    for source in input_data.get("results", []):
        try:
            records.append(fetch_one(source, cache_dir, downloader=downloader))
        except NoTextLayer:
            errors.append(_error(
                "NoTextLayer",
                f"no extractable text in {source['file_url']}",
                source,
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
    return records, errors


def _error(error_type: str, message: str, record: dict) -> dict:
    return {
        "step": STEP_NAME,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "error_type": error_type,
        "error_message": message,
        "context": {
            "committee_id": record.get("committee_id"),
            "public_body_id": record.get("public_body_id"),
            "file_url": record.get("file_url"),
        },
    }
