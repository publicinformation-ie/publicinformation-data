"""Shared PDF-bytes fetching and rasterization for the local OCR comparison.

steps/verify_disclosure_files/cache/ is the shared PDF-bytes cache keyed by
sha256(file_url).bytes — confirmed warm for all 1252 PDFs in the eval
fixture. (steps/transform_disclosure_files/cache/ uses the same key
convention but is currently empty on this machine; don't read from it.)
get_pdf_bytes treats a miss as "download and cache it", never as "skip this
file" or "re-run the pipeline step".

marker-pdf consumes PDF bytes/paths directly; PP-StructureV3 and the Ollama
vision models need page images, so page rasterization lives here once.
"""
import base64
from pathlib import Path

import pymupdf
import requests


def get_pdf_bytes(cache_dir: Path, file_url: str, sha256: str, timeout: int = 30) -> bytes:
    """Return cached PDF bytes for file_url, downloading and caching on a miss.

    cache_dir / f"{sha256}.bytes" is the same layout used by both
    steps/verify_disclosure_files/process.py and
    steps/transform_disclosure_files/process.py's DisclosureFileCache, so a
    download here also warms whichever cache_dir is passed in for anything
    else that reads it. Callers in this experiment pass
    steps/verify_disclosure_files/cache/ (confirmed warm for the sample).
    """
    cache_path = Path(cache_dir) / f"{sha256}.bytes"
    if cache_path.exists():
        return cache_path.read_bytes()
    response = requests.get(file_url, timeout=timeout)
    response.raise_for_status()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(response.content)
    return response.content


def render_pdf_pages_to_png(pdf_bytes: bytes, dpi: int = 150) -> list[bytes]:
    """Render every page of a PDF to PNG bytes at the given DPI."""
    zoom = dpi / 72
    matrix = pymupdf.Matrix(zoom, zoom)
    pages = []
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            pix = page.get_pixmap(matrix=matrix)
            pages.append(pix.tobytes("png"))
    return pages


def png_to_data_uri(png_bytes: bytes) -> str:
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"
