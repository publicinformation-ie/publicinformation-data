"""Review page for source-file triage. build(round_dir) writes review/index.html and results.json.

results.json ({"files": {url: {"sha256"}}}) exists only so serve.py's /pdf/<sha>.pdf route works unchanged.
"""
import json
from pathlib import Path

from experiments.gating.ledger import TRIAGE_CLASSES
from experiments.gating.review_page import CSS, _e
from experiments.gating.triage import load_proposals

# Page-local JS: each row keeps its selected classes as buttons with class "sel"; every click and every save
# posts the full set plus the note text, so a save can never drop a picked tag.
JS = """<script>
function row(b){return b.closest('[data-key]')}
function send(d){var t=d.querySelector('input[type=text]').value;
var tags=[].map.call(d.querySelectorAll('button.sel'),function(x){return x.dataset.c});
fetch('/verdict',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({key:d.dataset.key,text:t,tags:tags})}).then(function(r){
document.getElementById('st').textContent=r.ok?'saved':'save failed'})}
function pick(b){b.classList.toggle('sel');send(row(b))}
function sv(b){send(row(b))}
fetch('/verdicts').then(function(r){return r.json()}).then(function(v){
document.querySelectorAll('[data-key]').forEach(function(d){var x=v[d.dataset.key];if(!x)return;
d.querySelector('input[type=text]').value=x.text;
d.querySelectorAll('button[data-c]').forEach(function(b){if((x.tags||[]).indexOf(b.dataset.c)>=0)b.classList.add('sel')})})});
</script>"""

ORDER = ("not_foi_log", "small_log", "scan", "hard_table")


def _line(e: dict, p: dict | None) -> str:
    sha = e.get("sha256")
    if e.get("image"):
        assert e["image"].startswith("review/"), e["image"]
    img = f"<img loading=lazy src='{_e(e['image'][len('review/'):])}'><br>" if e.get("image") else ""
    pdf = f"<a href='/pdf/{_e(sha)}.pdf'>PDF</a>" if sha else ""
    if p:
        prop = f"proposed <b>{_e(p['class'])}</b>: {_e(p['reason'])}"
    else:
        prop = f"unreadable: {_e(e.get('unreadable'))}"
    btns = "".join(f"<button type=button data-c='{_e(c)}' onclick='pick(this)'>{_e(c)}</button>" for c in TRIAGE_CLASSES)
    return (f"<div class=f data-key='{_e('file:' + e['file_url'])}'>"
            f"<b>{_e(e.get('public_body_id', ''))} {_e(e.get('name'))}</b> "
            f"<span class=why>{_e(e['file_url'])} - link text: {_e(e.get('link_text'))}</span><br>"
            f"{img}{pdf}<br><span class=why>{prop}</span><br>"
            f"<input type=text placeholder='note'>{btns}"
            f"<button type=button onclick='sv(this)'>save</button></div>")


def build(round_dir: Path) -> Path:
    round_dir = Path(round_dir)
    inputs = json.loads((round_dir / "inputs.json").read_text())
    props = load_proposals(round_dir)

    def key(e):
        p = props.get(e["file_url"])
        return (ORDER.index(p["class"]) if p else len(ORDER), e.get("public_body_id") or 0)

    ordered = sorted(inputs, key=key)
    (round_dir / "results.json").write_text(json.dumps(
        {"files": {e["file_url"]: {"sha256": e["sha256"]} for e in inputs if e.get("sha256")}}, indent=1))
    body = [f"<h2>Source-file triage ({len(ordered)} files)</h2><p>not_foi_log proposals first: tag each. "
            f"Other groups need only spot checks. <span id=st></span></p>"]
    body += [_line(e, props.get(e["file_url"])) for e in ordered]
    review = round_dir / "review"
    review.mkdir(parents=True, exist_ok=True)
    idx = review / "index.html"
    idx.write_text("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
                   f"<title>Source-file triage</title><style>{CSS}</style>" + "".join(body)
                   + JS)
    return idx
