#!/usr/bin/env python3
"""Calibrate max_role_contamination / min_anchored_row_share with a body-id holdout.

Reads existing step outputs only (no pipeline reruns). Run from pipelines/foi_pipeline:
  uv run python experiments/2026-11-14-pdf-extractor-bakeoff/role_calibration.py
"""
import json
import sys
from itertools import product
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parents[3] / "src"))
from bakeoff import gold_accuracy  # noqa: E402
from cause_ledger import per_file_cross_role_rate  # noqa: E402
from lib.table_structure import score_table  # noqa: E402

STEPS = HERE.parents[1] / "steps"
BAD_RATE = 0.20
CONTAM = [0.02, 0.05, 0.10, 0.15, 0.20, 0.30]
ANCHOR = [0.80, 0.85, 0.90, 0.95]


def flagged(f, c, a):
    """Withheld if worst contamination exceeds c or anchored share is below a.
    Files with contamination None (no measurable column) are judged on anchors only."""
    if f["worst"] is not None and f["worst"] > c:
        return True
    return f["anchor"] is not None and f["anchor"] < a


def confusion(files, c, a):
    bad = [f for f in files if f["bad"]]
    good = [f for f in files if not f["bad"]]
    tp = sum(flagged(f, c, a) for f in bad)
    fp = sum(flagged(f, c, a) for f in good)
    rec = tp / len(bad) if bad else float("nan")
    fpr = fp / len(good) if good else float("nan")
    wh = sum(f["records"] for f in good if flagged(f, c, a))
    return dict(tp=tp, fn=len(bad) - tp, fp=fp, tn=len(good) - fp, recall=rec, fpr=fpr,
                withheld=wh, good_records=sum(f["records"] for f in good), nbad=len(bad), ngood=len(good))


def main():
    rates = per_file_cross_role_rate(STEPS)
    recs = json.loads((STEPS / "transform_disclosure_files/output.json").read_text())["results"]
    files, unmapped, allnone, nonpdf = [], 0, 0, 0
    for r in recs:
        rows = r.get("rows")
        if r.get("file_type") != "pdf" or not rows:
            nonpdf += 1
            continue
        sc = score_table(rows)
        if sc.roles_unmapped:
            unmapped += 1
            continue
        if sc.worst_role_contamination is None:
            allnone += 1
        rate = rates.get(r["file_url"], 0.0)
        files.append(dict(url=r["file_url"], body=r["public_body_id"], worst=sc.worst_role_contamination,
                          anchor=sc.anchored_row_share, rate=rate, bad=rate >= BAD_RATE,
                          records=sc.n_rows))
    # all-None contamination is a distinct state: reported, excluded from the grid
    grid_files = [f for f in files if f["worst"] is not None]
    even = [f for f in grid_files if f["body"] % 2 == 0]
    odd = [f for f in grid_files if f["body"] % 2 == 1]

    rows = []
    for c, a in product(CONTAM, ANCHOR):
        e = confusion(even, c, a)
        rows.append((c, a, e))
    ok = [(c, a, e) for c, a, e in rows if e["recall"] >= 0.8 and e["fpr"] <= 0.05]
    if ok:
        # loosest = fewest files flagged overall; ties -> larger contamination cap, lower anchor floor
        pick = min(ok, key=lambda t: (t[2]["tp"] + t[2]["fp"], -t[0], t[1]))
        how = "loosest pair with even-id recall >= 0.80 and good-file FPR <= 0.05"
    else:
        pick = max(rows, key=lambda t: (t[2]["recall"] - t[2]["fpr"], t[0], -t[1]))
        how = "NO pair met recall >= 0.80 and FPR <= 0.05 on even ids; chose highest Youden J"
    c, a, e = pick
    o = confusion(odd, c, a)

    L = [f"max_role_contamination = {c}", f"min_anchored_row_share = {a}", "",
         "# Role threshold calibration", "",
         f"Selection: {how}. Flag rule: worst_role_contamination > max OR anchored_row_share < min.", "",
         "## Population", "",
         f"- PDF files with rows and roles_unmapped False: {len(files)} "
         f"(grid population, contamination measured: {len(grid_files)}; even {len(even)}, odd {len(odd)})",
         f"- roles_unmapped True (excluded): {unmapped}",
         f"- roles_unmapped False but contamination all-None (no column with >=5 non-placeholder cells; "
         f"excluded from grid, not clean or contaminated): {allnone}",
         f"- non-PDF or no rows (excluded): {nonpdf}",
         f"- bad label: per_file_cross_role_rate >= {BAD_RATE}. Even: {e['nbad']} bad / {e['ngood']} good. "
         f"Odd: {o['nbad']} bad / {o['ngood']} good.", ""]

    def tab(title, data):
        L.extend([f"## {title}", "", "| max_contam | min_anchor | TP | FN | FP | TN | recall | FPR | good records withheld |",
                  "|---|---|---|---|---|---|---|---|---|"])
        for c_, a_, x in data:
            mark = " **<- chosen**" if (c_, a_) == (c, a) else ""
            L.append(f"| {c_}{mark} | {a_} | {x['tp']} | {x['fn']} | {x['fp']} | {x['tn']} | "
                     f"{x['recall']:.2f} | {x['fpr']:.3f} | {x['withheld']} / {x['good_records']} |")
        L.append("")

    tab("Even-id grid (fit)", rows)
    tab("Odd-id grid (holdout, for reference)", [(c_, a_, confusion(odd, c_, a_)) for c_, a_ in product(CONTAM, ANCHOR)])
    L += ["## Chosen pair: confusion", "", "| split | TP | FN | FP | TN | recall | FPR | good records withheld |",
          "|---|---|---|---|---|---|---|---|"]
    for name, x in (("even (fit)", e), ("odd (holdout)", o)):
        L.append(f"| {name} | {x['tp']} | {x['fn']} | {x['fp']} | {x['tn']} | {x['recall']:.2f} | "
                 f"{x['fpr']:.3f} | {x['withheld']} / {x['good_records']} |")
    L.append("")

    # secondary: bake-off gold set (selected candidate in current output)
    sample = {s["sha256"]: s["file_url"] for s in json.loads((HERE / "sample.json").read_text())}
    by_url = {r["file_url"]: r for r in recs}
    L += ["## Secondary: bake-off gold set (10 provisional files)", "",
          "| gold | extractor | worst contam | anchored | flagged | gold acc | bad rate |", "|---|---|---|---|---|---|---|"]
    for g in sorted((HERE / "gold").glob("*.json")):
        r = by_url.get(sample.get(g.stem))
        if not r or not r.get("rows"):
            L.append(f"| {g.stem[:6]} | - | no rows | | | | |")
            continue
        sc = score_table(r["rows"])
        acc = gold_accuracy(r["rows"], json.loads(g.read_text()))["normalised"]
        fl = "unmapped" if sc.roles_unmapped else flagged(dict(worst=sc.worst_role_contamination, anchor=sc.anchored_row_share), c, a)
        wc = "None" if sc.worst_role_contamination is None else f"{sc.worst_role_contamination:.2f}"
        an = "None" if sc.anchored_row_share is None else f"{sc.anchored_row_share:.2f}"
        L.append(f"| {g.stem[:6]} | {r.get('pdf_extractor')} | {wc} | {an} | {fl} | {acc:.2f} | {rates.get(r['file_url'], 0.0):.2f} |")
    out = HERE / "results" / "role_calibration.md"
    out.write_text("\n".join(L) + "\n")
    print("\n".join(L[:30]))


if __name__ == "__main__":
    main()
