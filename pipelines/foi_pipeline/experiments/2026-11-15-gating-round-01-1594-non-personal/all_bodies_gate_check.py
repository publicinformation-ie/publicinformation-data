"""All-bodies blast-radius check: widen value_kinds._is_date to the parser's D-Mon-YY pattern.

Scores every PDF item in steps/transform_disclosure_files/output.json (read only)
with the real override role maps, with and without the widened `_is_date`, and
classifies each file. Newly passing files are run through the real downstream
chain (experiments.gating.downstream) both ways and compared with what is
published. Nothing under src/ or steps/ is written; no network, no model calls.

Run from pipelines/foi_pipeline:
  uv run python experiments/2026-11-15-gating-round-01-1594-non-personal/all_bodies_gate_check.py
"""
import json
import re
import sys
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

FOI = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FOI))

from experiments.gating.downstream import ASSESS, default_gate, run_downstream, transform_index  # noqa: E402
from experiments.gating.paths import SCRATCH, STEPS  # noqa: E402
from experiments.gating.scope import file_stats  # noqa: E402
from lib import value_kinds  # noqa: E402
from steps.assess_table_structure.process import _load_override_role_maps  # noqa: E402
from steps.extract_disclosures_normalize_rows.process import _DATE_PATTERNS  # noqa: E402

OUT = Path(__file__).with_name("all_bodies_gate_check.json")
PARSER_RX: re.Pattern = _DATE_PATTERNS[1][0]  # D-Mon-YY / D-Mon-YYYY, exactly the parser's
_MONTH = re.compile(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", re.I)


@contextmanager
def widened_date():
    orig = value_kinds._is_date
    value_kinds._is_date = lambda text: bool(PARSER_RX.match(text)) or orig(text)
    try:
        yield
    finally:
        value_kinds._is_date = orig


def widened_gate(rows, role_map):
    with widened_date():
        return default_gate(rows, role_map)


def classify(a: list[str], b: list[str]) -> str:
    if a == b:
        return "same"
    if not b:
        return "newly_pass"
    if not a:
        return "newly_fail"
    return "changed_fail"


def date_cell_stats(rows: list[list]) -> dict:
    """Cells that look like D-Mon-YY dates but the parser pattern rejects.
    garbled: matches once whitespace is removed ("2 7 - J a n -20").
    other: has digits plus a month name but matches neither way."""
    garbled, other, ok = [], [], 0
    for row in rows:
        for c in row:
            if not isinstance(c, str):
                continue
            t = c.strip()
            if PARSER_RX.match(t):
                ok += 1
            elif PARSER_RX.match(re.sub(r"\s+", "", t)):
                garbled.append(t)
            elif _MONTH.search(t) and re.search(r"\d", t) and re.search(r"-\s*\d{2,4}\s*$", t):
                other.append(t)
    return {"parser_match": ok, "garbled": len(garbled), "other_unmatched": len(other),
            "examples": (garbled + other)[:5]}


def main() -> int:
    items = [it for it in transform_index(STEPS).values()
             if it.get("file_type") == "pdf" and it.get("rows")]
    role_maps = _load_override_role_maps(STEPS / ASSESS)
    classes: dict[str, list[dict]] = {k: [] for k in ("same", "newly_pass", "newly_fail", "changed_fail")}
    for it in items:
        url, rows = it["file_url"], it["rows"]
        _, a = default_gate(rows, role_maps.get(url))
        _, b = widened_gate(rows, role_maps.get(url))
        classes[classify(a, b)].append({"body": it.get("public_body_id"), "file_url": url,
                                        "before": a, "after": b})

    stats = file_stats(STEPS)
    by_url = {it["file_url"]: it for it in items}
    new = classes["newly_pass"]
    if new:
        batch = [by_url[e["file_url"]] for e in new]
        before = run_downstream(batch, "allbodies_without")
        after = run_downstream(batch, "allbodies_with", gate=widened_gate)
        for e in new:
            u = e["file_url"]
            s = stats.get(u)
            e["downstream_without"] = {"records": before[u].records, "errors": before[u].errors,
                                       "gate_pass": before[u].gate_pass}
            e["downstream_with"] = {"records": after[u].records, "errors": after[u].errors,
                                    "gate_pass": after[u].gate_pass,
                                    "error_classes": after[u].error_classes}
            e["published"] = ({"gated": s.gated, "records": s.records, "errors": s.errors}
                              if s else None)
            e["date_cells"] = date_cell_stats(by_url[u]["rows"])

    result = {"scanned_pdf_files": len(items),
              "counts": {k: len(v) for k, v in classes.items()},
              "files": classes}
    OUT.write_text(json.dumps(result, indent=2) + "\n")

    print(f"scanned {len(items)} PDF files: " + ", ".join(f"{k}={len(v)}" for k, v in classes.items()))
    for e in classes["newly_fail"] + classes["changed_fail"]:
        print("!!", e["body"], e["file_url"][-50:], e["before"], "->", e["after"])
    print(f"{'body':>5} {'file':<34} {'pub':>9} {'before':>9} {'after':>11} {'garbled':>7} {'other':>5}")
    for e in new:
        p, w, a, d = e["published"], e["downstream_without"], e["downstream_with"], e["date_cells"]
        pub = f"{p['records']}/{p['errors']}" if p else "-"
        print(f"{e['body']!s:>5} {e['file_url'][-34:]:<34} {pub:>9} "
              f"{w['records']}/{w['errors']:>3} {a['records']}/{a['errors']:>3} "
              f"{d['garbled']:>7} {d['other_unmatched']:>5}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
