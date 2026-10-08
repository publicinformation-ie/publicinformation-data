#!/usr/bin/env python3
import argparse
import hashlib
import io
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from xml.parsers import expat as pyexpat
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup, Comment

from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import append_error, read_json, write_json, write_status, IncrementalWriter
from lib.http_utils import fetch

STEP_NAME = "transform_minutes_files"


def _extract_pdfplumber(pdf_bytes: bytes) -> str:
    """Fallback extractor. Returns '' on failure/empty."""
    try:
        import pdfplumber
        parts = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                parts.append(page.extract_text() or "")
        return "\n".join(parts)
    except Exception:
        return ""


def extract_text(pdf_bytes: bytes):
    """Return (text, extractor). pdfplumber is the sole extractor."""
    text = _extract_pdfplumber(pdf_bytes)
    if text and text.strip():
        return text, "pdfplumber"
    return "", "pdfplumber"


def _cache_path(cache_dir, url, suffix=".pdf"):
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    return Path(cache_dir) / f"{digest}{suffix}"


_PDF_MAGIC = b"%PDF-"
# A .docx is a zip archive; the PK\x03\x04 local-file header opens it.
_ZIP_MAGIC = b"PK\x03\x04"
_DOC_SUFFIXES = {"pdf": ".pdf", "docx": ".docx"}
_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


_MAX_DOCX_XML_BYTES = 50 * 1024 * 1024


def _refuse_dtd(xml_bytes: bytes) -> None:
    """Raise if the XML declares a DOCTYPE or entity. Checked by the expat
    parser itself, not by searching bytes: a UTF-16 document has no
    b"<!DOCTYPE" sequence to find, but expat still reads its declarations."""
    def refuse(*_):
        raise ValueError("Word document XML declares a DOCTYPE; refusing to parse")
    parser = pyexpat.ParserCreate()
    parser.StartDoctypeDeclHandler = refuse
    parser.EntityDeclHandler = refuse
    parser.Parse(xml_bytes, True)


_MC_NS = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"


def _own_paragraphs(root):
    """Every <w:p> in document order, except those under <mc:Fallback>, which
    repeats the sibling <mc:Choice>. Iterative: nested text boxes can be deep."""
    stack = [root]
    while stack:
        node = stack.pop()
        if node.tag == _W_NS + "p":
            yield node
        stack.extend(reversed([c for c in node if c.tag != _MC_NS + "Fallback"]))


def _paragraph_text(para) -> str:
    """Text of one paragraph. Nested <w:p> (text boxes) are skipped here
    because `_own_paragraphs` yields them as paragraphs of their own."""
    parts = []
    stack = list(reversed(list(para)))
    while stack:
        node = stack.pop()
        if node.tag in (_W_NS + "p", _MC_NS + "Fallback"):
            continue
        if node.tag == _W_NS + "t":
            parts.append(node.text or "")
        elif node.tag == _W_NS + "tab":
            parts.append(" ")
        elif node.tag in (_W_NS + "br", _W_NS + "cr"):
            parts.append("\n")
        stack.extend(reversed(list(node)))
    return "".join(parts)


def extract_docx_text(docx_bytes: bytes) -> str:
    """Prose text of a Word document: one line per paragraph, tabs as spaces,
    line breaks kept. Reads word/document.xml only; table cells are included
    because their paragraphs are ordinary <w:p> elements. Refuses a
    word/document.xml that inflates past _MAX_DOCX_XML_BYTES (zip bomb)."""
    try:
        with zipfile.ZipFile(io.BytesIO(docx_bytes)) as archive:
            with archive.open("word/document.xml") as member:
                xml_bytes = member.read(_MAX_DOCX_XML_BYTES + 1)
    except (zipfile.BadZipFile, KeyError) as e:
        raise ValueError("file is not a Word document (no word/document.xml)") from e
    if len(xml_bytes) > _MAX_DOCX_XML_BYTES:
        raise ValueError("Word document XML is too large to extract")
    _refuse_dtd(xml_bytes)
    lines = []
    for para in _own_paragraphs(ET.fromstring(xml_bytes)):
        lines.extend(ln.strip() for ln in _paragraph_text(para).split("\n") if ln.strip())
    return "\n".join(lines)


def extract_document_text(data: bytes):
    """Return (text, extractor) for a PDF or Word document, chosen by magic bytes."""
    head = data.strip()
    if head.startswith(_PDF_MAGIC):
        return extract_text(data)
    if head.startswith(_ZIP_MAGIC):
        return extract_docx_text(data), "docx"
    raise ValueError("document is neither a PDF nor a DOCX "
                     "(missing %PDF- or PK zip magic bytes)")


def _download(url, cache_dir):
    """Fetch a PDF or DOCX minutes file, persisting it to the cache so re-runs
    don't re-fetch. The cache entry keeps the document's own suffix.

    Fails closed on any other body (e.g. an HTML error page served with a
    200) and writes via a temp file + rename so an interrupted download can
    never leave a truncated file as a valid cache entry."""
    for suffix in _DOC_SUFFIXES.values():
        path = _cache_path(cache_dir, url, suffix)
        if path.exists():
            return path.read_bytes()
    response = fetch("GET", url, allow_redirects=True)
    data = response.content
    head = data.strip()
    if head.startswith(_PDF_MAGIC):
        suffix = _DOC_SUFFIXES["pdf"]
    elif head.startswith(_ZIP_MAGIC):
        suffix = _DOC_SUFFIXES["docx"]
    else:
        raise ValueError(f"response from {url} is neither a PDF nor a DOCX "
                         "(missing %PDF- or PK zip magic bytes)")
    path = _cache_path(cache_dir, url, suffix)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_bytes(data)
    tmp_path.replace(path)
    return data


_BLOCK_TAGS = ["p", "div", "li", "ul", "ol", "tr", "table", "h1", "h2", "h3",
               "h4", "h5", "h6", "section", "article", "header", "footer",
               "blockquote", "pre", "dt", "dd"]


def extract_html_text(html: str, selector: str) -> str:
    """Return the text of the first element matching `selector`.

    Fails closed: a selector that matches nothing (site redesign) or yields
    only whitespace raises, so no empty record flows downstream."""
    node = BeautifulSoup(html, "html.parser").select_one(selector)
    if node is None:
        raise ValueError(f"selector {selector!r} matched nothing")
    # Newlines only at block boundaries: inline tags (<sup>, <strong>, ...)
    # must not split a sentence ("9<sup>th</sup>" -> "9th").
    for tag in node.find_all(["script", "style", "noscript", "template"]):
        tag.decompose()
    for c in node.find_all(string=lambda x: isinstance(x, Comment)):
        c.extract()
    for t in node.find_all(string=True):
        t.replace_with(re.sub(r"\s+", " ", str(t)))  # source wrapping is not a line break
    for br in node.find_all("br"):
        # html.parser can nest following content inside a <br> (after an
        # earlier unclosed <br>); unwrap so those children are kept.
        br.insert_before("\n")
        br.unwrap()
    for blk in node.find_all(_BLOCK_TAGS):
        blk.insert_before("\n")
        blk.insert_after("\n")
    raw = node.get_text("")
    lines = (re.sub(r"[ \t\r\f\v\xa0]+", " ", ln).strip() for ln in raw.split("\n"))
    text = "\n".join(ln for ln in lines if ln)
    if not text:
        raise ValueError(f"selector {selector!r} produced empty text")
    return text


def _html_text(url, cache_dir, selector):
    """Return extracted text for an HTML minutes page.

    The raw body is cached as `<digest>.html` only after the HTTP status and
    selector extraction have been validated, so error pages are never cached.
    A cache hit is re-extracted."""
    path = _cache_path(cache_dir, url).with_suffix(".html")
    if path.exists():
        return extract_html_text(path.read_text(encoding="utf-8"), selector)
    resp = fetch("GET", url, allow_redirects=True)
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code} fetching {url}")
    html = resp.text
    text = extract_html_text(html, selector)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(html, encoding="utf-8")
    tmp_path.replace(path)
    return text


def _process_one(item, cache_dir):
    url = item["file_url"]
    try:
        if item.get("file_kind") == "html":
            text = _html_text(url, cache_dir, item["text_selector"])
            return url, {**item, "text": text, "extractor": "html"}, None
        document = _download(url, cache_dir)
        text, extractor = extract_document_text(document)
        return item["file_url"], {**item, "text": text, "extractor": extractor}, None
    except Exception as e:
        return item["file_url"], None, e


def process(input_data, step_dir, writer, verbose=False, max_workers=4):
    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])

    cache_dir = step_dir / "pdf_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    pending = [item for item in input_data["results"]
               if not writer.is_processed(item["file_url"])]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_process_one, item, cache_dir): item for item in pending}
        for future in as_completed(futures):
            file_url, record, exc = future.result()
            if exc is not None:
                append_error(step_dir, {
                    "step": STEP_NAME,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "context": {"file_url": file_url,
                                "public_body_id": record["public_body_id"]
                                if record else None},
                })
                writer.append([])
            else:
                if not (record.get("text") or "").strip():
                    append_error(step_dir, {
                        "step": STEP_NAME,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "error_type": "EmptyTextExtraction",
                        "error_message": "pdfplumber returned empty text",
                        "context": {"file_url": file_url,
                                    "public_body_id": record.get("public_body_id")},
                    })
                writer.append([record])
            if verbose:
                print(".", end="", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Extract prose text from minutes PDFs")
    add_common_args(parser)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)

    try:
        input_data = read_json(args.input)
    except Exception as e:
        print(f"Fatal: could not read input: {e}", file=sys.stderr)
        sys.exit(1)
    input_data = filter_by_public_body(input_data, args.public_body)
    if args.public_body is not None and not (input_data.get("results")):
        print(f"No input record for public_body_id={args.public_body}", file=sys.stderr)
        sys.exit(0)

    writer = IncrementalWriter(output_path, STEP_NAME, key_field="file_url", force=args.force,
                               upstream_dirty_path=Path(args.input).parent / "dirty_ids.json",
                               target_public_body=args.public_body)

    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")

    process(input_data, step_dir, writer, verbose=args.verbose, max_workers=args.workers)
    count = writer.finalize()
    write_status(step_dir, count)
    print(f"Wrote {count} records to {output_path}")


if __name__ == "__main__":
    main()
