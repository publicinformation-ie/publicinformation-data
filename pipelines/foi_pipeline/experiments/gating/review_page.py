"""Static review page for a round (spec section 9). No external assets; all cell text escaped.

build(round_dir) writes round_dir/review/{index.html, tables/<fix-slug>/<sha>.html, gold.html, crops/}.
"""
import html
import json
from pathlib import Path

from experiments.gating.extract_cache import Extraction, get_rows
from experiments.gating.fixes import get as get_fix, load_round_fixes
from experiments.gating.downstream import transform_index
from experiments.gating.gold_tools import _norm, aligned_row, cells_to_check, crop_cell
from experiments.gating.compare import load_gold
from experiments.gating.paths import pdf_bytes

TAGS = ["fine", "shifted columns", "merged cells", "split cells", "wrong header", "gate wrong", "not a table"]
CSS = ("body{font:16px system-ui,sans-serif;margin:8px;max-width:60em}.f{border:1px solid #bbb;border-radius:6px;"
       "padding:8px;margin:8px 0}.rep{border-color:#c60;background:#fff7ee}.why{color:#555;font-size:14px}"
       "input[type=text],textarea{width:100%;box-sizing:border-box;font-size:16px;padding:6px}"
       "button{font-size:15px;padding:6px 10px;margin:2px}a{margin-right:10px}table{border-collapse:collapse}"
       "td,th{border:1px solid #999;padding:2px 5px}.diff{background:#fc8}img{max-width:100%}.ok{color:#080}")
JS = """<script>
function save(key,text,tags){fetch('/verdict',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({key:key,text:text,tags:tags||[]})}).then(r=>{document.getElementById('st').textContent=r.ok?'saved':'save failed'})}
function tag(b){var i=b.parentNode.querySelector('input[type=text]');i.value=(i.value?i.value+', ':'')+b.dataset.t}
function sv(b){var d=b.parentNode;var i=d.querySelector('input[type=text],textarea');var t=i.value;
save(d.dataset.key,t,TAGS.filter(x=>t.indexOf(x)>=0))}
function pick(b,v){var d=b.parentNode;var i=d.querySelector('input[type=text]');save(d.dataset.key,i.value,[v])}
var TAGS=%s;
fetch('/verdicts').then(r=>r.json()).then(v=>{document.querySelectorAll('[data-key]').forEach(d=>{
var x=v[d.dataset.key];if(x){var i=d.querySelector('input[type=text],textarea');if(i)i.value=x.text;
if(x.tags&&x.tags.length&&!x.text){}}})});
</script>"""


def _e(x) -> str:
    return html.escape(str(x), quote=True)


def slug(name: str) -> str:
    return name.replace(":", "_").replace("+", "_").replace("/", "_")


def _rows_for(name: str, url: str, data, stored: dict):
    ex = get_rows(get_fix(name), url, data or b"", stored)
    return ex.rows if ex.status == "ok" else None


def _table_html(title: str, rows: list[list], ref_rows: list[list] | None) -> str:
    out = [f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
           f"<style>{CSS}</style><h3>{_e(title)}</h3><p><a href='../../index.html'>back</a></p><table>"]
    for r in rows:
        tds = []
        for c, cell in enumerate(r):
            diff = False
            if ref_rows is not None and any(_norm(x) for x in r):
                ar = aligned_row(r, ref_rows)
                diff = ar is None or c >= len(ar) or ar[c] != _norm(cell)
            tds.append(f"<td{' class=\"diff\"' if diff else ''}>{_e(cell)}</td>")
        out.append("<tr>" + "".join(tds) + "</tr>")
    out.append("</table>")
    return "".join(out)


def _tag_buttons() -> str:
    return "".join(f"<button type=button data-t='{_e(t)}' onclick='tag(this)'>{_e(t)}</button>" for t in TAGS)


def _line(url: str, f: dict, why: str, rep: bool) -> str:
    links = "".join(
        f"<a href='tables/{slug(n)}/{_e(f['sha256'])}.html'>{_e(n)} (gate {'ok' if x.get('gate_pass') else 'fail'}, "
        f"{x.get('records', 0)} rec, {x.get('errors', 0)} err)</a>" for n, x in f["fixes"].items())
    return (f"<div class='f{' rep' if rep else ''}' data-key='{_e('file:' + url)}'>"
            f"<b>{_e(f.get('public_body_id', ''))} {_e(f['name'])}</b>{' <b>[representative]</b>' if rep else ''}"
            f" <span class=why>{_e(f['role'])} - {_e(why)}</span><br>"
            f"<a href='/pdf/{_e(f['sha256'])}.pdf'>PDF</a>{links}<br>"
            f"<input type=text placeholder='verdict'>{_tag_buttons()}"
            f"<button type=button onclick='sv(this)'>save</button></div>")


def _changed_by(f: dict) -> str | None:
    for n, x in f["fixes"].items():
        try:
            base = get_fix(n).base
        except KeyError:
            base = "current"
        b = f["fixes"].get(base)
        if n == base or b is None:
            continue
        if (x.get("gate_pass"), x.get("records"), x.get("errors")) != (b.get("gate_pass"), b.get("records"), b.get("errors")):
            return n
    return None


def build(round_dir: Path, representative_url: str | None = None, cluster_gold_sha: str | None = None) -> Path:
    round_dir = Path(round_dir)
    if (round_dir / "fixes.py").is_file():
        load_round_fixes(round_dir / "fixes.py")
    res = json.loads((round_dir / "results.json").read_text())
    files = res["files"]
    review = round_dir / "review"
    stored = transform_index()
    data = {u: pdf_bytes(u) for u in files}
    cache = {}
    for u, f in files.items():
        for n in f["fixes"]:
            cache[(u, n)] = _rows_for(n, u, data[u], stored.get(u, {}))
    for u, f in files.items():
        for n, x in f["fixes"].items():
            rows = cache[(u, n)]
            if rows is None:
                continue
            ref = x.get("agrees_with") or "current"
            ref_rows = cache.get((u, ref)) if ref in f["fixes"] else None
            p = review / "tables" / slug(n) / f"{f['sha256']}.html"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(_table_html(f"{f['name']} - {n}", rows, ref_rows))

    def why(f):
        fails = sorted({c for x in f["fixes"].values() for c in x.get("failed_checks", [])})
        return "failed: " + ", ".join(fails) if fails else "no failed checks"

    cluster = [u for u, f in files.items() if f["role"] == "cluster"]
    changed = {u: _changed_by(f) for u, f in files.items() if f["role"] != "cluster"}
    ctl = [u for u, f in files.items() if f["role"] == "control" and changed[u]]
    rest = [u for u in files if u not in cluster and u not in ctl]
    body = [f"<h2>Cluster {_e(res['cluster'])}</h2><p>Asked: (1) name the fault for the representative file, "
            f"(2) check the disputed gold cells<a href='gold.html'> (gold page)</a>, (3) ship yes or no. "
            f"<span id=st></span></p>"]
    body += [_line(u, files[u], why(files[u]), u == representative_url) for u in cluster]
    body += [_line(u, files[u], f"control changed by {changed[u]}", False) for u in ctl]
    if rest:
        body.append(f"<details><summary>{len(rest)} other files</summary>")
        body += [_line(u, files[u], why(files[u]), False) for u in rest]
        body.append("</details>")
    body.append(f"<div class=f data-key='__ship__'><b>Ship {_e(res.get('winner'))} for this cluster?</b><br>"
                f"<button type=button onclick=\"pick(this,'yes')\">yes</button>"
                f"<button type=button onclick=\"pick(this,'no')\">no</button>"
                f"<textarea placeholder=note></textarea></div>")
    review.mkdir(parents=True, exist_ok=True)
    idx = review / "index.html"
    idx.write_text("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
                   f"<title>Round {_e(res['cluster'])}</title><style>{CSS}</style>" + "".join(body)
                   + JS.replace("%s", json.dumps(TAGS)))
    if cluster_gold_sha:
        _build_gold(round_dir, files, cache, data, cluster_gold_sha)
    return idx


def _build_gold(round_dir: Path, files: dict, cache: dict, data: dict, sha: str) -> None:
    gold = load_gold(sha)
    url = next((u for u, f in files.items() if f["sha256"] == sha), None)
    if gold is None or url is None:
        return
    fix_rows = {n: cache[(url, n)] for n in files[url]["fixes"]}
    cells = cells_to_check(gold, fix_rows, seed=sha)
    review = round_dir / "review"
    body = ["<h2>Gold cells</h2><p><a href='index.html'>back</a> <span id=st></span></p>"]
    for c in cells:
        img = ""
        if data.get(url):
            crop_cell(data[url], {**_find_rect(gold, c), "page": _find_rect(gold, c)["page"]},
                      review / "crops" / f"{c['row']}-{c['col']}.png")
            img = f"<img src='crops/{c['row']}-{c['col']}.png'>"
        vals = "".join(f"<br>{_e(n)}: <code>{_e(v)}</code>" for n, v in c["values"].items())
        body.append(f"<div class=f data-key='gold:{c['row']}:{c['col']}'>{img}<br>gold: <code>{_e(c['gold'])}</code>"
                    f"{vals}<br><span class=why>{_e(c['reason'])}</span><br>"
                    f"<input type=text placeholder='correction'>"
                    f"<button type=button onclick=\"pick(this,'ok')\">ok</button>"
                    f"<button type=button onclick=\"pick(this,'wrong')\">wrong</button></div>")
    (review / "gold.html").write_text("<!doctype html><meta charset=utf-8><meta name=viewport "
                                      f"content='width=device-width'><style>{CSS}</style>" + "".join(body)
                                      + JS.replace("%s", json.dumps(TAGS)))


def _find_rect(gold: dict, c: dict) -> dict:
    return next(x for x in gold["cells"] if x["row"] == c["row"] and x["col"] == c["col"])
