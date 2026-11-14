#!/usr/bin/env python3
"""Replay cached Mistral OCR for error PDFs through the structure scorer.

No network, no PDF bytes. Run from pipelines/foi_pipeline:
    uv run python experiments/2026-11-14-pdf-extractor-bakeoff/replay_mistral_cache.py
"""
import json
import sys
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

_HERE = Path(__file__).parent
_FOI = _HERE.parents[1]
sys.path.insert(0, str(_FOI))
sys.path.insert(0, str(_FOI.parents[1] / "src"))

from lib.table_structure import score_table, passes, failed_checks
from steps.transform_disclosure_files.mistral_ocr import markdown_to_pages, read_cached_ocr
from steps.transform_disclosure_files.process import _merge_page_splits

_STEPS = _FOI / "steps"
_ERRORS = _STEPS / "extract_disclosures_canonicalize_rows" / "errors.json"
_TRANSFORM = _STEPS / "transform_disclosure_files" / "output.json"
_OCR_CACHE = _STEPS / "transform_disclosure_files" / "ocr_cache"
_OUT = _HERE / "results"


def main():
    errors = json.loads(_ERRORS.read_text())
    transform = {r["file_url"]: r for r in json.loads(_TRANSFORM.read_text())["results"]}

    n_errors = Counter()
    body_of = {}
    for e in errors:
        ctx = e.get("context") or {}
        url = ctx.get("file_url")
        if not url:
            continue
        n_errors[url] += 1
        body_of.setdefault(url, ctx.get("public_body_id"))

    out = []
    skipped_non_pdf = skipped_no_record = 0
    for url in sorted(n_errors):
        rec = transform.get(url)
        if rec is None:
            skipped_no_record += 1
            continue
        if rec.get("file_type") != "pdf":
            skipped_non_pdf += 1
            continue
        cur = score_table(rec["rows"])
        md = read_cached_ocr(url, _OCR_CACHE)
        mist = None
        if md is not None:
            rows, _ = _merge_page_splits(markdown_to_pages(md))
            mist = score_table(rows)
        out.append({
            "file_url": url,
            "public_body_id": rec.get("public_body_id", body_of[url]),
            "n_errors": n_errors[url],
            "current_extractor": rec.get("pdf_extractor"),
            "current": asdict(cur),
            "mistral": asdict(mist) if mist else None,
            "current_passes": passes(cur),
            "mistral_passes": passes(mist) if mist else None,
            "current_failed": failed_checks(cur),
            "mistral_failed": failed_checks(mist) if mist else None,
        })
    _OUT.mkdir(parents=True, exist_ok=True)
    (_OUT / "mistral_replay.json").write_text(json.dumps(out, indent=1))

    cached = [r for r in out if r["mistral"] is not None]
    def cat(r):
        return {(True, True): "both", (True, False): "mistral_only",
                (False, True): "current_only", (False, False): "neither"}[
            (r["mistral_passes"], r["current_passes"])]
    tot = Counter(cat(r) for r in cached)
    by_body = defaultdict(Counter)
    body_err = Counter()
    body_names = {r["public_body_id"]: transform[r["file_url"]]["name"] for r in out}
    for r in out:
        body_err[r["public_body_id"]] += r["n_errors"]
    for r in cached:
        by_body[r["public_body_id"]][cat(r)] += 1
    body_pdfs = Counter(r["public_body_id"] for r in out)
    body_cached = Counter(r["public_body_id"] for r in cached)

    lines = ["# Mistral cache replay (generated)", "",
             "User answer: the last run was not meant to use Mistral, so the error PDFs "
             "were not a configuration regression.", "",
             f"- distinct error file_urls: {len(n_errors)} "
             f"(non-pdf skipped: {skipped_non_pdf}, no transform record: {skipped_no_record})",
             f"- error PDFs: {len(out)}",
             f"- with Mistral cache hit: {len(cached)}",
             f"- cached, clean via Mistral: {tot['both'] + tot['mistral_only']}",
             f"- cached, clean via current: {tot['both'] + tot['current_only']}",
             f"- cached, clean via both: {tot['both']}",
             f"- cached, clean via neither: {tot['neither']}",
             f"- Mistral only: {tot['mistral_only']}; current only: {tot['current_only']}", "",
             "## Top 10 bodies by error count (cached PDFs only in the clean columns)", "",
             "| body | id | errors | error PDFs | cached | mistral | current | both | neither |",
             "|---|---|---|---|---|---|---|---|---|"]
    for b, ne in body_err.most_common(10):
        c = by_body[b]
        lines.append(f"| {body_names[b]} | {b} | {ne} | {body_pdfs[b]} | {body_cached[b]} | "
                     f"{c['both'] + c['mistral_only']} | {c['both'] + c['current_only']} | "
                     f"{c['both']} | {c['neither']} |")
    fc = Counter()
    for r in cached:
        for k in r["mistral_failed"]:
            fc[("mistral", k)] += 1
        for k in r["current_failed"]:
            fc[("current", k)] += 1
    lines += ["", "## Failed checks among cached PDFs", ""]
    for (who, k), n in sorted(fc.items()):
        lines.append(f"- {who} {k}: {n}")
    ext = Counter(r["current_extractor"] for r in out)
    lines += ["", f"Current extractor among error PDFs: {dict(ext)}"]
    (_OUT / "mistral_replay.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
