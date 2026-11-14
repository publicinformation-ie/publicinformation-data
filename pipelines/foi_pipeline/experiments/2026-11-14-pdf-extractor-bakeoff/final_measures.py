"""Task 12 measurements: read-only over existing step outputs (no pipeline reruns).

Usage: uv run python experiments/2026-11-14-pdf-extractor-bakeoff/final_measures.py --before <snapshot> --out <md>
Writes: gate blast radius, no-ref-no-dates count, files >=20%/>=50% errors, per-body table.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cause_ledger import classify_error  # noqa: E402

STEPS = Path(__file__).resolve().parents[2] / "steps"
CANON = "extract_disclosures_canonicalize_rows"


def load(p):
    d = json.loads(Path(p).read_text())
    return d.get("results", d) if isinstance(d, dict) else d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    br, be = load(a.before / CANON / "output.json"), load(a.before / CANON / "errors.json")
    ar, ae = load(STEPS / CANON / "output.json"), load(STEPS / CANON / "errors.json")
    bg = {e["context"]["file_url"] for e in load(a.before / "assess_table_structure/errors.json")}
    agl = load(STEPS / "assess_table_structure/errors.json")
    ag = {e["context"]["file_url"] for e in agl}
    brc, bec = Counter(r["file_url"] for r in br), Counter(e["context"]["file_url"] for e in be)
    arc, aec = Counter(r["file_url"] for r in ar), Counter(e["context"]["file_url"] for e in ae)
    new = ag - bg
    L = ["# Task 12 final measures (read-only)", ""]
    L += [f"Records {len(br)} -> {len(ar)} ({len(br)-len(ar)} lost, {(len(br)-len(ar))/len(br):.1%}); "
          f"errors {len(be)} -> {len(ae)}.", ""]
    L += ["## Gate blast radius", "",
          f"- files gated before {len(bg)}, now {len(ag)}; newly gated {len(new)}; gated files still emitting records: "
          f"{sum(1 for u in ag if arc[u])} ({sum(arc[u] for u in ag)} records)",
          f"- records lost from newly gated files: {sum(brc[u]-arc[u] for u in new)}; errors those files had before: {sum(bec[u] for u in new)}",
          f"- newly gated with records before and 0 errors: {sum(1 for u in new if brc[u] and not bec[u])} files, {sum(brc[u] for u in new if not bec[u])} records",
          f"- newly gated with error rate < 5% before: {sum(1 for u in new if brc[u] and bec[u]/(brc[u]+bec[u]) < 0.05)}",
          f"- newly gated with >= 40 records and <= 3 errors before: {sum(1 for u in new if brc[u] >= 40 and bec[u] <= 3)}", ""]
    nrd = [r for r in ar if not r.get("foi_reference_id") and not r.get("date_received") and not r.get("decision_date")]
    L += ["## Records with no reference and no dates", "", f"{len(nrd)} of {len(ar)} (spec baseline 3,354 of 59,600)", "",
          "Top bodies: " + ", ".join(f"{b}: {n}" for b, n in Counter(r["public_body_id"] for r in nrd).most_common(8)), ""]
    for th in (0.2, 0.5):
        fs = [u for u in set(arc) | set(aec) if u and aec[u] / (arc[u] + aec[u]) >= th]
        L += [f"## Files with errors on >= {int(th*100)}% of rows (errors / (records + errors))", "",
              f"{len(fs)} files, {sum(aec[u] for u in fs)} errors, {sum(arc[u] for u in fs)} surviving records; "
              f"before: {sum(1 for u in set(brc)|set(bec) if u and bec[u]/(brc[u]+bec[u]) >= th)} files.",
              f"Docling scope (gated {len(ag)} + these not gated {len([u for u in fs if u not in ag])}) = "
              f"{len(ag | set(fs))}" if th == 0.2 else "", ""]
        if th == 0.2:
            cls: dict = {}
            for e in ae:
                cls.setdefault(e["context"]["file_url"], Counter())[classify_error(e)] += 1
            L += ["| body | records | errors | rate | extractor | dominant class | file |", "|---|---|---|---|---|---|---|"]
            ext = {}
            for r in load(STEPS / "assess_table_structure/output.json"):
                ext[r.get("file_url")] = r.get("pdf_extractor")
            body = {r["file_url"]: r["public_body_id"] for r in ar}
            body.update({e["context"]["file_url"]: e["context"]["public_body_id"] for e in ae})
            for u in sorted(fs, key=lambda u: -aec[u]):
                c = cls[u].most_common(1)[0][0]
                L.append(f"| {body[u]} | {arc[u]} | {aec[u]} | {aec[u]/(arc[u]+aec[u]):.0%} | {ext.get(u)} | {c} | {u} |")
            L.append("")
    ki = Counter(r["file_url"] for r in ar if r.get("known_issues"))
    L += ["## Alternative definition: share of surviving records carrying known_issues", ""]
    for th in (0.2, 0.5):
        fs = [u for u in arc if ki[u] / arc[u] >= th]
        L.append(f"- >= {int(th*100)}%: {len(fs)} files, {sum(arc[u] for u in fs)} records, {sum(aec[u] for u in fs)} errors")
    L += ["", f"Records with known_issues: {sum(ki.values())}; canonicalize errors: {len(ae)} (an error does not always drop its row).", ""]
    bb, ab = Counter(r["public_body_id"] for r in br), Counter(r["public_body_id"] for r in ar)
    bx = Counter(e["context"]["public_body_id"] for e in be)
    ax = Counter(e["context"]["public_body_id"] for e in ae)
    rows = [(b, bx[b], ax[b], bb[b], ab[b]) for b in set(bb) | set(ab) | set(bx) | set(ax)
            if (bx[b], bb[b]) != (ax[b], ab[b])]
    L += ["## Per body: errors and records, before -> after (all bodies that changed)", "",
          "| body | errors before | errors after | records before | records after |", "|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: -(abs(r[1]-r[2]) + abs(r[3]-r[4]))):
        L.append("| %s | %d | %d | %d | %d |" % r)
    a.out.write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
