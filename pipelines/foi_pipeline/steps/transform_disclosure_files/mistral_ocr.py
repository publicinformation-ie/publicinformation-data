#!/usr/bin/env python3
"""Mistral OCR extraction for PDF disclosure files.

Ported markdown parsing from
experiments/2025-01-03-mistral-ocr-comparison/convert.py.
"""
import datetime
import hashlib
import json
import re
import time
from pathlib import Path

from mistralai.client import Mistral

MISTRAL_OCR_MODEL = "mistral-ocr-latest"

_PAGE_BREAK_MARKER = "\n\n<<<MISTRAL_PAGE_BREAK>>>\n\n"


def parse_markdown_table(table_text):
    """Parse a single markdown table into rows.

    Handles multi-line cells where content continues on the next line
    without the leading | character.
    """
    lines = table_text.strip().split('\n')
    if not lines:
        return []

    rows = []
    current_row = []
    in_table = False

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Skip separator lines (|---|---|) - lines that contain only |, -, :, and spaces
        if re.match(r'^\|[\s\-:|]+\|$', line):
            in_table = True
            continue

        if line.startswith('|'):
            if current_row:
                rows.append(current_row)
                current_row = []
            in_table = True
            line = line.strip()
            if line.startswith('|'):
                line = line[1:]
            if line.endswith('|'):
                line = line[:-1]
            cells = [cell.strip() for cell in line.split('|') if cell.strip()]
            current_row = cells
        elif in_table and current_row:
            continuation = line.rstrip('|').strip()
            if continuation:
                current_row[-1] = current_row[-1] + '\n' + continuation
        elif in_table:
            pass

    if current_row:
        rows.append(current_row)

    return rows


def strip_markdown_formatting(text):
    """Strip bold/italic/code/strikethrough/link markdown formatting from text."""
    if not text:
        return text

    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    text = re.sub(r'~~(.+?)~~', r'\1', text)
    text = re.sub(r'\[(.+?)\]\([^)]*\)', r'\1', text)

    return text


def markdown_to_pages(markdown):
    """Convert Mistral OCR markdown output to per-page pipeline rows.

    Splits on the literal _PAGE_BREAK_MARKER inserted by call_mistral_ocr,
    parsing each page's markdown independently. Returning rows grouped by
    page (rather than one flattened list) lets process._merge_page_splits
    align repeated header rows across page boundaries — it already handles
    a title/subtitle preamble on page 1 that never repeats on later pages,
    which a flat list discards the information needed to detect.
    Returns [] if no tables were found on any page.
    """
    if not markdown or not markdown.strip():
        return []

    pages = []
    for section in markdown.split(_PAGE_BREAK_MARKER):
        if not section.strip():
            continue

        section = section.replace('\r\n', '\n')
        table_rows = parse_markdown_table(section)

        if table_rows:
            processed_rows = []
            for row in table_rows:
                processed_row = []
                for cell in row:
                    cell = cell.replace('\n', ' ')
                    cell = strip_markdown_formatting(cell)
                    processed_row.append(cell)
                processed_rows.append(processed_row)
            pages.append(processed_rows)

    return pages


def call_mistral_ocr(file_url, cache_dir, base_url, api_key, semaphore=None, max_retries=3):
    """Return raw Mistral OCR markdown for file_url, checking ocr_cache/ first.

    On a cache miss, calls the Mistral client with document_url pointing at
    {base_url}/{sha256}.bytes, retrying with exponential backoff on failure.
    Writes a successful response (including an empty-tables "" result) to
    ocr_cache/{sha256}.json before returning. Returns None only after
    max_retries API failures — a cache write never happens in that case, so
    the next run retries rather than caching a permanent-looking failure.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    sha256 = hashlib.sha256(file_url.encode("utf-8")).hexdigest()
    cache_path = cache_dir / f"{sha256}.json"

    if cache_path.exists():
        cached = json.loads(cache_path.read_text())
        return cached["markdown"]

    document_url = f"{base_url.rstrip('/')}/{sha256}.bytes"

    def _do_call():
        client = Mistral(api_key=api_key)
        ocr_response = client.ocr.process(
            model=MISTRAL_OCR_MODEL,
            document={"type": "document_url", "document_url": document_url},
            table_format="markdown",
            extract_header=True,
            confidence_scores_granularity="page",
        )
        markdown_parts = []
        if hasattr(ocr_response, "pages"):
            for page in ocr_response.pages:
                if hasattr(page, "tables") and page.tables:
                    for table in page.tables:
                        if hasattr(table, "markdown") and table.markdown:
                            markdown_parts.append(table.markdown)
                        elif hasattr(table, "content") and table.content:
                            markdown_parts.append(table.content)
        if hasattr(ocr_response, "tables") and ocr_response.tables:
            for table in ocr_response.tables:
                if hasattr(table, "markdown") and table.markdown:
                    markdown_parts.append(table.markdown)
                elif hasattr(table, "content") and table.content:
                    markdown_parts.append(table.content)
        return _PAGE_BREAK_MARKER.join(markdown_parts)

    for attempt in range(max_retries):
        try:
            if semaphore is not None:
                with semaphore:
                    markdown = _do_call()
            else:
                markdown = _do_call()
            cache_path.write_text(json.dumps({
                "file_url": file_url,
                "markdown": markdown,
                "cached_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }))
            return markdown
        except Exception:
            if attempt < max_retries - 1:
                time.sleep((2 ** attempt) * 1)
            else:
                return None
    return None
