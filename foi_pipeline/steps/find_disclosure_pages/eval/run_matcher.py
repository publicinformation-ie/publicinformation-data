#!/usr/bin/env python3
"""
Run find_disclosure_link over the cached fixtures and write matcher_output.json
in the same shape as the step's output.json, so evaluate.py can consume it.
Fully offline — no network.

Usage (from foi_pipeline/):
    uv run python steps/find_disclosure_pages/eval/run_matcher.py
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from steps.find_disclosure_pages.process import find_disclosure_link

STEP_DIR = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures"
OUT = Path(__file__).parent / "matcher_output.json"


def main():
    output = json.loads((STEP_DIR / "output.json").read_text())
    foi_by_id = {str(r["public_body_id"]): r for r in output["results"]}

    results = []
    for fixture in sorted(FIXTURES.glob("*.html")):
        pid = fixture.stem
        src = foi_by_id.get(pid)
        if src is None:
            continue
        foi_url = src["foi_page_url"]
        html = fixture.read_text(encoding="utf-8")
        match = find_disclosure_link(html, foi_url)
        if match:
            disclosure_url, sc = match
            confidence = "high" if sc >= 70 else "medium"
            method = "crawl"
        else:
            disclosure_url, confidence, method = foi_url, "none", "foi_page_fallback"
        results.append({
            "public_body_id": int(pid),
            "name": src.get("name", ""),
            "foi_page_url": foi_url,
            "disclosure_page_url": disclosure_url,
            "confidence": confidence,
            "source_method": method,
        })

    OUT.write_text(json.dumps({
        "metadata": {"step": "find_disclosure_pages_matcher_eval",
                     "completed_at": datetime.now(timezone.utc).isoformat()},
        "results": results,
    }, indent=2))
    print(f"Wrote {len(results)} matcher results to {OUT}")


if __name__ == "__main__":
    main()
