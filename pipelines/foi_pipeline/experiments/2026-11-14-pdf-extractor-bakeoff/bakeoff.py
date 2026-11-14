#!/usr/bin/env python3
"""Score every candidate extractor on every on-disk sample PDF; gold accuracy on gold files.

No network, no paid calls (mistral_cache reads the on-disk cache only).
Run from pipelines/foi_pipeline:
    uv run python experiments/2026-11-14-pdf-extractor-bakeoff/bakeoff.py
"""
import hashlib
import json
import re
import sys
import time
from dataclasses import asdict
from pathlib import Path

_HERE = Path(__file__).parent
_FOI = _HERE.parents[1]
sys.path.insert(0, str(_FOI))
sys.path.insert(0, str(_FOI.parents[1] / "src"))

from lib.table_structure import _cell_type, _data_rows, failed_checks, passes, score_table
from steps.transform_disclosure_files.candidates import CANDIDATE_NAMES, extract_candidate
from steps.transform_disclosure_files.process import _merge_page_splits

CACHE = _FOI / "steps" / "verify_disclosure_files" / "cache"
OCR_CACHE = _FOI / "steps" / "transform_disclosure_files" / "ocr_cache"
RESULTS = _HERE / "results"
ALL = CANDIDATE_NAMES + ("docling",)


def _ws(s) -> str:
    return " ".join(("" if s is None else str(s)).split())


def _norm(s) -> str:
    """Whitespace + text-layer artefact normalisation (applied to both sides)."""
    s = _ws(s).replace("", "•")
    s = re.sub(r"(?<=\w[-‐-―]) (?=\w)", "", s)
    return s


def gold_accuracy(rows: list[list], gold: dict) -> dict:
    _, data, _ = _data_rows(rows)
    out = {}
    for label, fn in (("raw", _ws), ("normalised", _norm)):
        total = hit = aligned = 0
        for g in gold["rows"]:
            gcells = [fn(c) for c in g]
            key = next((c for c in g if _cell_type(c) == "reference"), None)
            if key is None:
                key = next((c for c in g if _cell_type(c) == "date"), None)
            cands = data
            if key is not None:
                k = fn(key)
                hits = [r for r in data if any(fn(c) == k for c in r)]
                cands = hits or []
            best = 0
            for r in cands:
                rc = [fn(c) for c in r]
                m = sum(1 for i, c in enumerate(gcells) if i < len(rc) and rc[i] == c)
                best = max(best, m)
            if cands and best:
                aligned += 1
            total += len(gcells)
            hit += best
        out[label] = hit / total if total else 0.0
        out[label + "_rows_aligned"] = aligned / len(gold["rows"]) if gold["rows"] else 0.0
    return out


def main():
    sample = [s for s in json.loads((_HERE / "sample.json").read_text()) if s["on_disk"]]
    dsum = json.loads((RESULTS / "docling" / "_summary.json").read_text())
    results = []
    for s in sample:
        url = s["file_url"]
        path = CACHE / (hashlib.sha256(url.encode()).hexdigest() + ".bytes")
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == s["sha256"], url
        gp = _HERE / "gold" / (s["sha256"] + ".json")
        gold = json.loads(gp.read_text()) if gp.exists() else None
        for name in ALL:
            rec = {"sha256": s["sha256"], "file_url": url, "public_body_id": s["public_body_id"],
                   "stratum": s["stratum"], "candidate": name, "has_gold": gold is not None}
            t0 = time.perf_counter()
            rows = None
            try:
                if name == "docling":
                    dp = RESULTS / "docling" / (s["sha256"] + ".json")
                    pages = json.loads(dp.read_text())["pages"]
                    rows, _ = _merge_page_splits(pages) if any(pages) else (None, None)
                    rec["seconds"] = dsum["timings"].get(s["sha256"])
                else:
                    c = extract_candidate(name, data, file_url=url, ocr_cache_dir=OCR_CACHE)
                    rows = c.rows if c else None
                    rec["seconds"] = time.perf_counter() - t0
            except Exception as e:  # extractor failure
                rec["error"] = f"{type(e).__name__}: {str(e)[:120]}"
                rec["seconds"] = time.perf_counter() - t0
            if not rows:
                rec["status"] = "error" if "error" in rec else "no_table"
            else:
                sc = score_table(rows)
                rec.update(status="ok", score=asdict(sc), passes=passes(sc),
                           failed=failed_checks(sc))
                if gold:
                    rec["gold"] = gold_accuracy(rows, gold)
            results.append(rec)
        print(s["sha256"][:8], file=sys.stderr)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "bakeoff.json").write_text(json.dumps(results, separators=(",", ":")))
    print(len(results), "records")


if __name__ == "__main__":
    main()
