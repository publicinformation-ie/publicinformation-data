"""Tap-to-approve review of control files (spec section 14.3): is the stored extraction actually right?

For each control candidate, a sample of the stored extracted rows is shown beside a crop of the PDF row.
The reviewer taps Correct or Wrong (and, if wrong, the bad columns), and once per file whether rows are
missing. `finalize` turns the taps into a cell score per file; a control must reach `gold_min` (0.95) and
have no missing rows. Nothing is read from an extractor except the rows already stored by the pipeline.

  uv run python -m experiments.gating.control_review build --round-dir D
  uv run python -m experiments.gating.serve --round-dir D          # then open the printed URL
  uv run python -m experiments.gating.control_review finalize --round-dir D
"""
import argparse
import hashlib
import html
import json
import random
import re
import sys
from pathlib import Path

import pymupdf

from experiments.gating.paths import GATING, content_sha, pdf_bytes, settings

SAMPLE_ROWS = 8
CROP_DPI = 130
CONTINUATION_MAX = 6  # as normalize_header._MAX_CONTINUATION_ROWS
KNOWN_BAD_BODIES = {1210, 1508, 1235}  # wrong under their current extractor (spec 14.3)
REPLACEMENT_EXTRACTORS = {"pymupdf": 3, "camelot_stream": 3}  # three known-bad controls, two candidates each


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def sample_rows(rows: list[list], seed: str, n: int = SAMPLE_ROWS, start: int = 1) -> list[int]:
    """Indices into rows after the header: the first two, the last, and random others, in file order."""
    body = [i for i in range(start, len(rows)) if sum(1 for c in rows[i] if _norm(c)) >= 2]
    if len(body) <= n:
        return body
    keep = set(body[:2]) | {body[-1]}
    rest = [i for i in body if i not in keep]
    keep |= set(random.Random(seed).sample(rest, n - len(keep)))
    return sorted(keep)


def locate_row(doc, cells: list[str]) -> tuple[int, tuple[float, float, float, float], float] | None:
    """Page number (1-based) and a crop rect for a stored row, found by searching its cell text on each page."""
    snippets = []
    for c in cells:
        lines = [ln for ln in str(c or "").split("\n") if len(_norm(ln)) >= 3]
        for line in dict.fromkeys(lines[:2] + lines[-2:]):  # first and last lines bound a multi-line cell
            snippets.append(_norm(line)[:40])
    if not snippets:
        return None
    best = None
    for pno, page in enumerate(doc, 1):
        hits = [(s, page.search_for(s)) for s in snippets]
        n = sum(1 for _, h in hits if h)
        if n and (best is None or n > best[0]):
            best = (n, pno, hits)
    if best is None:
        return None
    _, pno, hits = best
    page = doc[pno - 1]
    anchor = min(((s, h) for s, h in hits if h), key=lambda sh: (len(sh[1]), -len(sh[0])))[1][0]
    ys0, ys1 = [], []
    for _, h in hits:
        near = [r for r in h if abs(r.y0 - anchor.y0) < 220]
        if near:
            r = min(near, key=lambda r: abs(r.y0 - anchor.y0))
            ys0.append(r.y0)
            ys1.append(r.y1)
    y0, y1 = min(ys0) - 6, max(ys1) + 6
    first = next((h for s, h in hits if s == snippets[0] and h), None)  # leftmost cell's first line: the row top
    top = min(first, key=lambda r: abs(r.y0 - anchor.y0)).y0 - 4 if first else y0
    return pno, (0.0, max(0.0, y0), page.rect.width, min(page.rect.height, y1)), top


def crop_png(doc, pno: int, rect: tuple, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    page = doc[pno - 1]
    page.get_pixmap(dpi=CROP_DPI, clip=pymupdf.Rect(*rect) & page.rect).save(out)


def candidates() -> list[dict]:
    """Current controls minus the known-bad ones, plus replacement candidates for their extractors."""
    from experiments.gating.scope import file_stats  # noqa: PLC0415

    controls = json.loads((GATING / "controls.json").read_text())
    bad_urls = {c["file_url"] for c in controls if c["public_body_id"] in KNOWN_BAD_BODIES}
    out = [dict(c, origin="control") for c in controls if c["file_url"] not in bad_urls]
    taken = {c["file_url"] for c in controls}
    want = dict(REPLACEMENT_EXTRACTORS)
    for url, s in sorted(file_stats().items(), key=lambda kv: hashlib.sha256(kv[0].encode()).hexdigest()):
        ext = s.pdf_extractor or ""
        if (url in taken or s.file_type != "pdf" or s.gated or s.errors or s.records < 20
                or want.get(ext, 0) <= 0 or pdf_bytes(url) is None):
            continue
        want[ext] -= 1
        out.append({"file_url": url, "public_body_id": s.public_body_id, "pdf_extractor": ext,
                    "records": s.records, "origin": "candidate"})
    return out


def header_indexes() -> dict[str, int]:
    """Header row index the pipeline settles on, per file (the first grid row can be a title)."""
    p = GATING.parent.parent / "steps" / "extract_disclosures_detect_header_row" / "output.json"
    return {r["file_url"]: int(r.get("header_row_idx") or 0) for r in json.loads(p.read_text())["results"]}


def build(round_dir: Path) -> Path:
    from experiments.gating.downstream import transform_index  # noqa: PLC0415

    round_dir = Path(round_dir)
    review = round_dir / "review"
    review.mkdir(parents=True, exist_ok=True)
    stored = transform_index()
    hdr_idx = header_indexes()
    files = []
    for c in candidates():
        data = pdf_bytes(c["file_url"])
        item = stored.get(c["file_url"])
        if data is None or item is None or not item.get("rows"):
            print(f"skip (no cached bytes or stored rows): {c['file_url']}", file=sys.stderr)
            continue
        sha = content_sha(data)
        rows = item["rows"]
        hi = hdr_idx.get(c["file_url"], 0)
        header = rows[hi]
        items = []
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            for i in sample_rows(rows, sha, start=hi + 1):
                loc = locate_row(doc, rows[i])
                j = i + 1  # continuation rows (fewer than two filled cells) belong to this record
                while j < len(rows) and j - i <= CONTINUATION_MAX and sum(1 for c in rows[j] if _norm(c)) < 2:
                    j += 1
                merged = [" ".join(p for p in (str(rows[k][c] or "").strip() for k in range(i, j) if c < len(rows[k])) if p)
                          for c in range(len(rows[i]))]
                img = None
                if loc:
                    nxt = locate_row(doc, rows[j]) if j < len(rows) else None
                    rect = loc[1]
                    if nxt and nxt[0] == loc[0] and nxt[2] > rect[1]:  # the record ends where the next one starts
                        rect = (rect[0], rect[1], rect[2], min(max(rect[3], nxt[2]), rect[1] + 400))
                    elif j - i > 1:  # last record on the page: leave room for its continuation lines
                        rect = (rect[0], rect[1], rect[2], min(loc[1][3] + 60 * (j - i - 1), rect[1] + 400))
                    img = f"img/{sha[:12]}-{i}.png"
                    crop_png(doc, loc[0], rect, review / img)
                items.append({"key": f"{sha[:12]}|r{i}", "row": i, "cells": merged,
                              "img": img, "page": loc[0] if loc else None})
            n_pages = len(doc)
        files.append({"sha": sha, "sha12": sha[:12], "body": c["public_body_id"], "name": item.get("name"),
                      "url": c["file_url"], "extractor": c["pdf_extractor"], "origin": c["origin"],
                      "n_rows": len(rows) - 1 - hi, "n_pages": n_pages, "header": [_norm(h) for h in header],
                      "items": items, "missing_key": f"{sha[:12]}|missing"})
    (round_dir / "files.json").write_text(json.dumps(files, indent=1, ensure_ascii=False) + "\n")
    page = review / "index.html"
    page.write_text(_page(files))
    return page


def _e(x) -> str:
    return html.escape(str(x), quote=True)


def _page(files: list[dict]) -> str:
    cards = []
    for f in files:
        rows = []
        for it in f["items"]:
            kv = "".join(
                f'<div class="kv"><b>{_e(h)}</b><span>{_e(v) or "&nbsp;"}</span></div>'
                for h, v in zip(f["header"], it["cells"]))
            chips = "".join(f'<button class="chip" data-col="{ci}">{_e(h)}</button>'
                            for ci, h in enumerate(f["header"]))
            img = (f'<img loading="lazy" src="{it["img"]}" alt="pdf row">'
                   if it["img"] else '<p class="warn">Row not found in the PDF text. Open the PDF.</p>')
            rows.append(f'<div class="row" data-key="{_e(it["key"])}">{img}<div class="cells">{kv}</div>'
                        f'<div class="btns"><button class="ok">Correct</button><button class="bad">Wrong</button></div>'
                        f'<div class="chips" hidden><p>Tap the wrong columns</p>{chips}</div></div>')
        cards.append(
            f'<section class="file" data-sha="{f["sha12"]}"><h2>Body {f["body"]}: {_e(f["name"])}</h2>'
            f'<p class="meta">{_e(f["extractor"])} · {f["n_rows"]} rows · {f["n_pages"]} pages · {_e(f["origin"])}</p>'
            f'<p><a href="/pdf/{f["sha"]}.pdf">Open the PDF</a></p>{"".join(rows)}'
            f'<div class="row miss" data-key="{_e(f["missing_key"])}"><p><b>Are any PDF rows missing from the extraction?</b>'
            f'<br><small>Flip through the PDF: {f["n_rows"]} rows extracted over {f["n_pages"]} pages.</small></p>'
            f'<div class="btns"><button class="ok">None missing</button><button class="bad">Some missing</button></div></div>'
            f'</section>')
    return PAGE.replace("@@CARDS@@", "\n".join(cards))


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Control review</title>
<style>
body{font:16px system-ui,sans-serif;margin:0;padding:0 12px 80px;background:#f6f6f4;color:#111}
header{position:sticky;top:0;background:#111;color:#fff;padding:10px 12px;margin:0 -12px;z-index:5;display:flex;gap:12px;align-items:center}
header button{font-size:15px;padding:6px 12px;border-radius:6px;border:0}
.file{margin:18px 0;padding:12px;background:#fff;border-radius:10px;box-shadow:0 1px 3px #0003}
.meta{color:#555;margin:0}.row{border-top:1px solid #ddd;padding:10px 0}
.row img{width:100%;border:1px solid #bbb;border-radius:4px;display:block}
.kv{display:flex;gap:8px;padding:3px 0;border-bottom:1px dotted #ddd}.kv b{flex:0 0 34%;font-weight:600;color:#444;font-size:14px}
.kv span{white-space:pre-wrap;word-break:break-word}
.btns{display:flex;gap:10px;margin-top:10px}.btns button{flex:1;font-size:19px;padding:16px 0;border:2px solid #888;border-radius:10px;background:#eee}
.row.done-ok{background:#e8f6e8}.row.done-bad{background:#fbeaea}
.row.done-ok .ok,.row.done-bad .bad{outline:4px solid #000}
.ok{background:#cdeccd!important}.bad{background:#f4c9c9!important}
.chips button{font-size:16px;padding:10px 14px;margin:4px;border-radius:20px;border:2px solid #888;background:#fff}
.chips button.on{background:#c0392b;color:#fff;border-color:#c0392b}.warn{color:#a40}
</style></head><body>
<header><span id="prog">0 / 0</span><button id="next">Next undone</button><span id="err" style="color:#f88"></span></header>
@@CARDS@@
<script>
const V={};
function post(key,tags){return fetch('/verdict',{method:'POST',headers:{'Content-Type':'application/json'},
 body:JSON.stringify({key:key,text:'',tags:tags})}).then(r=>{if(!r.ok)throw 0;V[key]={tags:tags};
 document.getElementById('err').textContent=''}).catch(()=>{document.getElementById('err').textContent='NOT SAVED, retry'})}
function paint(el){const t=(V[el.dataset.key]||{}).tags;el.classList.remove('done-ok','done-bad');
 if(!t)return;el.classList.add(t[0]==='ok'?'done-ok':'done-bad');
 const ch=el.querySelector('.chips');if(ch){ch.hidden=t[0]==='ok';
  ch.querySelectorAll('.chip').forEach(c=>c.classList.toggle('on',t.includes('c'+c.dataset.col)))}}
function prog(){const rs=[...document.querySelectorAll('.row[data-key]')];
 document.getElementById('prog').textContent=rs.filter(r=>V[r.dataset.key]).length+' / '+rs.length}
document.querySelectorAll('.row[data-key]').forEach(el=>{
 el.querySelector('.ok').onclick=()=>post(el.dataset.key,['ok']).then(()=>{paint(el);prog()});
 el.querySelector('.bad').onclick=()=>post(el.dataset.key,['bad']).then(()=>{paint(el);prog()});
 el.querySelectorAll('.chip').forEach(c=>c.onclick=()=>{const cur=(V[el.dataset.key]||{tags:['bad']}).tags.filter(x=>x!=='bad');
  const t='c'+c.dataset.col;const n=cur.includes(t)?cur.filter(x=>x!==t):cur.concat(t);
  post(el.dataset.key,['bad'].concat(n)).then(()=>paint(el))})});
document.getElementById('next').onclick=()=>{const r=[...document.querySelectorAll('.row[data-key]')].find(r=>!V[r.dataset.key]);
 if(r)r.scrollIntoView({block:'center'})};
fetch('/verdicts').then(r=>r.json()).then(d=>{Object.assign(V,d);
 document.querySelectorAll('.row[data-key]').forEach(paint);prog()});
</script></body></html>"""


def finalize(round_dir: Path) -> dict:
    round_dir = Path(round_dir)
    files = json.loads((round_dir / "files.json").read_text())
    vpath = round_dir / "verdicts.json"
    verdicts = json.loads(vpath.read_text()) if vpath.is_file() else {}
    gold_min = settings()["gold_min"]
    out = {}
    for f in files:
        good = bad = 0
        pending = 0
        for it in f["items"]:
            v = verdicts.get(it["key"])
            if v is None:
                pending += 1
                continue
            n_cells = sum(1 for c in it["cells"] if _norm(c))
            tags = v["tags"]
            if tags[0] == "ok":
                good += n_cells
                continue
            cols = [int(t[1:]) for t in tags if t.startswith("c")]
            wrong = len(cols) if cols else n_cells  # a Wrong with no columns marked counts the whole row
            wrong = min(wrong, n_cells)
            bad += wrong
            good += n_cells - wrong
        miss = verdicts.get(f["missing_key"])
        miss_ok = miss is not None and miss["tags"][0] == "ok"
        total = good + bad
        score = round(good / total, 4) if total else None
        done = pending == 0 and miss is not None
        out[f["sha"]] = {
            "file_url": f["url"], "public_body_id": f["body"], "pdf_extractor": f["extractor"],
            "cell_score": score, "rows_pending": pending + (miss is None),
            "rows_missing": None if miss is None else not miss_ok,
            "good_control": bool(done and score is not None and score >= gold_min and miss_ok),
            "complete": done,
        }
    (round_dir / "control_results.json").write_text(json.dumps(out, indent=1) + "\n")
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="control_review")
    ap.add_argument("cmd", choices=["build", "finalize"])
    ap.add_argument("--round-dir", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "build":
        print(build(Path(a.round_dir)))
    else:
        for sha, r in finalize(Path(a.round_dir)).items():
            print(sha[:12], r["public_body_id"], r["pdf_extractor"], r["cell_score"], "GOOD" if r["good_control"] else "no")


if __name__ == "__main__":
    main()
