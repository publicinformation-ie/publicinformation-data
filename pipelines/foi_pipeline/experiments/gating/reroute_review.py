"""Tap-to-approve review of a re-routed extractor for the controls_rejected.json files.

Same tap UI and verdict format as control_review, but the rows shown come from a CHOSEN candidate
(a fixes.py name such as `force:pdfplumber`, `force:mistral_cache` or `docling`), read from the
extraction cache; nothing is downloaded and no paid call is made (mistral_cache is a cache read).

  uv run python -m experiments.gating.reroute_review survey --round-dir D     # candidates x fill -> survey.json
  uv run python -m experiments.gating.reroute_review build  --round-dir D [--pick 1210=docling ...]
  uv run python -m experiments.gating.serve --round-dir D
  uv run python -m experiments.gating.control_review finalize --round-dir D   # same verdict scoring
"""
import argparse
import json
import sys
from pathlib import Path

import pymupdf

from experiments.gating import control_review as cr
from experiments.gating.control_review import CONTINUATION_MAX, _norm
from experiments.gating.paths import GATING, SCRATCH, content_sha, pdf_bytes

CANDIDATES = ["force:pdfplumber", "force:camelot_lattice", "force:pymupdf", "force:mistral_cache",
              "force:camelot_stream", "docling"]
FILL_FIELDS = ["foi_reference_id", "date_received", "decision_date", "decision_status", "request_description"]
# Default pick per public_body_id, chosen from survey.json (record count vs PDF rows, then fill, then header).
PICKS = {1210: "docling", 1508: "force:pdfplumber", 1235: "force:mistral_cache",
         1655: "docling", 1244: "force:mistral_cache"}


def parse_picks(args: list[str] | None) -> dict[int, str]:
    """`--pick 1210=docling` overrides on top of PICKS. Unknown candidates are an error."""
    picks = dict(PICKS)
    for a in args or []:
        body, _, name = a.partition("=")
        if not body.isdigit() or name not in CANDIDATES:
            raise ValueError(f"bad --pick {a!r}; want BODY=<one of {CANDIDATES}>")
        picks[int(body)] = name
    return picks


def fill_shares(records: list[dict]) -> dict[str, float]:
    """Share of records with a non-empty value, per field in FILL_FIELDS."""
    n = max(1, len(records))
    return {k: round(sum(1 for r in records if r.get(k) not in (None, "")) / n, 2) for k in FILL_FIELDS}


def merge_record(rows: list[list], i: int) -> tuple[int, list[str]]:
    """Merge row i with the continuation rows (fewer than two filled cells) that follow it.
    Returns (index of the next record's first row, merged cell texts)."""
    j = i + 1
    while j < len(rows) and j - i <= CONTINUATION_MAX and sum(1 for c in rows[j] if _norm(c)) < 2:
        j += 1
    merged = [" ".join(p for p in (str(rows[k][c] or "").strip() for k in range(i, j) if c < len(rows[k])) if p)
              for c in range(len(rows[i]))]
    return j, merged


def _rejected() -> list[dict]:
    return json.loads((GATING / "controls_rejected.json").read_text())


def _rows(fix_name: str, url: str, data: bytes, stored: dict) -> list[list] | None:
    from experiments.gating.extract_cache import get_rows  # noqa: PLC0415
    from experiments.gating.fixes import get  # noqa: PLC0415

    ex = get_rows(get(fix_name), url, data, stored)
    return ex.rows if ex.status == "ok" else None


def survey(round_dir: Path) -> dict:
    from experiments.gating.downstream import item_for, run_downstream, transform_index  # noqa: PLC0415

    stored = transform_index()
    out = {}
    for c in _rejected():
        url, data = c["file_url"], pdf_bytes(c["file_url"])
        entry = {"body": c["public_body_id"], "stored_extractor": c["pdf_extractor"], "candidates": {}}
        for name in CANDIDATES:
            rows = _rows(name, url, data, stored[url]) if data else None
            if rows is None:
                entry["candidates"][name] = {"status": "not_extracted"}
                continue
            o = run_downstream([item_for(stored[url], rows, name)], "reroute_survey", SCRATCH)[url]
            recs = [r for r in _read_records() if r.get("file_url") == url]
            entry["candidates"][name] = {"raw_rows": len(rows), "gate_pass": o.gate_pass, "records": o.records,
                                         "errors": o.errors, "fill": fill_shares(recs)}
        out[url] = entry
    Path(round_dir).mkdir(parents=True, exist_ok=True)
    (Path(round_dir) / "survey.json").write_text(json.dumps(out, indent=1) + "\n")
    return out


def _read_records() -> list[dict]:
    d = next(iter(sorted((SCRATCH / "reroute_survey").glob("*canonicalize_rows"))))
    return json.loads((d / "output.json").read_text())["results"]


def build(round_dir: Path, picks: dict[int, str] | None = None) -> Path:
    from experiments.gating.downstream import transform_index  # noqa: PLC0415
    from lib.table_utils import detect_header_row  # noqa: PLC0415

    picks = picks or PICKS
    round_dir = Path(round_dir)
    review = round_dir / "review"
    review.mkdir(parents=True, exist_ok=True)
    stored = transform_index()
    files = []
    for c in _rejected():
        url, body = c["file_url"], c["public_body_id"]
        name = picks[body]
        data = pdf_bytes(url)
        rows = _rows(name, url, data, stored.get(url, {})) if data else None
        if not rows:
            print(f"skip body {body}: {name} gave no rows", file=sys.stderr)
            continue
        sha = content_sha(data)
        hi = int(detect_header_row(rows) or 0)
        items = []
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            for i in cr.sample_rows(rows, sha, start=hi + 1):
                loc = cr.locate_row(doc, rows[i])
                j, merged = merge_record(rows, i)
                img = None
                if loc:
                    nxt = cr.locate_row(doc, rows[j]) if j < len(rows) else None
                    rect = loc[1]
                    if nxt and nxt[0] == loc[0] and nxt[2] > rect[1]:
                        rect = (rect[0], rect[1], rect[2], min(max(rect[3], nxt[2]), rect[1] + 400))
                    elif j - i > 1:
                        rect = (rect[0], rect[1], rect[2], min(loc[1][3] + 60 * (j - i - 1), rect[1] + 400))
                    img = f"img/{sha[:12]}-{i}.png"
                    cr.crop_png(doc, loc[0], rect, review / img)
                items.append({"key": f"{sha[:12]}|r{i}", "row": i, "cells": merged,
                              "img": img, "page": loc[0] if loc else None})
            n_pages = len(doc)
        files.append({"sha": sha, "sha12": sha[:12], "body": body, "name": stored.get(url, {}).get("name"),
                      "url": url, "extractor": name, "origin": "reroute",
                      "n_rows": len(rows) - 1 - hi, "n_pages": n_pages,
                      "header": [_norm(h) for h in rows[hi]], "items": items,
                      "missing_key": f"{sha[:12]}|missing"})
    (round_dir / "files.json").write_text(json.dumps(files, indent=1, ensure_ascii=False) + "\n")
    page = review / "index.html"
    page.write_text(cr._page(files).replace("<title>Control review</title>", "<title>Reroute review</title>"))
    return page


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="reroute_review")
    ap.add_argument("cmd", choices=["survey", "build"])
    ap.add_argument("--round-dir", required=True)
    ap.add_argument("--pick", action="append", help="BODY=candidate override, repeatable")
    a = ap.parse_args(argv)
    if a.cmd == "survey":
        survey(Path(a.round_dir))
        print(Path(a.round_dir) / "survey.json")
    else:
        print(build(Path(a.round_dir), parse_picks(a.pick)))


if __name__ == "__main__":
    main()
