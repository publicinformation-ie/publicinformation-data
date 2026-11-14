#!/usr/bin/env python3
"""Draw the stratified bake-off sample and fetch any PDFs missing from the cache.

Run from pipelines/foi_pipeline:
    uv run python experiments/2026-11-14-pdf-extractor-bakeoff/sample.py --dry-run
    uv run python experiments/2026-11-14-pdf-extractor-bakeoff/sample.py

Scoring is offline (transform output.json rows through lib.table_structure). The
default run downloads missing PDFs sequentially, 2 s apart, via
DisclosureFileCache.get_file_path; failures are recorded in sample.json.
"""
import argparse
import hashlib
import json
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

_HERE = Path(__file__).parent
_FOI = _HERE.parents[1]
sys.path.insert(0, str(_FOI))
sys.path.insert(0, str(_FOI.parents[1] / "src"))

from lib.table_structure import score_table, passes, failed_checks
from steps.transform_disclosure_files.mistral_ocr import read_cached_ocr
from steps.verify_disclosure_files.process import DisclosureFileCache

_STEPS = _FOI / "steps"
_ERRORS = _STEPS / "extract_disclosures_canonicalize_rows" / "errors.json"
_TRANSFORM = _STEPS / "transform_disclosure_files" / "output.json"
_OCR_CACHE = _STEPS / "transform_disclosure_files" / "ocr_cache"
_VERIFY_DIR = _STEPS / "verify_disclosure_files"
_OUT = _HERE / "sample.json"

SEED = 20261114
PER_STRATUM = 6
MAX_PER_BODY = 3
MIN_MISTRAL = 8
MIN_CAMELOT = 4
MIN_TOTAL = 36

# priority order when a file fails several checks
MECHANISMS = [
    ("width_shift", "width_uniformity"),
    ("fragments", "fragment_share"),
    ("split_words", "split_word_rate"),
    ("header_repeat", "repeated_header_share"),
]
STRATA = [m for m, _ in MECHANISMS] + ["clean_with_errors", "clean_no_errors"]

_RTE = "https://about.rte.ie/wp-content/uploads/"
_FINGAL = "https://www.fingal.ie/sites/default/files/"
MANDATORY = [
    _RTE + "2019/07/rte-freedom-of-information-q4-disclosure-log-2018.pdf",  # RTE 2018 (Q4)
    _RTE + "2020/01/RTE-FOI-DISCLOSURE-LOG-Q4.pdf",  # RTE Q4 2019
    _FINGAL + "2019-03/FOI%20Disclosure%20Log%202016.pdf",  # Fingal 2016
    _FINGAL + "2026-01/2024-foi-disclosure-log.pdf",  # Fingal 2024
]


def _stratum(failed, n_errors):
    for name, check in MECHANISMS:
        if check in failed:
            return name
    if not failed and n_errors:
        return "clean_with_errors"
    if not failed:
        return "clean_no_errors"
    return None  # fails only column_type_purity: not a target mechanism


def build_candidates():
    n_errors = Counter()
    for e in json.loads(_ERRORS.read_text()):
        url = (e.get("context") or {}).get("file_url")
        if url:
            n_errors[url] += 1
    cands = []
    for r in json.loads(_TRANSFORM.read_text())["results"]:
        if r.get("file_type") != "pdf":
            continue
        url = r["file_url"]
        failed = failed_checks(score_table(r["rows"]))
        s = _stratum(failed, n_errors[url])
        if s == "clean_no_errors" and r.get("pdf_extractor") != "pdfplumber":
            s = None
        if s is None:
            continue
        cands.append({
            "file_url": url,
            "public_body_id": r["public_body_id"],
            "name": r["name"],
            "stratum": s,
            "extractor": r.get("pdf_extractor"),
            "failed": failed,
            "mistral": read_cached_ocr(url, _OCR_CACHE) is not None,
        })
    return cands


def select(cands):
    rng = random.Random(SEED)
    by_url = {c["file_url"]: c for c in cands}
    chosen, per_body, per_stratum = [], Counter(), Counter()

    def take(c):
        chosen.append(c)
        per_body[c["public_body_id"]] += 1
        per_stratum[c["stratum"]] += 1

    for url in MANDATORY:
        take(by_url[url])
    pool = {s: [c for c in cands if c["stratum"] == s and c not in chosen] for s in STRATA}
    for s in STRATA:
        rng.shuffle(pool[s])

    def can(c):
        return (c not in chosen and per_body[c["public_body_id"]] < MAX_PER_BODY
                and per_stratum[c["stratum"]] < PER_STRATUM)

    # quota pass first (camelot, then Mistral hits), then fill to PER_STRATUM
    for key, need in (("camelot", MIN_CAMELOT), ("mistral", MIN_MISTRAL)):
        def has(c):
            return c["extractor"] == "camelot_stream" if key == "camelot" else c["mistral"]
        for s in STRATA:
            for c in pool[s]:
                if sum(1 for x in chosen if has(x)) >= need:
                    break
                if has(c) and can(c):
                    take(c)
    for s in STRATA:
        for c in pool[s]:
            if per_stratum[s] >= PER_STRATUM:
                break
            if can(c):
                take(c)
    # top up to MIN_TOTAL when a stratum has too few eligible files (header_repeat is rare)
    while len(chosen) < MIN_TOTAL:
        added = False
        for s in STRATA:
            for c in pool[s]:
                if len(chosen) >= MIN_TOTAL:
                    break
                if c not in chosen and per_body[c["public_body_id"]] < MAX_PER_BODY:
                    take(c)
                    added = True
                    break
        if not added:
            break
    return chosen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    chosen = select(build_candidates())
    print(f"{'stratum':18} {'n':>3} {'camelot':>7} {'mistral':>7}")
    for s in STRATA:
        g = [c for c in chosen if c["stratum"] == s]
        print(f"{s:18} {len(g):>3} {sum(c['extractor']=='camelot_stream' for c in g):>7} "
              f"{sum(c['mistral'] for c in g):>7}")
    print(f"total {len(chosen)}; camelot_stream {sum(c['extractor']=='camelot_stream' for c in chosen)}; "
          f"mistral hits {sum(c['mistral'] for c in chosen)}; max per body "
          f"{max(Counter(c['public_body_id'] for c in chosen).values())}")
    if args.dry_run:
        for c in chosen:
            print(f"  {c['stratum']:18} {c['name'][:28]:28} {c['extractor']:14} {c['file_url']}")
        return

    cache = DisclosureFileCache(_VERIFY_DIR / "cache")
    out, fetched = [], 0
    for c in chosen:
        path = cache._get_cache_path(c["file_url"])
        entry = {"file_url": c["file_url"], "public_body_id": c["public_body_id"],
                 "stratum": c["stratum"],
                 # sha256 of the file bytes if on disk (cache filename is sha256 of the URL)
                 "sha256": None, "on_disk": False}
        if not path.exists():
            if fetched:
                time.sleep(2)
            fetched += 1
            try:
                cache.get_file_path(c["file_url"], str(_VERIFY_DIR))
            except Exception as e:  # record, do not abort
                entry["error"] = f"{type(e).__name__}: {e}"
        if path.exists():
            entry["on_disk"] = True
            entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"{'ok ' if entry['on_disk'] else 'FAIL'} {c['file_url']}", flush=True)
        out.append(entry)
    _OUT.write_text(json.dumps(out, indent=1))
    print(f"on_disk {sum(e['on_disk'] for e in out)}/{len(out)}")


if __name__ == "__main__":
    main()
