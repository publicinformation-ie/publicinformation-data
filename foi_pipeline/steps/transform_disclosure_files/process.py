#!/usr/bin/env python3
import argparse
import concurrent.futures
import datetime
import decimal
import fcntl
import hashlib
import io
import os
import sys
import tempfile
import time
from pathlib import Path

from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import append_error, read_json, write_json, write_status, IncrementalWriter
from lib.http_utils import fetch

STEP_NAME = "transform_disclosure_files"


class DisclosureFileCache:
    """Thread-safe cache for downloaded disclosure files.

    Stores files in a cache/ directory keyed by SHA256 hash of the URL.
    Uses file locking to prevent concurrent downloads of the same URL.
    """

    def __init__(self, cache_dir):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _url_hash(self, file_url):
        return hashlib.sha256(file_url.encode("utf-8")).hexdigest()

    def _get_cache_path(self, file_url):
        return self.cache_dir / f"{self._url_hash(file_url)}.bytes"

    def _lock_path(self, file_url):
        return self.cache_dir / f"{self._url_hash(file_url)}.lock"

    def _acquire_lock(self, lock_path, timeout=300):
        """Acquire an exclusive file lock. Returns the open fd holding the lock, or None on timeout."""
        lock_file = open(lock_path, "w")
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return lock_file
            except (IOError, OSError):
                time.sleep(0.1)
        # One final attempt — handles the case where the holder died without releasing
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return lock_file
        except (IOError, OSError):
            lock_file.close()
            return None

    def _release_lock(self, lock_file):
        """Release a file lock."""
        try:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
            lock_file.close()
        except Exception:
            pass

    def get_file_path(self, file_url, step_dir):
        """Download and cache file if not present, return path to cached file.

        Args:
            file_url: URL of the file to download
            step_dir: Step directory (for error reporting)

        Returns:
            Path to the cached file
        """
        from lib.http_utils import fetch
        from lib.file_utils import append_error

        cache_path = self._get_cache_path(file_url)
        lock_path = self._lock_path(file_url)

        # Check if file exists and is readable
        if cache_path.exists():
            try:
                with open(cache_path, "rb") as f:
                    f.read(1)  # Test read
                return cache_path
            except (IOError, OSError):
                # File exists but is corrupted
                cache_path.unlink(missing_ok=True)

        # Need to download - acquire lock
        lock_file = self._acquire_lock(lock_path)
        if lock_file is None:
            raise RuntimeError(f"Could not acquire lock for {file_url} after timeout")
        try:

            # Double-check another process didn't download while we waited
            if cache_path.exists():
                try:
                    with open(cache_path, "rb") as f:
                        f.read(1)
                    return cache_path
                except (IOError, OSError):
                    cache_path.unlink(missing_ok=True)

            # Download to temp file first (atomic write)
            temp_fd, temp_path = tempfile.mkstemp(dir=str(self.cache_dir))
            try:
                response = fetch("GET", file_url, allow_redirects=True)
                with os.fdopen(temp_fd, "wb") as f:
                    f.write(response.content)
                # Atomic rename
                os.replace(temp_path, str(cache_path))
                return cache_path
            except Exception as e:
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                append_error(step_dir, {
                    "step": STEP_NAME,
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "context": {"file_url": file_url},
                })
                raise DownloadError(str(e)) from e
        finally:
            self._release_lock(lock_file)


class DownloadError(Exception):
    """Raised when file download fails."""
    pass


def serialise_cell(value):
    """Convert a cell value to a JSON-safe type. Returns (value, used_fallback)."""
    if value is None:
        return None, False
    if isinstance(value, bool):
        return value, False
    if isinstance(value, (str, int, float)):
        return value, False
    if isinstance(value, datetime.datetime):
        return value.isoformat(), False
    if isinstance(value, datetime.date):
        return value.isoformat(), False
    if isinstance(value, decimal.Decimal):
        return float(value), False
    return str(value), True


def _normalise_cell(cell):
    """Normalise a cell for header fingerprint comparison."""
    if cell is None:
        return ""
    return " ".join(str(cell).strip().split()).lower()


def _merge_page_splits(
    pages_rows: list[list[list]],
    header_k: int = 6,
    null_threshold: float = 0.4,
) -> tuple[list[list], dict]:
    """Merge rows split across page boundaries in a pdfplumber extraction.

    Returns (flat_rows, stats) where stats contains page_split_merges
    and header_rows_stripped counts.
    """
    if not pages_rows:
        return [], {"page_split_merges": 0, "header_rows_stripped": 0}

    page_split_merges = 0
    header_rows_stripped = 0

    # Build header fingerprint from first page (up to K rows)
    page1 = pages_rows[0]
    k = min(header_k, len(page1))
    fingerprint = [tuple(_normalise_cell(c) for c in row) for row in page1[:k]]

    accumulated = list(page1)

    for page_rows in pages_rows[1:]:
        remaining = list(page_rows)

        # Strip rows from the top of this page that sequentially match the fingerprint
        fp_idx = 0
        while remaining and fp_idx < len(fingerprint):
            candidate = tuple(_normalise_cell(c) for c in remaining[0])
            if candidate == fingerprint[fp_idx]:
                remaining.pop(0)
                header_rows_stripped += 1
                fp_idx += 1
            else:
                break

        # Merge continuation row: first remaining row is a continuation if
        # it has more than null_threshold fraction of None cells AND the previous
        # row also has more than null_threshold fraction of None cells
        if remaining and accumulated:
            row = remaining[0]
            last = accumulated[-1]
            n_cells = len(row)
            n_last_cells = len(last)
            row_null_frac = sum(1 for c in row if c is None) / n_cells if n_cells > 0 else 0
            last_null_frac = sum(1 for c in last if c is None) / n_last_cells if n_last_cells > 0 else 0
            if row_null_frac > null_threshold and last_null_frac > null_threshold:
                merged = []
                for a, b in zip(last, row):
                    if a is not None and b is not None:
                        merged.append(f"{a} {b}")
                    elif a is not None:
                        merged.append(a)
                    else:
                        merged.append(b)
                # Preserve any extra cells if row widths differ
                if len(row) > len(last):
                    merged.extend(row[len(last):])
                accumulated[-1] = merged
                remaining.pop(0)
                page_split_merges += 1

        accumulated.extend(remaining)

    return accumulated, {
        "page_split_merges": page_split_merges,
        "header_rows_stripped": header_rows_stripped,
    }


def _extract_xlsx(file_bytes):
    """Parse XLSX bytes. Returns (sheet_name, rows, fallback_cells, has_multiple_sheets)."""
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    has_multiple_sheets = any(
        any(v is not None for row in ws.iter_rows(values_only=True) for v in row)
        for ws in wb.worksheets[1:]
    )
    ws = wb.worksheets[0]
    sheet_name = ws.title
    rows = []
    fallback_cells = []
    for row_idx, row in enumerate(ws.iter_rows(values_only=True)):
        serialised_row = []
        for col_idx, cell_val in enumerate(row):
            val, used_fallback = serialise_cell(cell_val)
            if used_fallback:
                fallback_cells.append(
                    (row_idx, col_idx, type(cell_val).__name__, repr(cell_val)[:50])
                )
            serialised_row.append(val)
        rows.append(serialised_row)
    wb.close()
    return sheet_name, rows, fallback_cells, has_multiple_sheets


def _xlrd_cell_to_python(cell, datemode):
    """Convert an xlrd Cell to a Python value suitable for serialise_cell."""
    import xlrd
    if cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
        return None
    if cell.ctype == xlrd.XL_CELL_TEXT:
        return cell.value
    if cell.ctype == xlrd.XL_CELL_NUMBER:
        return cell.value  # always float from xlrd
    if cell.ctype == xlrd.XL_CELL_DATE:
        return datetime.datetime(*xlrd.xldate_as_tuple(cell.value, datemode))
    if cell.ctype == xlrd.XL_CELL_BOOLEAN:
        return bool(cell.value)
    return cell.value  # XL_CELL_ERROR — hits str() fallback in serialise_cell


def _extract_xls(file_bytes):
    """Parse XLS bytes. Returns (sheet_name, rows, fallback_cells, has_multiple_sheets)."""
    import xlrd
    wb = xlrd.open_workbook(file_contents=file_bytes)
    has_multiple_sheets = any(ws.nrows > 0 for ws in wb.sheets()[1:])
    ws = wb.sheets()[0]
    sheet_name = ws.name
    rows = []
    fallback_cells = []
    for row_idx in range(ws.nrows):
        serialised_row = []
        for col_idx in range(ws.ncols):
            raw = _xlrd_cell_to_python(ws.cell(row_idx, col_idx), wb.datemode)
            val, used_fallback = serialise_cell(raw)
            if used_fallback:
                fallback_cells.append(
                    (row_idx, col_idx, type(raw).__name__, repr(raw)[:50])
                )
            serialised_row.append(val)
        rows.append(serialised_row)
    return sheet_name, rows, fallback_cells, has_multiple_sheets


_DEFAULT_PDF_TABLE_SETTINGS = {
    "snap_y_tolerance": 3,
    "snap_tolerance": 6,
    "edge_min_length": 10,
}


def _extract_pdf(file_bytes, table_settings=None):
    """Parse PDF bytes. Returns (sheet_name, rows, fallback_cells, has_multiple_tables)."""
    import pdfplumber
    rows = []
    total_tables = 0
    _ts = table_settings if table_settings is not None else _DEFAULT_PDF_TABLE_SETTINGS
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        n_pages = len(pdf.pages)
        for page in pdf.pages:
            tables = page.extract_tables(table_settings=_ts)
            total_tables += len(tables)
            for table in tables:
                for row in table:
                    serialised_row = [serialise_cell(cell)[0] for cell in row]
                    rows.append(serialised_row)
    if total_tables == 0:
        raise ValueError("no tables found")
    sheet_name = "page 1" if n_pages == 1 else f"pages 1-{n_pages}"
    return sheet_name, rows, [], total_tables > 1


def _process_single_file(item, cache, step_dir):
    """Process a single file. Called by worker processes.

    Args:
        item: A result item from input_data
        cache: DisclosureFileCache instance
        step_dir: Step directory path

    Returns:
        List of result dicts to append (typically 0 or 1 items)
    """
    file_url = item["file_url"]
    file_type = item["file_type"]

    try:
        # Get file from cache (downloads if needed)
        cached_path = cache.get_file_path(file_url, step_dir)
        with open(cached_path, "rb") as f:
            file_bytes = f.read()

        if file_type == "xlsx":
            sheet_name, rows, fallback_cells, has_multiple = _extract_xlsx(file_bytes)
            if has_multiple:
                append_error(step_dir, {
                    "step": STEP_NAME,
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "error_type": "MultipleSheetWarning",
                    "error_message": "File has multiple sheets; only the first sheet was extracted.",
                    "context": {"file_url": file_url},
                })
        elif file_type == "xls":
            sheet_name, rows, fallback_cells, has_multiple = _extract_xls(file_bytes)
            if has_multiple:
                append_error(step_dir, {
                    "step": STEP_NAME,
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "error_type": "MultipleSheetWarning",
                    "error_message": "File has multiple sheets; only the first sheet was extracted.",
                    "context": {"file_url": file_url},
                })
        else:  # pdf
            sheet_name, rows, fallback_cells, has_multiple = _extract_pdf(file_bytes)
            if has_multiple:
                append_error(step_dir, {
                    "step": STEP_NAME,
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "error_type": "MultipleTableWarning",
                    "error_message": "File has multiple tables; all table rows were concatenated.",
                    "context": {"file_url": file_url},
                })

        if fallback_cells:
            append_error(step_dir, {
                "step": STEP_NAME,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "error_type": "CellSerializationWarning",
                "error_message": f"{len(fallback_cells)} cell(s) used str() fallback.",
                "context": {"file_url": file_url, "cells": fallback_cells},
            })

        return [{**item, "sheet_name": sheet_name, "rows": rows}], True

    except DownloadError:
        # Already logged by cache - don't re-log
        return [], False  # not marked processed — allows retry on next run

    except Exception as e:
        append_error(step_dir, {
            "step": STEP_NAME,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "error_type": type(e).__name__,
            "error_message": str(e),
            "context": {"file_url": file_url},
        })
        return [], True  # marked processed — parse errors are permanent failures


def process(input_data, step_dir, writer, verbose=False, workers=4):
    errors_path = Path(step_dir) / "errors.json"
    if not errors_path.exists():
        write_json(errors_path, [])

    # Initialize cache
    cache = DisclosureFileCache(Path(step_dir) / "cache")

    # Filter out already processed items
    items_to_process = [
        item for item in input_data["results"]
        if not writer.is_processed(item["file_url"])
    ]

    if not items_to_process:
        return

    # Process in parallel using ThreadPoolExecutor
    # Note: We use threads instead of processes because:
    # 1. pdfplumber releases the GIL during CPU-intensive parsing
    # 2. File I/O also releases the GIL
    # 3. Threads can share the cache and step_dir objects without pickling
    # This gives us effective parallelism while avoiding pickling issues
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        # Submit all tasks and collect futures to preserve order
        futures = [executor.submit(_process_single_file, item, cache, step_dir) 
                  for item in items_to_process]
        results = [f.result() for f in futures]

    all_results = []
    for i, (result_list, mark_processed) in enumerate(results):
        file_url = items_to_process[i]["file_url"]
        all_results.extend(result_list)
        if not result_list and mark_processed:
            writer.processed_keys.add(file_url)

    writer.append(all_results)

    if verbose:
        print(".", end="", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Download and convert disclosure log files (XLSX/XLS/PDF) to JSON arrays"
    )
    add_common_args(parser)
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers for file processing (default: 4)",
    )
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)
    override_path = step_dir / "override.json"

    try:
        input_data = read_json(args.input)
    except Exception as e:
        print(f"Fatal: could not read input: {e}", file=sys.stderr)
        sys.exit(1)
    input_data = filter_by_public_body(input_data, args.public_body)
    if args.public_body is not None and not (
        input_data.get("results") or input_data.get("public_bodies")
    ):
        print(f"No input record for public_body_id={args.public_body}", file=sys.stderr)
        sys.exit(0)

    writer = IncrementalWriter(
        output_path, STEP_NAME, key_field="file_url", force=args.force,
        override_path=override_path,
        upstream_dirty_path=Path(args.input).parent / "dirty_ids.json",
        target_public_body=args.public_body,
    )

    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")

    process(input_data, step_dir, writer, verbose=args.verbose, workers=args.workers)
    count = writer.finalize()
    write_status(step_dir, count)
    if args.verbose:
        print()
    print(f"Wrote {count} records to {output_path}")


if __name__ == "__main__":
    main()
