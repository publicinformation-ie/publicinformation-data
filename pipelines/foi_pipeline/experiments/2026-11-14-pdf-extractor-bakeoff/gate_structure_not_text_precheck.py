"""Offline pre-check for openspec change foi-gate-on-structure-not-text.

Re-scores transform_disclosure_files/output.json with the real scorer
(lib.table_structure.score_table) and compares with the stored gate result
(assess_table_structure/errors.json). Writes results/gate_structure_not_text_precheck.md.
Run from the repo root with PYTHONPATH=src:pipelines/foi_pipeline.
"""
import collections, json
from pathlib import Path
from lib.table_structure import failed_checks, score_table

P = Path("pipelines/foi_pipeline/steps")
OUT = Path(__file__).parent / "results" / "gate_structure_not_text_precheck.md"
res = json.load(open(P / "transform_disclosure_files/output.json"))["results"]
old = {e["context"]["file_url"]: e["context"]["failed_checks"]
       for e in json.load(open(P / "assess_table_structure/errors.json"))}
override = set(json.load(open(P / "extract_disclosures_canonicalize/column_mappings.json")))

recovered, rows_rec, still, newfail = (collections.Counter() for _ in range(4))
run_together_accepted = []
n_pdf = n_pass_before = 0
for r in res:
    if r.get("file_type") != "pdf" or not r.get("rows") or r["file_url"] in override:
        continue
    u = r["file_url"]; n_pdf += 1
    sc = score_table(r["rows"]); f = failed_checks(sc)
    was = old.get(u)
    key = "+".join(sorted(was)) if was else None
    if was is None:
        n_pass_before += 1
        if f: newfail["+".join(f)] += 1
    elif not f:
        recovered[key] += 1; rows_rec[key] += sc.n_rows
        if sc.run_together_rate > 0.02: run_together_accepted.append(u)
    else:
        still["+".join(f)] += 1
gated = sum(1 for u in old if u not in override)
lines = [
    "# Pre-check: gate on structure, not text", "",
    "Offline re-score of `transform_disclosure_files/output.json` with the new `score_table`. Nothing re-run.", "",
    f"- PDFs with rows and no override: {n_pdf}; gated before: {gated}; passing before: {n_pass_before}",
    f"- **Recovered: {sum(recovered.values())} files, {sum(rows_rec.values())} data rows**",
    f"- **Currently passing PDFs that now fail: {sum(newfail.values())}** {dict(newfail)}",
    f"- Recovered files with run_together_rate > 0.02 (accepted with poor text): {len(run_together_accepted)}", "",
    "## Recovered by original failed-check combination", "",
    "| Original failed checks | Recovered files | Data rows | Still gated |", "|---|---|---|---|",
]
total = collections.Counter("+".join(sorted(v)) for u, v in old.items() if u not in override)
for k, n in total.most_common():
    lines.append(f"| {k} | {recovered[k]} of {n} | {rows_rec[k]} | {n - recovered[k]} |")
lines += ["", "## Gated files that still fail, by their new failed checks", ""]
lines += [f"- {k}: {v}" for k, v in still.most_common()]
OUT.parent.mkdir(exist_ok=True); OUT.write_text("\n".join(lines) + "\n")
print("\n".join(lines))
