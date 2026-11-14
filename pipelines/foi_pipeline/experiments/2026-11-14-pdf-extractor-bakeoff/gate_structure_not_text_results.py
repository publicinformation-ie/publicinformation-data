"""Acceptance checks + follow-up counts for openspec change foi-gate-on-structure-not-text.
Run from pipelines/foi_pipeline: PYTHONPATH=../../src:. python experiments/<this dir>/gate_structure_not_text_results.py
"""
import collections, json, sys
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from lib.column_map import canonicalize_headers
from bakeoff import gold_accuracy
from lib.table_structure import passes, score_table

S = Path("steps")
A = Path("/Volumes/ext/dev/publicinformation/foi-after-pr26-snapshot-2026-11-14")
B = Path("/Volumes/ext/dev/publicinformation/foi-before-snapshot-2026-11-12")
def res(d, step): return json.load(open(d / step / "output.json"))["results"]
def errs(d, step="assess_table_structure"):
    return {e["context"]["file_url"]: e["context"] for e in json.load(open(d / step / "errors.json"))}
CAN = "extract_disclosures_canonicalize_rows"
now, pr26, nov = res(S, CAN), res(A, CAN), res(B, CAN)
def by_body(rs):
    c = collections.Counter()
    for r in rs: c[str(r["public_body_id"])] += 1
    return c
bn, bp, bv = by_body(now), by_body(pr26), by_body(nov)
bodies = sorted(set(bn) | set(bp) | set(bv), key=int)
junk = lambda r: not r.get("foi_reference_id") and not r.get("date_received") and not r.get("decision_date")
e_now, e_pr26 = errs(S), errs(A)
L = ["# Gate on structure, not text: results", "",
     "Working tree after the all-bodies re-run vs the post-PR #26 snapshot (`foi-after-pr26-snapshot-2026-11-14`) and the Nov-12 baseline.", ""]

L += ["## Totals", "", "| | Nov-12 baseline | post-PR #26 | this change |", "|---|---|---|---|",
      f"| canonicalize_rows records | {len(nov)} | {len(pr26)} | {len(now)} |",
      f"| TableStructureUnreliable | n/a (no gate) | {len(e_pr26)} | {len(e_now)} |", ""]

below5 = [(b, bp[b], bn[b]) for b in bodies if bp[b] and bn[b] < 0.95 * bp[b]]
belowbase = [(b, bv[b], bn[b]) for b in bodies if bn[b] < bv[b]]
zero_now = [b for b in bodies if bn[b] == 0]
zero_new = [b for b in zero_now if bp[b] > 0]
L += [f"- Bodies in union: {len(bodies)}",
      f"- Bodies below the Nov-12 baseline: {len(belowbase)} (records short: {sum(x[1]-x[2] for x in belowbase)})",
      f"- Zero-record bodies now: {len(zero_now)} ({', '.join(zero_now)}); newly zero vs PR #26: {zero_new}", "",
      "### Bodies down more than 5% vs post-PR #26", ""]
L += [f"- body {b}: {x} -> {y}" for b, x, y in below5] or ["- none"]

# selection changes
tn, tp = {r["file_url"]: r.get("pdf_extractor") for r in res(S, "transform_disclosure_files")}, {r["file_url"]: r.get("pdf_extractor") for r in res(A, "transform_disclosure_files")}
chg = [(u, tp[u], tn[u]) for u in tn if u in tp and tp[u] != tn[u]]
L += ["", f"## Extractor selection changes: {len(chg)} files", "", "| from -> to | files |", "|---|---|"]
for k, v in collections.Counter(f"{a} -> {b}" for _, a, b in chg).most_common(): L.append(f"| {k} | {v} |")
L += ["", "<details><summary>Files</summary>", ""] + [f"- {u} : {a} -> {b}" for u, a, b in chg] + ["", "</details>"]

# acceptance
newly = [u for u in e_pr26 if u not in e_now]
rec_by_url = collections.defaultdict(list)
for r in now: rec_by_url[r["file_url"]].append(r)
rep_only = [u for u, c in e_pr26.items() if c["failed_checks"] == ["repeated_header_share"] and u in newly]
bad = 0
for u in rep_only:
    for r in rec_by_url[u]:
        for f in ("foi_reference_id", "date_received", "decision_date", "requester_type", "decision_status", "review_status", "related_request", "request_description"):
            v = r.get(f)
            if isinstance(v, str) and any(canonicalize_headers([v]).values()): bad += 1
nr = [r for u in newly for r in rec_by_url[u]]
jshare = sum(map(junk, nr)) / len(nr) if nr else 0
wid = [u for u, c in e_pr26.items() if c["failed_checks"] == ["width_uniformity"]]
still = [u for u in wid if u in e_now]
L += ["", "## Acceptance checks", ""]
L += [f"- (a) no body down >5% vs PR #26 without explanation: **{'PASS' if not below5 else 'FAIL'}** ({len(below5)} bodies)",
      f"- (b) header-like field values in records from the {len(rep_only)} newly accepted repeated-header files: **{'PASS' if bad == 0 else 'FAIL'}** ({bad} values; {sum(len(rec_by_url[u]) for u in rep_only)} records)",
      f"- (c) junk share of records from {len(newly)} newly accepted files: **{'PASS' if jshare <= .05 else 'FAIL'}** ({jshare:.1%} of {len(nr)})",
      f"- (d) width-only files still rejected: **{'PASS' if len(still) == len(wid) else 'FAIL'}** ({len(still)} of {len(wid)})"]
# gold
sample = {s["sha256"]: s["file_url"] for s in json.load(open(HERE / "sample.json"))}
rows_now = {r["file_url"]: r for r in res(S, "transform_disclosure_files")}
tp_, fp_, fn_, tn_, det = 0, 0, 0, 0, []
for g in (HERE / "gold").glob("*.json"):
    u = sample.get(g.stem); r = rows_now.get(u)
    if not r or not r.get("rows"): det.append(f"{g.stem[:6]}: no rows"); continue
    sc = score_table(r["rows"]); acc = gold_accuracy(r["rows"], json.load(open(g)))["normalised"]
    p, y = passes(sc), acc >= .95
    tp_ += p and y; fp_ += p and not y; fn_ += (not p) and y; tn_ += (not p) and not y
    det.append(f"{g.stem[:6]} {r.get('pdf_extractor')}: passes={p} gold={acc:.2f}")
L += [f"- (e) gold-set confusion (selected candidate only, 10-file in-sample set; not a pass bar): TP {tp_} FP {fp_} FN {fn_} TN {tn_}"
      f"; precision {tp_/(tp_+fp_):.2f}" if tp_ + fp_ else f"- (e) gold TP {tp_} FP {fp_} FN {fn_} TN {tn_}"]
L += ["  - " + d for d in det]

# follow-ups
errc = collections.Counter(); per = collections.defaultdict(collections.Counter)
for e in json.load(open(S / CAN / "errors.json")):
    errc[e["error_type"]] += 1; per[e["error_type"]][str(e["context"].get("public_body_id"))] += 1
jb = collections.Counter(str(r["public_body_id"]) for r in now if junk(r))
L += ["", "## Follow-ups (counts after the re-run)", "",
      f"1. Column mis-mapping: StatusValueIsDate {errc['StatusValueIsDate']}; top bodies {per['StatusValueIsDate'].most_common(4)}; UnrecognizedDecisionStatus {errc['UnrecognizedDecisionStatus']}",
      f"2. Fragment junk (no reference, no dates): {sum(jb.values())} records; top bodies {jb.most_common(6)} (1486={jb['1486']}, 1655={jb['1655']}, 1235={jb['1235']}, 1390={jb['1390']})",
      f"3. Cell repair: UnrecognizedRequesterType {errc['UnrecognizedRequesterType']} (body 1655: {per['UnrecognizedRequesterType']['1655']}); run-together tokens in newly accepted files: see pre-check (11 files with run_together_rate > 0.02)",
      f"4. Zero-record bodies 1496 / 1758: {bn['1496']} / {bn['1758']} records",
      f"5. Width-gated files: {len(e_now)} still rejected, of which width-only {len(still)}; baseline junk for the 33 width-only files was 35%"]
(HERE / "results" / "gate_structure_not_text_results.md").write_text("\n".join(L) + "\n")
print("\n".join(l for l in L if not l.startswith("- http")))
