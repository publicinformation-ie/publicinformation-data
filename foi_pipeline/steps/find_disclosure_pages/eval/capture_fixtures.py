#!/usr/bin/env python3
"""
Cache HTML for the offline eval loop:
  - fixtures/{id}.html               the FOI page (matcher input)
  - fixtures/destinations/{id}.html  the current candidate disclosure page
                                     (read by the Task 3 labeler for ground truth)

Run rarely (only to refresh the corpus). Re-running skips already-cached files,
so the iteration loop stays offline and deterministic.

Usage (from foi_pipeline/):
    uv run python steps/find_disclosure_pages/eval/capture_fixtures.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scripts.http_utils import fetch, is_safe_url

STEP_DIR = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures"
DESTINATIONS = FIXTURES / "destinations"


def _grab(url, dest):
    """Cache one URL. Returns True if newly fetched, None if already cached,
    False on skip/error. Non-HTML responses are stubbed so the labeler can read
    the URL + content-type without parsing binary (e.g. PDF disclosure logs)."""
    if dest.exists():
        return None
    if not is_safe_url(url):
        print(f"    SKIP unsafe {url}")
        return False
    try:
        resp = fetch("GET", url, allow_redirects=True)
        ctype = resp.headers.get("content-type", "")
        if "html" not in ctype.lower():
            dest.write_text(f"<!-- non-HTML content ({ctype}) at {url} -->", encoding="utf-8")
        else:
            dest.write_text(resp.text, encoding="utf-8")
        return True
    except Exception as e:
        print(f"    FAIL {url}: {type(e).__name__}: {e}")
        return False


def main():
    FIXTURES.mkdir(exist_ok=True)
    DESTINATIONS.mkdir(exist_ok=True)
    output = json.loads((STEP_DIR / "output.json").read_text())
    foi_ok = dest_ok = 0
    for r in output["results"]:
        pid = r["public_body_id"]
        foi_url = r["foi_page_url"]
        cand_url = r.get("disclosure_page_url", foi_url)
        if _grab(foi_url, FIXTURES / f"{pid}.html"):
            foi_ok += 1
        # Only fetch the candidate when it differs from the FOI page.
        if cand_url.rstrip("/") != foi_url.rstrip("/"):
            if _grab(cand_url, DESTINATIONS / f"{pid}.html"):
                dest_ok += 1
        print(f"  [{pid}] done")
    print(f"\nCaptured {foi_ok} FOI pages, {dest_ok} candidate destinations")


if __name__ == "__main__":
    main()
