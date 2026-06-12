#!/usr/bin/env python3
import argparse
import datetime
import fcntl
import hashlib
import io
import os
import sys
import tempfile
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import append_error, read_json, write_json, write_status, IncrementalWriter
from lib.http_utils import fetch

STEP_NAME = "verify_disclosure_files"

TIER_A = [
    "disclosure log",
    "foi log",
    "foi disclosure",
    "non-personal foi",
    "freedom of information disclosure",
]

TIER_B = [
    "freedom of information",
    "date received",
    "date of decision",
    "decision",
    "request reference",
    "foi",
]


class DisclosureFileCache:
    """Thread-safe download cache keyed by SHA256(url), shared with transform_disclosure_files."""

    def __init__(self, cache_dir):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _url_hash(self, file_url):
        return hashlib.sha256(file_url.encode("utf-8")).hexdigest()

    def _get_cache_path(self, file_url):
        return self.cache_dir / f"{self._url_hash(file_url)}.bytes"

    def _get_lock_path(self, file_url):
        return self.cache_dir / f"{self._url_hash(file_url)}.lock"

    def _acquire_lock(self, lock_path, timeout=300):
        lock_file = open(lock_path, "w")
        start = time.time()
        while time.time() - start < timeout:
            try:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return lock_file
            except (IOError, OSError):
                time.sleep(0.1)
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return lock_file
        except (IOError, OSError):
            lock_file.close()
            return None

    def _release_lock(self, lock_file):
        try:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
            lock_file.close()
        except Exception:
            pass

    def get_file_path(self, file_url, step_dir):
        """Return path to cached file, downloading if not present."""
        cache_path = self._get_cache_path(file_url)

        if cache_path.exists():
            try:
                with open(cache_path, "rb") as f:
                    f.read(1)
                return cache_path
            except (IOError, OSError):
                cache_path.unlink(missing_ok=True)

        lock_file = self._acquire_lock(self._get_lock_path(file_url))
        if lock_file is None:
            raise RuntimeError(f"Could not acquire lock for {file_url} after timeout")
        try:
            if cache_path.exists():
                try:
                    with open(cache_path, "rb") as f:
                        f.read(1)
                    return cache_path
                except (IOError, OSError):
                    cache_path.unlink(missing_ok=True)

            temp_fd, temp_path = tempfile.mkstemp(dir=str(self.cache_dir))
            try:
                response = fetch("GET", file_url, allow_redirects=True)
                if not response.ok:
                    raise DownloadError(f"HTTP {response.status_code} for {file_url}")
                with os.fdopen(temp_fd, "wb") as f:
                    f.write(response.content)
                os.replace(temp_path, str(cache_path))
                return cache_path
            except Exception as e:
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
    pass


def _extract_text_pdf(file_bytes):
    """Extract first-page text via pdfplumber text layer. Returns str or None."""
    import pdfplumber
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            if not pdf.pages:
                return None
            return pdf.pages[0].extract_text() or ""
    except Exception:
        return None


def _extract_text_xlsx(file_bytes):
    """Collect up to 100 cell values from first sheet of an XLSX. Returns str or None."""
    import openpyxl
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
        ws = wb.worksheets[0]
        cells = []
        for row in ws.iter_rows(values_only=True):
            for cell in row:
                if cell is not None:
                    cells.append(str(cell))
                    if len(cells) >= 100:
                        break
            if len(cells) >= 100:
                break
        return " ".join(cells)
    except Exception:
        return None


def _extract_text_xls(file_bytes):
    """Collect up to 100 cell values from first sheet of an XLS. Returns str or None."""
    import xlrd
    try:
        wb = xlrd.open_workbook(file_contents=file_bytes)
        ws = wb.sheets()[0]
        cells = []
        for row_idx in range(ws.nrows):
            for col_idx in range(ws.ncols):
                val = ws.cell_value(row_idx, col_idx)
                if val is not None and str(val).strip():
                    cells.append(str(val))
                    if len(cells) >= 100:
                        break
            if len(cells) >= 100:
                break
        return " ".join(cells)
    except Exception:
        return None


def _score_text(text):
    """Returns (verification_status, verification_signal).

    Tier A: one strong phrase → "verified"
    Tier B: two or more weak phrases → "verified"
    No text: "unverified"
    Text present, no match: "rejected"
    """
    if not text or not text.strip():
        return "unverified", None
    text_lower = text.lower()
    # Find the longest matching Tier A phrase
    tier_a_matches = [phrase for phrase in TIER_A if phrase in text_lower]
    if tier_a_matches:
        # Return the longest match to prioritize more specific phrases
        longest = max(tier_a_matches, key=len)
        return "verified", longest
    tier_b_matches = [phrase for phrase in TIER_B if phrase in text_lower]
    if len(tier_b_matches) >= 2:
        return "verified", ", ".join(tier_b_matches[:2])
    return "rejected", None


def _normalize_url_text(file_url, link_text):
    """Normalize URL path + link_text for keyword scanning.

    Replaces URL separators with spaces so "foi-disclosure-log" → "foi disclosure log",
    making it easier to match against keyword lists.
    """
    import urllib.parse
    parsed = urllib.parse.urlparse(file_url)
    path = parsed.path
    # Replace common separators with spaces
    path = urllib.parse.unquote(path)
    for ch in ["-", "_", "."]:
        path = path.replace(ch, " ")
    combined = f"{path} {link_text or ''}".strip()
    return combined


def _verify_one(item, cache, step_dir):
    """Download and verify a single file. Returns None on download failure, result record on success."""
    file_url = item["file_url"]
    file_type = item["file_type"]

    try:
        cached_path = cache.get_file_path(file_url, step_dir)
        file_bytes = cached_path.read_bytes()
    except DownloadError:
        # Download failures are not marked as processed; they will be retried
        return None

    try:
        if file_type == "pdf":
            text = _extract_text_pdf(file_bytes)
        elif file_type == "xlsx":
            text = _extract_text_xlsx(file_bytes)
        elif file_type == "xls":
            text = _extract_text_xls(file_bytes)
        else:
            text = None

        status, signal = _score_text(text)

        # If content scoring is rejected or unverified, try URL/link_text as fallback
        if status in ("rejected", "unverified"):
            url_text = _normalize_url_text(file_url, item.get("link_text", ""))
            url_status, url_signal = _score_text(url_text)
            if url_status == "verified":
                status, signal = url_status, f"url:{url_signal}"

        return {**item, "verification_status": status, "verification_signal": signal}
    except Exception as e:
        append_error(step_dir, {
            "step": STEP_NAME,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "error_type": type(e).__name__,
            "error_message": str(e),
            "context": {"file_url": file_url},
        })
        # Extraction errors return unverified record (we know file exists, just can't read it)
        return {**item, "verification_status": "unverified", "verification_signal": None}


def process(input_data, step_dir, writer, verbose=False, max_workers=4):
    errors_path = Path(step_dir) / "errors.json"
    if not errors_path.exists():
        write_json(errors_path, [])

    cache = DisclosureFileCache(Path(step_dir) / "cache")

    pending = [
        item for item in input_data["results"]
        if not writer.is_processed(item["file_url"])
    ]

    if not pending:
        return

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_verify_one, item, cache, step_dir): item for item in pending}
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                writer.append([result])
                results.append(result)

    if verbose:
        status_counts = Counter(r["verification_status"] for r in results)
        print(f"\nVerification: {dict(status_counts)}")


def main():
    parser = argparse.ArgumentParser(description="Content-verify disclosure log files for FOI signals")
    add_common_args(parser)
    parser.add_argument("--workers", type=int, default=4)
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

    process(input_data, step_dir, writer, verbose=args.verbose, max_workers=args.workers)
    count = writer.finalize()
    write_status(step_dir, count)
    if args.verbose:
        print()
    print(f"Wrote {count} records to {output_path}")


if __name__ == "__main__":
    main()
