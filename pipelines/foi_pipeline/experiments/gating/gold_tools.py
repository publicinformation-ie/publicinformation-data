"""Repeatable hand-checked gold tables (method: BAKEOFF/gold/README.md).

Page images are rendered, a model drafts column/row bounds from them, and cell text is read from the
PDF's own text layer. No extractor ever seeds a gold file. Cell `rect`s are in PDF points.

CLI: render --url U --out D | build --url U --bounds F
"""
import argparse
import json
import random
import sys
from pathlib import Path

import pymupdf

from experiments.gating.paths import BAKEOFF, GATING, GOLD_DIR, content_sha, pdf_bytes  # noqa: F401  (sets sys.path)

if str(BAKEOFF) not in sys.path:
    sys.path.insert(0, str(BAKEOFF))
from bakeoff import _norm  # noqa: E402
from lib.table_structure import _cell_type, _data_rows  # noqa: E402

STATUS_PATH = GATING / "gold_status.json"
GOLD_CELLS_DIR = GATING / "gold_cells"  # cell page + rect, kept out of the bake-off gold format
FIRST, LAST = 15, 5


def render_pages(data: bytes, out_dir: Path, dpi: int = 110) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for i, page in enumerate(doc, 1):
            p = out_dir / f"page-{i}.png"
            page.get_pixmap(dpi=dpi).save(p)
            paths.append(p)
    return paths


def _cell_text(words: list, rect: tuple) -> str:
    x0, y0, x1, y1 = rect
    inside = [w for w in words if x0 <= (w[0] + w[2]) / 2 < x1 and y0 <= (w[1] + w[3]) / 2 < y1]
    inside.sort(key=lambda w: (w[5], w[6], w[0]))
    return " ".join(w[4] for w in inside)


def gold_from_bounds(data: bytes, bounds: dict) -> dict:
    k = 72 / bounds.get("dpi", 110)
    rows, cells = [], []
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for pg in bounds["pages"]:
            words = doc[pg["page"] - 1].get_text("words")
            xs, ys = pg["x"], pg["y"]
            for r in range(len(ys) - 1):
                if r in pg.get("skip_rows", []):
                    continue
                rects = [(xs[c] * k, ys[r] * k, xs[c + 1] * k, ys[r + 1] * k) for c in range(len(xs) - 1)]
                row = [_cell_text(words, rc) for rc in rects]
                if any(row):
                    rows.append((row, pg["page"], rects))
    if len(rows) > FIRST + LAST:
        rows = rows[:FIRST] + rows[-LAST:]
    out_cells = [{"row": i, "col": c, "page": page, "rect": [round(v, 2) for v in rects[c]]}
                 for i, (row, page, rects) in enumerate(rows) for c in range(len(row))]
    return {"columns": list(bounds["columns"]), "rows": [r[0] for r in rows], "cells": out_cells}


def _gold_key(grow: list) -> str | None:
    key = next((c for c in grow if _cell_type(c) == "reference"), None)
    if key is None:
        key = next((c for c in grow if _cell_type(c) == "date"), None)
    return key


def aligned_row(grow: list, data: list[list], fn=_norm) -> list[str] | None:
    """Candidate row for a gold row, as gold_accuracy: rows holding the key cell, best column matches."""
    gcells = [fn(c) for c in grow]
    key = _gold_key(grow)
    cands = data
    if key is not None:
        k = fn(key)
        cands = [r for r in data if any(fn(c) == k for c in r)]
    best, best_m = None, 0
    for r in cands:
        rc = [fn(c) for c in r]
        m = sum(1 for i, c in enumerate(gcells) if i < len(rc) and rc[i] == c)
        if m > best_m:
            best, best_m = rc, m
    return best


def cells_to_check(gold: dict, fix_rows: dict, n_random: int = 10, seed: str = "") -> list[dict]:
    data_by_fix = {}
    for fix, rows in fix_rows.items():
        data_by_fix[fix] = _data_rows(rows)[1] if rows else None
    allcells = [(i, c) for i, row in enumerate(gold["rows"]) for c in range(len(row))]
    disputed, rest = [], []
    for i, c in allcells:
        g = _norm(gold["rows"][i][c])
        values, differs = {}, False
        for fix, data in data_by_fix.items():
            if data is None:
                continue
            ar = aligned_row(gold["rows"][i], data)
            v = ar[c] if ar is not None and c < len(ar) else ""
            values[fix] = v
            differs = differs or v != g
        (disputed if differs else rest).append((i, c, values))
    picked = random.Random(seed).sample(rest, min(n_random, len(rest)))
    out = []
    for reason, group in (("disputed", disputed), ("random", picked)):
        for i, c, values in group:
            out.append({"row": i, "col": c, "gold": gold["rows"][i][c], "values": values, "reason": reason})
    return out


def crop_cell(data: bytes, cell: dict, out: Path, dpi: int = 150, pad: int = 6) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        page = doc[cell["page"] - 1]
        x0, y0, x1, y1 = cell["rect"]
        clip = pymupdf.Rect(x0 - pad, y0 - pad, x1 + pad, y1 + pad) & page.rect
        page.get_pixmap(dpi=dpi, clip=clip).save(out)
    return out


def _set_status(sha: str, value: str, status_path: Path) -> None:
    status_path = Path(status_path)
    d = json.loads(status_path.read_text()) if status_path.is_file() else {}
    d[sha] = value
    status_path.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n")


def save_gold(content_sha: str, gold: dict, gold_dir: Path = GOLD_DIR,
              status_path: Path = STATUS_PATH, cells_dir: Path = GOLD_CELLS_DIR, force: bool = False) -> Path:
    gold_dir = Path(gold_dir)
    gold_dir.mkdir(parents=True, exist_ok=True)
    p = gold_dir / f"{content_sha}.json"
    if p.exists() and not force:
        raise FileExistsError(f"{p} already exists (may be hand-checked); pass force=True / --force to overwrite")
    if gold.get("cells"):
        cells_dir = Path(cells_dir)
        cells_dir.mkdir(parents=True, exist_ok=True)
        (cells_dir / f"{content_sha}.json").write_text(json.dumps(gold["cells"], indent=1) + "\n")
    p.write_text(json.dumps({"columns": gold["columns"], "rows": gold["rows"]}, indent=1, ensure_ascii=False) + "\n")
    _set_status(content_sha, "provisional", status_path)
    return p


def load_gold_cells(sha: str, cells_dir: Path = GOLD_CELLS_DIR) -> list | None:
    p = Path(cells_dir) / f"{sha}.json"
    return json.loads(p.read_text()) if p.is_file() else None


def mark_gold_checked(sha: str, status_path: Path = STATUS_PATH) -> None:
    _set_status(sha, "checked", status_path)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="gold_tools")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render")
    r.add_argument("--url", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--dpi", type=int, default=110)
    b = sub.add_parser("build")
    b.add_argument("--url", required=True)
    b.add_argument("--bounds", required=True)
    b.add_argument("--force", action="store_true", help="overwrite an existing gold file (resets it to provisional)")
    a = ap.parse_args(argv)
    data = pdf_bytes(a.url)
    if data is None:
        sys.exit(f"not in the PDF cache: {a.url}")
    if a.cmd == "render":
        for p in render_pages(data, Path(a.out), a.dpi):
            print(p)
    else:
        gold = gold_from_bounds(data, json.loads(Path(a.bounds).read_text()))
        sha = content_sha(data)
        print(save_gold(sha, gold, force=a.force), f"({len(gold['rows'])} rows, provisional)")


if __name__ == "__main__":
    main()
