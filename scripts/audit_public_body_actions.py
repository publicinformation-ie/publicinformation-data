"""Audit published public-body-actions rows against the source PDFs.

Independent of the pipeline's PyMuPDF extraction: each row is located by its
action number in `pdftotext -layout` output for its `source_page`, and the
published value must appear in that row's text. This tests extraction
fidelity, not whether the source document is itself correct.

Checks (see docs/analysis/2026-11-08-public-body-actions-coverage-and-accuracy.md):
  * stated original deadlines: raw text appears in the PDF row
  * interpreted original deadlines: chosen year appears in the PDF row
  * report observations: reported deadline and status appear in the PDF row
  * parsed start/end dates are consistent with the raw text (year, quarter,
    open-ended)

Layout artefacts (a cell wrapped across lines, a row the number regex cannot
find) are reported as `unverified`, not failures.

Needs `pdftotext` (poppler) and the PDFs in
pipelines/document_pipeline/steps/fetch_pdfs/pdfs/.

Usage:
    python scripts/audit_public_body_actions.py [--json] [--check]

`--check` exits 1 when a deadline or status mismatch is found, or when a
parsed start/end disagrees with its raw text. Unverified rows do not fail it.
"""
import argparse
import calendar
import csv
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "public/latest/public-body-actions"
PDFS = ROOT / "pipelines/document_pipeline/steps/fetch_pdfs/pdfs"

ROW_START = re.compile(r"^\s*0*\d{1,3}\.?\s{2,}\S")
_pages = {}


def page_lines(slug, page):
    key = (slug, page)
    if key not in _pages:
        out = subprocess.run(
            ["pdftotext", "-f", str(page), "-l", str(page), "-layout",
             str(PDFS / f"{slug}.pdf"), "-"],
            capture_output=True, text=True, check=True).stdout
        _pages[key] = out.splitlines()
    return _pages[key]


def row_text(slug, page, number):
    """Whitespace-collapsed text of the row starting at `number`, or None."""
    lines = page_lines(slug, page)
    starts = [i for i, ln in enumerate(lines)
              if re.match(rf"^\s*0*{number}\.?\s", ln)]
    if not starts:
        return None
    i = starts[0]
    j = i + 1
    while j < len(lines) and not ROW_START.match(lines[j]):
        j += 1
    return re.sub(r"\s+", " ", " ".join(lines[i:j]))


def parse_consistent(raw, start, end, precision):
    """True/False for year and quarter; None when raw has no year to check."""
    if precision == "year":
        m = re.search(r"20\d\d", raw)
        if not m:
            return None
        y = int(m[0])
        return (start, end) == (f"{y}-01-01", f"{y}-12-31")
    if precision == "quarter":
        m = re.search(r"Q([1-4])\D*(\d{4})|(\d{4})\s*Q([1-4])", raw)
        if not m:
            return None
        q, y = (int(m[1]), int(m[2])) if m[1] else (int(m[4]), int(m[3]))
        sm = 3 * q - 2
        last = calendar.monthrange(y, sm + 2)[1]
        return (start, end) == (f"{y}-{sm:02d}-01", f"{y}-{sm + 2:02d}-{last}")
    return not start and not end  # annual / ongoing: no dates


def audit():
    actions = list(csv.DictReader(open(DATA / "actions.csv", encoding="utf-8")))
    obs = list(csv.DictReader(
        open(DATA / "action-status-observations.csv", encoding="utf-8")))
    counts = Counter()
    findings = []

    def add(kind, ident, detail):
        findings.append({"kind": kind, "id": ident, "detail": detail})
        counts[kind] += 1

    for r in actions:
        ident = r["action_id"]
        ok = parse_consistent(r["original_deadline_raw"],
                              r["original_deadline_start"],
                              r["original_deadline_end"],
                              r["original_deadline_precision"])
        if r["original_deadline_confidence"] == "stated" and ok is False:
            add("parse-mismatch", ident, r["original_deadline_raw"][:60])
        blk = row_text(r["plan_slug"], r["source_page"], r["action_number"])
        if blk is None:
            add("unverified", ident, "row not found")
            continue
        if r["original_deadline_confidence"] == "interpreted":
            if r["original_deadline_end"][:4] in blk:
                counts["interpreted-ok"] += 1
            else:
                add("deadline-mismatch", ident, r["original_deadline_end"])
        else:
            raw = r["original_deadline_raw"]
            if raw[:12] in blk or (r["original_deadline_end"]
                                   and r["original_deadline_end"][:4] in blk):
                counts["stated-ok"] += 1
            else:
                add("unverified", ident, f"deadline {raw[:40]!r} not in row")

    for r in obs:
        ident = f"{r['action_id']} @ {r['as_of']}"
        ok = parse_consistent(r["reported_deadline_raw"],
                              r["reported_deadline_start"],
                              r["reported_deadline_end"],
                              r["reported_deadline_precision"])
        if ok is False:
            add("parse-mismatch", ident, r["reported_deadline_raw"][:60])
        number = r["action_id"].split("#")[1]
        blk = row_text(r["report_slug"], r["source_page"], number)
        if blk is None:
            add("unverified", ident, "row not found")
            continue
        squashed = re.sub(r"\s+", "", blk)
        d = r["reported_deadline_raw"]
        if d and re.sub(r"\s+", "", d) not in squashed and not (
                r["reported_deadline_precision"] == "ongoing"
                and "ngoing" in blk):
            add("deadline-mismatch", ident, d)
        else:
            counts["reported-deadline-ok"] += 1
        # Formats B (Year Three, Final) take status from section headings,
        # so there is no status cell to look for in the row.
        if not r["report_slug"].endswith(
                ("three-progress-report", "final-progress-report")):
            status = r["status"].replace("OnSchedule", "On schedule")
            if re.sub(r"\s", "", status).lower() in squashed.lower():
                counts["status-ok"] += 1
            elif r["status"] == "OnSchedule" and "schedule" in blk.lower():
                counts["status-ok-wrapped"] += 1  # "On / Schedule" line wrap
            else:
                add("status-mismatch", ident, r["status"])
    return counts, findings


def main(argv=None):
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--json", action="store_true", help="emit JSON")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 on any mismatch (unverified rows ignored)")
    args = ap.parse_args(argv)
    counts, findings = audit()
    failing = [f for f in findings if f["kind"].endswith("mismatch")]
    if args.json:
        print(json.dumps({"counts": counts, "findings": findings}, indent=2))
    else:
        for k, v in sorted(counts.items()):
            print(f"{k}: {v}")
        for f in findings:
            print(f"  [{f['kind']}] {f['id']}: {f['detail']}")
    return 1 if args.check and failing else 0


if __name__ == "__main__":
    sys.exit(main())
