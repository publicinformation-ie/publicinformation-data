#!/usr/bin/env python3
"""Before/after tables for the structure-based PDF extractor change.

    before_after.py --before DIR --after DIR --bodies 1655,1112 [--out FILE]

DIR holds <step>/output.json and <step>/errors.json for transform_disclosure_files,
assess_table_structure (after only), extract_disclosures_canonicalize_rows. Every
table is restricted to --bodies so a partial run is never read as an all-bodies
result. Without --bodies, all bodies found in --after canonicalize_rows are used.
"""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

TRANSFORM = "transform_disclosure_files"
ASSESS = "assess_table_structure"
CANON = "extract_disclosures_canonicalize_rows"


def _load(d, step, name):
    p = Path(d) / step / f"{name}.json"
    if not p.exists() or p.stat().st_size == 0:
        return []
    data = json.loads(p.read_text())
    return data["results"] if isinstance(data, dict) and name == "output" else data


def _bid(rec):
    v = rec.get("public_body_id")
    if v is None:
        v = (rec.get("context") or {}).get("public_body_id")
    return None if v is None else str(v)


def _errors(d):
    out = []
    for step in (TRANSFORM, ASSESS, CANON):
        out += _load(d, step, "errors")
    return out


def _file_extractors(d, bodies):
    """file_url -> (body, extractor) for PDF records in transform output."""
    m = {}
    for r in _load(d, TRANSFORM, "output"):
        if _bid(r) in bodies and r.get("file_type") == "pdf":
            m.setdefault(r["file_url"], (_bid(r), r.get("pdf_extractor")))
    return m


def _table(title, header, rows):
    lines = [f"### {title}", "", "| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines) + "\n"


def build(before, after, bodies):
    out = []
    eb = Counter(e.get("error_type") for e in _errors(before) if _bid(e) in bodies)
    ea = Counter(e.get("error_type") for e in _errors(after) if _bid(e) in bodies)
    out.append(_table("Errors per error_type", ["error_type", "before", "after", "delta"],
                      [(k, eb[k], ea[k], ea[k] - eb[k]) for k in sorted(set(eb) | set(ea), key=str)]))

    rb = Counter(_bid(r) for r in _load(before, CANON, "output") if _bid(r) in bodies)
    ra = Counter(_bid(r) for r in _load(after, CANON, "output") if _bid(r) in bodies)
    out.append(_table("Records per public_body_id (canonicalize_rows)",
                      ["public_body_id", "before", "after", "delta"],
                      [(k, rb[k], ra[k], ra[k] - rb[k]) for k in sorted(set(rb) | set(ra), key=lambda x: int(x))]
                      + [("TOTAL", sum(rb.values()), sum(ra.values()), sum(ra.values()) - sum(rb.values()))]))

    fb, fa = _file_extractors(before, bodies), _file_extractors(after, bodies)
    pb = Counter(v[1] for v in fb.values())
    pa = Counter(v[1] for v in fa.values())
    out.append(_table("PDF files per pdf_extractor", ["pdf_extractor", "before", "after", "delta"],
                      [(k, pb[k], pa[k], pa[k] - pb[k]) for k in sorted(set(pb) | set(pa), key=str)]))

    moved = sorted((u, fb.get(u, (None, "absent"))[1], fa[u][1], fa[u][0]) for u in fa
                   if fb.get(u, (None, "absent"))[1] != fa[u][1])
    trans = Counter((b, a) for _, b, a, _ in moved)
    out.append(_table("Files that changed extractor (transitions)", ["before", "after", "files"],
                      [(str(b), str(a), n) for (b, a), n in sorted(trans.items(), key=str)]))
    out.append(_table("Files that changed extractor (list)", ["public_body_id", "before", "after", "file_url"],
                      [(bid, b, a, u) for u, b, a, bid in moved]))

    unrel = defaultdict(list)
    for e in _load(after, ASSESS, "errors"):
        if e.get("error_type") == "TableStructureUnreliable" and _bid(e) in bodies:
            unrel[_bid(e)].append(e["context"]["file_url"])
    out.append(_table("TableStructureUnreliable per body", ["public_body_id", "files"],
                      [(b, len(v)) for b, v in sorted(unrel.items(), key=lambda x: int(x[0]))]
                      + [("TOTAL", sum(len(v) for v in unrel.values()))]))
    return "\n".join(out), len(fa)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--bodies", help="comma-separated public_body_ids in the run")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.bodies:
        bodies = {b.strip() for b in a.bodies.split(",") if b.strip()}
    else:
        bodies = {_bid(r) for r in _load(a.after, CANON, "output")}
    text, nfiles = build(a.before, a.after, bodies)
    head = f"Coverage: {len(bodies)} bodies ({', '.join(sorted(bodies, key=int))}); {nfiles} PDF files. NOT an all-bodies result.\n\n"
    print(head + text)
    if a.out:
        Path(a.out).write_text(head + text)


if __name__ == "__main__":
    main()
