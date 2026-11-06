#!/usr/bin/env python3
import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from lib.cli_utils import add_common_args, filter_by_public_body
from lib.disclosure_link_utils import FILE_EXTENSIONS, find_file_links
from lib.file_utils import append_error, errors_outside_bodies, read_dirty_ids, read_json, write_json, write_status
from lib.http_utils import fetch

STEP_NAME = "fingerprint_disclosure_pages"


def _hash_links(links):
    raw = "\n".join(sorted(set(f["file_url"] for f in links)))
    return "sha256-" + hashlib.sha256(raw.encode()).hexdigest()


def _fetch_one(item):
    """Returns (body_id, name, url, links, exc)."""
    body_id = item["public_body_id"]
    url = item["disclosure_page_url"]
    name = item.get("name", "")
    try:
        ext = Path(urlparse(url).path).suffix.lower()
        if ext in FILE_EXTENSIONS:
            # Disclosure page IS a direct file — treat it as a single link
            links = [{"file_url": url, "file_type": FILE_EXTENSIONS[ext], "link_text": ""}]
            return body_id, name, url, links, None
        response = fetch("GET", url, allow_redirects=True)
        links = find_file_links(response.text, url)
        return body_id, name, url, links, None
    except Exception as e:
        return body_id, name, url, [], e


def process(input_data, step_dir, previous_hashes, preserved_hashes=None, force=False, max_workers=10):
    """Fetch all disclosure pages and compare file-link hashes to previous_hashes.

    Returns (results, dirty_ids) where:
      results  — list of output records (one per body)
      dirty_ids — set of public_body_ids whose hash changed or are new

    preserved_hashes: hashes loaded from previous output, used on fetch error to avoid
    losing the last known hash even when force=True clears effective_hashes for dirty-detection.
    """
    effective_hashes = {} if force else previous_hashes
    items = input_data["results"]
    results_by_id = {}
    dirty_ids = set()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_one, item): item for item in items}
        for future in as_completed(futures):
            body_id, name, url, links, exc = future.result()
            if exc is not None:
                append_error(step_dir, {
                    "step": STEP_NAME,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "context": {"url": url, "public_body_id": body_id, "name": name},
                })
                # Preserve previous hash on error; do not mark dirty
                results_by_id[body_id] = {
                    "public_body_id": body_id,
                    "name": name,
                    "disclosure_page_url": url,
                    "page_hash": (preserved_hashes or effective_hashes).get(body_id, _hash_links([])),
                    "file_count": 0,
                }
            else:
                new_hash = _hash_links(links)
                old_hash = effective_hashes.get(body_id)
                if old_hash is None or new_hash != old_hash:
                    dirty_ids.add(body_id)
                results_by_id[body_id] = {
                    "public_body_id": body_id,
                    "name": name,
                    "disclosure_page_url": url,
                    "page_hash": new_hash,
                    "file_count": len(links),
                }

    # Preserve order from input
    results = [results_by_id[item["public_body_id"]] for item in items if item["public_body_id"] in results_by_id]
    return results, dirty_ids


def main():
    parser = argparse.ArgumentParser(description="Fingerprint disclosure pages to detect changes")
    add_common_args(parser)
    parser.add_argument("--workers", type=int, default=10)
    args = parser.parse_args()

    output_path = Path(args.output)
    # Same as steps/<step>/ in production (the runner passes steps/<step>/output.json)
    step_dir = output_path.parent
    dirty_path = step_dir / "dirty_ids.json"
    errors_path = step_dir / "errors.json"

    try:
        input_data = read_json(args.input)
    except Exception as e:
        print(f"Fatal: could not read input: {e}", file=sys.stderr)
        sys.exit(1)
    input_data = filter_by_public_body(input_data, args.public_body)
    if args.public_body is not None and not input_data.get("results"):
        print(f"No input record for public_body_id={args.public_body}", file=sys.stderr)
        sys.exit(0)

    # Always load for error-preservation, even on force runs
    preserved_hashes = {}
    previous_records = []
    if output_path.exists():
        try:
            prev = read_json(output_path)
            previous_records = prev.get("results", [])
            for r in previous_records:
                if "public_body_id" in r and "page_hash" in r:
                    preserved_hashes[r["public_body_id"]] = r["page_hash"]
        except (json.JSONDecodeError, KeyError):
            if args.public_body is not None:
                # Scoped run would overwrite every other body's records/hashes
                print(f"Fatal: could not read previous output {output_path}; "
                      "refusing scoped run (fix or delete it, or run unscoped)",
                      file=sys.stderr)
                sys.exit(1)
            # Unscoped: first run or corrupt file — treat as empty

    # Pending dirty IDs from earlier runs (drained only by find_disclosure_files).
    # Read before writing anything; raises ValueError if corrupt.
    previous_dirty = read_dirty_ids(dirty_path) if dirty_path.exists() else set()

    # Scoped runs keep other bodies' errors; unscoped runs reset them
    if args.public_body is not None:
        write_json(errors_path, errors_outside_bodies(errors_path, {args.public_body}))
    else:
        write_json(errors_path, [])

    # previous_hashes for dirty-detection (empty on force)
    previous_hashes = {} if args.force else preserved_hashes

    results, dirty_ids = process(
        input_data, step_dir, previous_hashes,
        preserved_hashes=preserved_hashes,
        force=args.force, max_workers=args.workers
    )

    if args.public_body is not None:
        new_by_id = {r["public_body_id"]: r for r in results}
        merged = []
        for r in previous_records:
            merged.append(new_by_id.pop(r.get("public_body_id"), r))
        merged.extend(new_by_id.values())
        results = merged

    write_json(output_path, {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
        "results": results,
    })
    pending = previous_dirty | dirty_ids
    write_json(dirty_path, sorted(pending))
    write_status(step_dir, len(results))
    print(f"Wrote {len(results)} records ({len(dirty_ids)} dirty this run, {len(pending)} pending total)")


if __name__ == "__main__":
    main()
