#!/usr/bin/env python3
"""
Cache HTML for the offline eval loop:
  - fixtures/{id}.html            the FOI page (matcher input)
  - fixtures/{id}_candidate.html  the winning candidate page, only for bodies
                                   this step upgraded (has source_page_url)

Run rarely (only to refresh the corpus). Re-running skips already-cached
files, so the iteration loop stays offline and deterministic.

Usage (from foi_pipeline/):
    uv run python steps/find_foi_email_pages/eval/capture_fixtures.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from lib.http_utils import fetch, is_safe_url

STEP_DIR = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures"


def _grab(url, dest):
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
    output = json.loads((STEP_DIR / "output.json").read_text())
    foi_ok = cand_ok = 0
    for r in output["results"]:
        pid = r["public_body_id"]
        foi_url = r.get("foi_page_url")
        if not foi_url:
            continue  # e.g. records that never had a foi_page_url upstream
        foi_result = _grab(foi_url, FIXTURES / f"{pid}.html")
        if foi_result:
            foi_ok += 1
        cand_result = None
        source_url = r.get("source_page_url")
        if source_url:
            cand_result = _grab(source_url, FIXTURES / f"{pid}_candidate.html")
            if cand_result:
                cand_ok += 1
        status = "ERROR" if foi_result is False or cand_result is False else "done"
        print(f"  [{pid}] {status}")
    print(f"\nCaptured {foi_ok} FOI pages, {cand_ok} candidate pages")


if __name__ == "__main__":
    main()
