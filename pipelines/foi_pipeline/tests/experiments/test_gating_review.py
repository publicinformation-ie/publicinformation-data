import http.client
import json
import threading

import pytest

from experiments.gating import review_page as rp
from experiments.gating import serve as sv
from experiments.gating.fixes import Fix

U1, U2, U3 = "https://x.test/a.pdf", "https://x.test/b.pdf", "https://x.test/c.pdf"
S1, S2, S3 = "a" * 64, "b" * 64, "c" * 64
ROWS = {
    "current": [["Ref", "Date"], ["FOI-1", "01/01/2023"], ["FOI-2", "<script>x</script>"]],
    "force:docling": [["Ref", "Date"], ["FOI-1", "01/01/2023"], ["FOI-2", "02/02/2023"]],
}


def _fx(status="ok", gate=True, rec=3, err=0, checks=(), agrees=None):
    return {"status": status, "gate_pass": gate, "failed_checks": list(checks), "records": rec,
            "errors": err, "best_agreement": 0.9, "agrees_with": agrees, "resolved": False, "family": "x"}


@pytest.fixture
def round_dir(tmp_path, monkeypatch):
    res = {"cluster": "c1", "settings": {}, "winner": "force:docling",
           "fix_rows": [{"fix": "current"}, {"fix": "force:docling"}],
           "files": {
               U1: {"role": "cluster", "sha256": S1, "public_body_id": 1, "name": "A body",
                    "fixes": {"current": _fx(gate=False, checks=["contamination"]),
                              "force:docling": _fx(agrees="current")}},
               U2: {"role": "control", "sha256": S2, "public_body_id": 2, "name": "B body",
                    "fixes": {"current": _fx(rec=5), "force:docling": _fx(rec=2)}},
               U3: {"role": "control", "sha256": S3, "public_body_id": 3, "name": "C body",
                    "fixes": {"current": _fx(), "force:docling": _fx()}}}}
    (tmp_path / "results.json").write_text(json.dumps(res))
    monkeypatch.setattr(rp, "get_fix", lambda n: Fix(name=n, kind="baseline" if n == "current" else "candidate"))
    monkeypatch.setattr(rp, "get_rows", lambda fix, u, d, st, *a, **k: rp.Extraction(ROWS[fix.name], "ok"))
    monkeypatch.setattr(rp, "transform_index", lambda: {U1: {}, U2: {}, U3: {}})
    monkeypatch.setattr(rp, "pdf_bytes", lambda u: b"%PDF")
    return tmp_path


def test_index_lists_cluster_files_with_pdf_and_fix_links(round_dir):
    idx = rp.build(round_dir, representative_url=U1)
    html = idx.read_text()
    assert idx == round_dir / "review" / "index.html"
    assert "A body" in html and f"/pdf/{S1}.pdf" in html
    assert "force:docling (gate ok, 3 rec, 0 err)" in html
    assert "current (gate fail, 3 rec, 0 err)" in html
    assert "control changed by force:docling" in html
    assert "Ship force:docling for this cluster?" in html and "__ship__" in html
    assert "shifted columns" in html and "representative" in html.lower()
    assert html.index("A body") < html.index("B body") < html.index("C body")
    assert (round_dir / "review" / "tables" / "force_docling" / f"{S1}.html").is_file()


def test_cell_text_is_escaped(round_dir):
    rp.build(round_dir)
    t = (round_dir / "review/tables/current" / f"{S1}.html").read_text()
    assert "&lt;script&gt;" in t and "<script>x" not in t


def test_differing_cells_are_highlighted(round_dir):
    rp.build(round_dir)
    t = (round_dir / "review/tables/current" / f"{S1}.html").read_text()
    assert t.count('class="diff"') == 0  # current is its own reference
    t2 = (round_dir / "review/tables/force_docling" / f"{S1}.html").read_text()
    assert t2.count('class="diff"') == 1  # compared with its agrees_with fix


@pytest.fixture
def server(round_dir, monkeypatch):
    rp.build(round_dir)
    monkeypatch.setattr(sv, "pdf_bytes", lambda u: b"%PDF-fake" if u == U1 else None)
    srv = sv.make_server(round_dir, "127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv, round_dir
    srv.shutdown()
    srv.server_close()


def req(srv, method, path, body=None, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1])
    c.request(method, path, body=body, headers=headers or {})
    r = c.getresponse()
    return r.status, r.getheader("Content-Type"), r.read()


def post(srv, obj):
    return req(srv, "POST", "/verdict", json.dumps(obj), {"Content-Type": "application/json"})


def test_post_verdict_persists_and_get_returns_it(server):
    srv, rd = server
    assert post(srv, {"key": "k1", "text": "fine", "tags": ["fine"]})[0] == 200
    st, _, body = req(srv, "GET", "/verdicts")
    v = json.loads(body)["k1"]
    assert st == 200 and v["text"] == "fine" and v["tags"] == ["fine"] and v["saved_at"]
    assert json.loads((rd / "verdicts.json").read_text())["k1"]["text"] == "fine"


def test_verdict_survives_second_save_for_other_key(server):
    srv, _ = server
    post(srv, {"key": "a", "text": "1", "tags": []})
    post(srv, {"key": "b", "text": "2", "tags": []})
    v = json.loads(req(srv, "GET", "/verdicts")[2])
    assert v["a"]["text"] == "1" and v["b"]["text"] == "2"


def test_path_traversal_is_404(server):
    srv, _ = server
    for p in ("/review/../../results.json", "/review/../results.json", "/pdf/../x.pdf",
              f"/pdf/{'d' * 64}.pdf", "/review/%2e%2e/results.json", "/nope"):
        assert req(srv, "GET", p)[0] == 404, p


def test_malformed_post_is_400(server):
    srv, _ = server
    assert req(srv, "POST", "/verdict", "not json")[0] == 400
    assert post(srv, {"text": "x"})[0] == 400
    assert post(srv, {"key": "k", "text": 5, "tags": []})[0] == 400
    assert req(srv, "POST", "/verdict", "x" * 70000)[0] == 400


def test_pdf_served_only_for_round_sha(server):
    srv, _ = server
    st, ct, body = req(srv, "GET", f"/pdf/{S1}.pdf")
    assert (st, ct, body) == (200, "application/pdf", b"%PDF-fake")
    assert req(srv, "GET", f"/pdf/{S2}.pdf")[0] == 404  # in round, but no bytes
    assert req(srv, "GET", "/")[0] == 200


def test_gold_page_has_cells_and_buttons(round_dir, monkeypatch):
    gold = {"columns": ["Ref", "Date"], "rows": [["FOI-2", "02/02/2023"]],
            "cells": [{"row": 0, "col": c, "page": 1, "rect": [0, 0, 1, 1]} for c in range(2)]}
    monkeypatch.setattr(rp, "load_gold", lambda sha: gold)
    monkeypatch.setattr(rp, "crop_cell", lambda data, cell, out, **k: out)
    rp.build(round_dir, cluster_gold_sha=S1)
    g = (round_dir / "review" / "gold.html").read_text()
    assert "gold:0:1" in g and "&lt;script&gt;" in g and ">wrong<" in g and "crops/0-1.png" in g
