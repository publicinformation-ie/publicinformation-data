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


def markdown_to_rows(markdown):
    """Convert Mistral OCR markdown output to pipeline rows format.

    Handles multiple tables separated by --- (page breaks), multi-line
    cells (joined with space), and markdown formatting (stripped).
    Returns [] if no tables found.
    """
    if not markdown or not markdown.strip():
        return []

    all_rows = []
    sections = re.split(r'\n---\n', markdown)

    for section in sections:
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

            all_rows.extend(processed_rows)

    return all_rows


def _normalise_cell(cell):
    """Normalise a cell for header comparison. Duplicated from process.py's
    identically-named function to avoid a circular import between the two
    peer modules; keep both in sync if the normalisation rule changes."""
    if cell is None:
        return ""
    return " ".join(str(cell).strip().split()).lower()


def _strip_duplicate_headers(rows):
    """Drop rows that exactly match row 0's normalised header.

    Mistral's extract_header=True guarantees each page-table starts with a
    complete header row — there's no partial/split header to align (unlike
    process.py's _merge_page_splits fingerprint alignment), just an exact
    repeat to remove. Returns (deduped_rows, count_stripped).
    """
    if not rows:
        return rows, 0
    header = tuple(_normalise_cell(c) for c in rows[0])
    deduped = [rows[0]]
    count = 0
    for row in rows[1:]:
        if tuple(_normalise_cell(c) for c in row) == header:
            count += 1
        else:
            deduped.append(row)
    return deduped, count


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
