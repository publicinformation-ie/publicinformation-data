#!/usr/bin/env python3
"""Audit chapter/section trees for corruption, published and at current HEAD.

Read-only. Requires the gitignored step outputs, so run it in the main
checkout, not a worktree:

    cd pipelines/document_pipeline
    PYTHONPATH=".:../../src" python \
      experiments/2026-11-07-structure-corruption-audit/audit.py

Produces two tables:
  --published  audit the committed public/documents/**/meta.json chapter lists
  --head       run current detect_structure/process.py over the cached
               extract_pages sidecars and audit the resulting tree
"""
import argparse
from collections import Counter
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
PIPELINE = HERE.parent.parent          # pipelines/document_pipeline
sys.path.insert(0, str(PIPELINE))      # detect_structure imports `documents`, `lib`
sys.path.insert(0, str(PIPELINE.parent.parent / "src"))

import importlib.util                  # noqa: E402
_spec = importlib.util.spec_from_file_location(
    "ds", PIPELINE / "steps" / "detect_structure" / "process.py")
ds = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ds)

BARE = re.compile(r'^\s*[\d.)”"\'\-–—]*\s*$')

PUBLISHED = [
    ("sustainable-mobility-policy", "14 junk: '1'-'6' chapters+overviews, '\"' x3"),
    ("sustainable-mobility-policy-action-plan-2026-2030", "4 junk: '\"' chapters"),
    ("sustainable-mobility-policy-year-two-progress-report", "6 junk: '\"' x5 + 'Policy'"),
    ("sustainable-mobility-policy-year-three-progress-report", "4 junk: '\"' chapters"),
    ("sustainable-mobility-policy-action-plan-2022-2025", "junk '2040'; split titles"),
    ("all-island-strategic-rail-review-final-report", "junk '21'; 'Appendix C' split"),
    ("gda-cycle-network-plan-2022", "junk 'l' (map glyph)"),
    ("cycleconnects-summary-report", "'Network' x2 split; scrambled order"),
    ("nta-statement-of-strategy-2026-2030", "single 'Strategy' chapter"),
    ("emra-regional-spatial-and-economic-strategy", "15 dot-leader chapters; prose fragments"),
    ("national-cycle-network-plan", "'1 way', '73 blanket', page ranges 900-1107"),
    ("connecting-ireland-rural-mobility-plan", "duplicate '1 Introduction'; '15 min walk'"),
    ("gda-transport-strategy-2022-2042", "junk 'Servicing', 'Assessment'; missing 15, 18"),
    ("code-of-practice-recreational-craft", "missing 1.1; 'Emergency Procedures' 100pp"),
    ("ndp-sectoral-investment-plan-for-transport", "missing chapters; junk '3 and 5'"),
]


def pages(slug):
    base = PIPELINE / "steps" / "extract_pages" / "pages" / slug
    return [json.loads(p.read_text())
            for p in sorted(base.glob("*.json"))]


def audit_head(slug):
    P = pages(slug)
    if not P:
        return None
    pc = len(P)
    nodes, method, report = ds.detect_structure(P, None, pc)
    l1 = [n for n in nodes if n.level == 1]
    rate = report["match_rate"] if report else None
    levels = dict(sorted(Counter(n.level for n in nodes).items()))
    issues = []
    if len({n.level for n in nodes}) > 1 and not l1:
        issues.append("no-level-1")
    for n in nodes:
        if BARE.fullmatch(n.title) or len(n.title.strip()) < 2:
            issues.append(f"junk-title:{n.title!r}")
        elif not ds.is_heading_candidate(n.title):
            issues.append(f"not-candidate:{n.title[:28]!r}")
    issues += ds.validate_split(nodes, pc)
    return method, len(nodes), len(l1), issues, rate, levels


def audit_published(slug):
    meta = json.loads((Path("public") / "documents" / slug / "meta.json").read_text())
    hits = []
    for ch in meta.get("chapters", []):
        for n in [ch] + ch.get("sections", []):
            t = (n.get("title") or "").strip()
            if BARE.fullmatch(t) or len(t) < 2:
                hits.append(t)
    return meta.get("detection_method"), len(meta.get("chapters", [])), hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--published", action="store_true")
    ap.add_argument("--head", action="store_true")
    args = ap.parse_args()

    if args.published or not args.head:
        print("== published meta.json ==")
        for slug, note in PUBLISHED:
            method, chapters, hits = audit_published(slug)
            print(f"{slug[:52]:52} {method:9} ch={chapters:3} "
                  f"bare-junk={hits if hits else '-'}  | {note}")

    if args.head:
        print("\n== detect_structure at HEAD ==")
        for slug, _ in PUBLISHED:
            r = audit_head(slug)
            if r is None:
                print(f"{slug[:52]:52} (no sidecars)")
                continue
            method, nodes, l1, issues, rate, levels = r
            status = "OK " if not issues else "BAD"
            rate_s = "-" if rate is None else f"{rate:.3f}"
            print(f"{status} {slug[:52]:52} {method:9} n={nodes:3} "
                  f"l1={l1:3} issues={len(issues)} toc_rate={rate_s} levels={levels}")
            for i in issues[:6]:
                print(f"      {i}")


if __name__ == "__main__":
    main()
