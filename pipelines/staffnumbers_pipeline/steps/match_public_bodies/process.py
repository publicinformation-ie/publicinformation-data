#!/usr/bin/env python3
"""Resolve each source row to a canonical public body, deterministically.

Only two things auto-match, and both are exact:
  * `exact`: the source name and a canonical name are identical after
    normalisation (case, accents, '&'/'and', 'the', punctuation, parentheticals);
  * `rule`: a local authority label such as 'County Council - Leitrim' rewritten
    to 'Leitrim County Council' and then matched exactly.

Anything else stays unmatched. There is deliberately no fuzzy threshold: a
near-miss like 'Corporate Enforcement Agency' vs '... Authority' is a human
decision, made in apply_overrides/override.json. The closest candidates are
written to match_log.json to make that review quick.
"""
import argparse
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from lib.file_utils import append_errors, read_json, write_json, write_status

STEP_NAME = "match_public_bodies"
CANDIDATES_PATH = "pipelines/foi_pipeline/steps/find_public_bodies/output.json"
SUGGESTION_FLOOR = 0.6

_LA_RE = re.compile(r"^(city\s*(?:&|and)\s*county|county|city)\s+council\s*-\s*(.+)$", re.IGNORECASE)


def match_key(name: str) -> str:
    text = unicodedata.normalize("NFKD", name)
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r"\(.*?\)", " ", text).replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\bthe\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def local_authority_name(label: str):
    """'County Council - Leitrim' -> 'Leitrim County Council'; None if the
    label is not in the source's inverted local-authority form."""
    m = _LA_RE.match(label.strip())
    if not m:
        return None
    kind = " ".join(m.group(1).lower().replace("&", "and").split())
    place = m.group(2).strip()
    return {"county": f"{place} County Council",
            "city": f"{place} City Council",
            "city and county": f"{place} City and County Council"}[kind]


def build_index(candidates: list) -> dict:
    index = defaultdict(list)
    for body in candidates:
        index[match_key(body["name"])].append(body["public_body_id"])
    return index


def resolve(name: str, index: dict):
    """Return (public_body_id | None, status, method). status is 'exact',
    'rule', 'ambiguous' (several canonical bodies share the key) or 'unmatched'."""
    for candidate, method in ((name, "exact_name"), (local_authority_name(name), "local_authority_rule")):
        if candidate is None:
            continue
        ids = index.get(match_key(candidate), [])
        if len(ids) == 1:
            return ids[0], ("exact" if method == "exact_name" else "rule"), method
        if len(ids) > 1:
            return None, "ambiguous", method
    return None, "unmatched", None


def suggestions(name: str, candidates: list, limit=3) -> list:
    query = match_key(local_authority_name(name) or name)
    scored = sorted(
        ((SequenceMatcher(None, query, match_key(b["name"])).ratio(), b) for b in candidates),
        key=lambda t: t[0], reverse=True)[:limit]
    return [{"public_body_id": b["public_body_id"], "name": b["name"], "score": round(s, 3)}
            for s, b in scored if s >= SUGGESTION_FLOOR]


def process(records: list, candidates: list):
    index = build_index(candidates)
    out, log = [], []
    for rec in records:
        body_id, status, method = resolve(rec["source_name"], index)
        out.append({**rec, "public_body_id": body_id, "match_status": status, "match_method": method})
        if body_id is None:
            log.append({"source_key": rec["source_key"], "source_name": rec["source_name"],
                        "status": status, "suggestions": suggestions(rec["source_name"], candidates)})
    return out, log


def main():
    parser = argparse.ArgumentParser(description="Match PER staff-number rows to canonical public bodies")
    parser.add_argument("--input", required=True, help="fetch_staff_numbers output.json")
    parser.add_argument("--output", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--public-body", type=int, default=None, dest="public_body")
    parser.add_argument("--candidates", default=None,
                        help=f"find_public_bodies output.json (default <repo_root>/{CANDIDATES_PATH})")
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    repo_root = step_dir.parent.parent.parent.parent
    output_path = Path(args.output) if args.output else step_dir / "output.json"
    candidates_path = Path(args.candidates) if args.candidates else repo_root / CANDIDATES_PATH

    if not args.force and output_path.exists():
        print(f"Output exists at {output_path}, skipping (use --force to re-run)")
        return
    try:
        data = read_json(args.input)
        candidates = read_json(candidates_path)["public_bodies"]
    except Exception as e:
        print(f"Fatal: {e}", file=sys.stderr)
        sys.exit(1)

    errors_path = step_dir / "errors.json"
    if errors_path.exists():
        errors_path.unlink()
    results, log = process(data["results"], candidates)
    write_json(step_dir / "match_log.json", log)
    write_json(output_path, {
        "metadata": {**data["metadata"], "step": STEP_NAME,
                     "completed_at": datetime.now(timezone.utc).isoformat()},
        "results": results,
    })
    write_status(step_dir, len(results))
    ambiguous = [e for e in log if e["status"] == "ambiguous"]
    append_errors(step_dir, [{
        "step": STEP_NAME, "error_type": "ambiguous_match",
        "error_message": "several canonical bodies share this normalised name",
        "context": {"source_key": e["source_key"]}} for e in ambiguous])
    print(f"Matched {len(results) - len(log)}/{len(results)} deterministically; "
          f"{len(log)} left for review ({len(ambiguous)} ambiguous)")


if __name__ == "__main__":
    main()
