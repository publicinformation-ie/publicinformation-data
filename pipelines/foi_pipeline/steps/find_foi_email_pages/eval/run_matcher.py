#!/usr/bin/env python3
"""
Run the find_foi_email_pages scorer/extractor over cached fixtures and write
matcher_output.json in the same shape as the step's output.json, so
evaluate.py can consume it. Fully offline — no network.

Evaluates only the single highest-scoring candidate per body (the one
capture_fixtures.py caches), not the live step's up-to-3-candidate fallback.

Usage (from foi_pipeline/):
    uv run python steps/find_foi_email_pages/eval/run_matcher.py
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from steps.find_foi_email_pages.process import find_candidate_links, _confidence
from steps.get_foi_emails.process import extract_emails, pick_foi_email

STEP_DIR = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures"
OUT = Path(__file__).parent / "matcher_output.json"


def _matcher_result_for_fixture(foi_html, foi_url, candidate_html):
    """Pure function: given the FOI page HTML and (maybe) the winning
    candidate's HTML, return the upgrade outcome as a dict with foi_email,
    email_status, and (if upgraded) confidence + source_page_url."""
    candidates = find_candidate_links(foi_html, foi_url)
    if not candidates or candidate_html is None:
        return {"foi_email": None, "email_status": "not_found"}

    candidate_url, link_score = candidates[0]
    emails = extract_emails(candidate_html)
    email, email_status = pick_foi_email(emails)
    if email_status != "found":
        return {"foi_email": None, "email_status": "not_found"}

    return {
        "foi_email": email,
        "email_status": "found",
        "confidence": _confidence(link_score, email),
        "source_page_url": candidate_url,
    }


def main():
    output = json.loads((STEP_DIR / "output.json").read_text())
    foi_by_id = {str(r["public_body_id"]): r for r in output["results"]}

    results = []
    skipped = 0
    for fixture in sorted(FIXTURES.glob("*.html")):
        if fixture.stem.endswith("_candidate"):
            continue
        pid = fixture.stem
        src = foi_by_id.get(pid)
        if src is None:
            skipped += 1
            continue
        foi_url = src["foi_page_url"]
        foi_html = fixture.read_text(encoding="utf-8")
        candidate_fixture = FIXTURES / f"{pid}_candidate.html"
        candidate_html = candidate_fixture.read_text(encoding="utf-8") if candidate_fixture.exists() else None

        outcome = _matcher_result_for_fixture(foi_html, foi_url, candidate_html)
        results.append({
            "public_body_id": int(pid),
            "name": src.get("name", ""),
            "foi_page_url": foi_url,
            **outcome,
        })

    OUT.write_text(json.dumps({
        "metadata": {"step": "find_foi_email_pages_matcher_eval",
                     "completed_at": datetime.now(timezone.utc).isoformat()},
        "results": results,
    }, indent=2))
    msg = f"Wrote {len(results)} matcher results to {OUT}"
    if skipped:
        msg += f" ({skipped} fixtures skipped — not found in output.json)"
    print(msg)


if __name__ == "__main__":
    main()
