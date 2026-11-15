import hashlib
import json

import pytest

from experiments.gating import round as rnd
from experiments.gating.downstream import FileOutcome
from experiments.gating.extract_cache import Extraction
from experiments.gating.fixes import REGISTRY, Fix
from experiments.gating.paths import content_sha
from experiments.gating.scope import FileStat
from steps.transform_disclosure_files.process import CANDIDATE_ORDER

S = {"agreement_min": 0.90, "gold_min": 0.95}


def f(gate=True, agr=0.9, override_bound=False):
    return {"x": {"gate_pass": gate, "best_agreement": agr, "override_bound": override_bound}}


def _stat(url, body, ext, records=50, errors=0, gated=False, ftype="pdf"):
    return FileStat(file_url=url, public_body_id=body, name=url, file_type=ftype, pdf_extractor=ext,
                    gated=gated, records=records, errors=errors)


def test_pick_controls_is_deterministic_one_per_body_spread_over_extractors(tmp_path):
    stats = {}
    for i in range(12):
        url = f"https://x.test/{i}.pdf"
        ext = CANDIDATE_ORDER[i % 2]
        stats[url] = _stat(url, i // 2, ext)  # two files per body
        (tmp_path / f"{hashlib.sha256(url.encode()).hexdigest()}.bytes").write_bytes(b"pdf%d" % i)
    bad = {"g": _stat("g", 99, CANDIDATE_ORDER[0], gated=True), "e": _stat("e", 98, CANDIDATE_ORDER[0], errors=1),
           "s": _stat("s", 97, CANDIDATE_ORDER[0], records=5), "n": _stat("n", 96, CANDIDATE_ORDER[0]),
           "x": _stat("x", 95, CANDIDATE_ORDER[0], ftype="xlsx")}
    stats.update(bad)
    a = rnd.pick_controls(stats, n=4, cache_dir=tmp_path)
    assert a == rnd.pick_controls(stats, n=4, cache_dir=tmp_path)
    assert len(a) == 4
    assert not set(a) & set(bad)
    assert len({stats[u].public_body_id for u in a}) == 4
    assert {stats[u].pdf_extractor for u in a} == set(CANDIDATE_ORDER[:2])
    assert stats[a[0]].pdf_extractor == CANDIDATE_ORDER[0] and stats[a[1]].pdf_extractor == CANDIDATE_ORDER[1]


def test_pick_controls_skips_gold(tmp_path, monkeypatch):
    url = "https://x.test/a.pdf"
    (tmp_path / f"{hashlib.sha256(url.encode()).hexdigest()}.bytes").write_bytes(b"abc")
    monkeypatch.setattr(rnd, "load_gold", lambda sha: {"g": 1})
    assert rnd.pick_controls({url: _stat(url, 1, CANDIDATE_ORDER[0])}, cache_dir=tmp_path) == []


def test_resolved_requires_gate_agreement_and_gold():
    assert rnd.resolved(f(gate=True, agr=0.92), "x", 0.96, S) is True
    assert rnd.resolved(f(gate=True, agr=0.92), "x", None, S) is None
    assert rnd.resolved(f(gate=True, agr=0.92), "x", 0.94, S) is False
    assert rnd.resolved(f(gate=True, agr=None), "x", 0.99, S) is False
    assert rnd.resolved(f(gate=False, agr=0.99), "x", 0.99, S) is False
    assert rnd.resolved(f(gate=True, agr=0.99, override_bound=True), "x", 0.99, S) is False


def test_control_worse_cases():
    base = dict(status="ok", gate_pass=True, records=10, errors=1, gold=0.9)
    assert rnd.control_worse(dict(base), base) is False
    assert rnd.control_worse({**base, "gate_pass": False}, base) is True
    assert rnd.control_worse({**base, "records": 9}, base) is True
    assert rnd.control_worse({**base, "errors": 2}, base) is True
    assert rnd.control_worse({**base, "gold": 0.85}, base) is True
    assert rnd.control_worse({**base, "gold": 0.895}, base) is False
    assert rnd.control_worse({**base, "gold": None}, base) is False
    assert rnd.control_worse({**base, "status": "error"}, base) is True
    assert rnd.control_worse({**base, "records": 20, "gate_pass": True}, {**base, "gate_pass": False}) is False


def _row(fix, kind, scope="routed", gp=1, gold=0.9, agr=0.9, worse=0, **kw):
    return dict(fix=fix, kind=kind, scope=scope, files_gate_pass=gp, gold_accuracy=gold, agreement=agr,
                controls_worse=worse, disqualified=scope == "global" and worse > 0, **kw)


def test_pick_winner_order():
    assert rnd.pick_winner([_row("a", "fork", gold=0.9), _row("b", "config", gold=0.95)]) == "b"
    assert rnd.pick_winner([_row("a", "fork", agr=0.9), _row("b", "config", agr=0.8)]) == "a"
    assert rnd.pick_winner([_row("a", "fork", agr=None), _row("b", "config", agr=0.8)]) == "b"
    assert rnd.pick_winner([_row("a", "fork"), _row("b", "config")]) == "b"
    assert rnd.pick_winner([_row("current", "baseline", gold=1.0), _row("a", "fork", gold=0.5)]) == "a"
    assert rnd.pick_winner([_row("current", "baseline")]) == "current"
    assert rnd.pick_winner([_row("a", "fork", gp=0), _row("b", "config", gp=0)]) is None
    assert rnd.pick_winner([]) is None


def test_global_fix_with_worse_control_is_disqualified_routed_is_not(tmp_path, monkeypatch):
    res = _run(tmp_path, monkeypatch, scopes=("global", "routed"), control_records_new=5)
    rows = {r["fix"]: r for r in res["fix_rows"]}
    assert rows["tg"]["controls_worse"] == 1 and rows["tg"]["disqualified"] is True
    assert rows["tr"]["controls_worse"] == 1 and rows["tr"]["disqualified"] is False
    assert rows["tg"]["controls_differ"] == 1
    assert res["winner"] == "tr"


CL, CT, GD = "https://x.test/cl.pdf", "https://x.test/ct.pdf", "https://x.test/gd.pdf"
BYTES = {CL: b"cl", CT: b"ct", GD: b"gd"}
GOOD = [["Ref", "Date"], ["1", "01/01/2020"]]
OTHER = [["Ref", "Date"], ["2", "02/02/2020"]]


def _run(tmp_path, monkeypatch, scopes=("routed",), control_records_new=50, not_extracted=None):
    names = ["current"] + [f"t{'g' if s == 'global' else 'r'}" for s in scopes]
    for n, s in zip(names[1:], scopes):
        monkeypatch.setitem(REGISTRY, n, Fix(name=n, kind="fork", scope=s, family="docling"))
    monkeypatch.setitem(REGISTRY, "current", Fix(name="current", kind="baseline"))
    stored = {u: {"file_url": u, "public_body_id": i, "name": u, "rows": GOOD, "pdf_extractor": "pdfplumber"}
              for i, u in enumerate(BYTES)}
    monkeypatch.setattr(rnd, "transform_index", lambda: stored)
    monkeypatch.setattr(rnd, "file_stats", lambda: {u: _stat(u, i, "pdfplumber", records=10) for i, u in enumerate(BYTES)})
    monkeypatch.setattr(rnd, "pdf_bytes", lambda u, *a: BYTES[u])
    monkeypatch.setattr(rnd, "settings", lambda: S)
    gold = {"cells": []}
    monkeypatch.setattr(rnd, "load_gold", lambda sha: gold if sha == content_sha(BYTES[GD]) else None)
    monkeypatch.setattr(rnd, "gold_score", lambda rows, g: 0.97 if rows == GOOD else 0.5)

    def fake_rows(fix, url, data, item, *a):
        if fix.name == not_extracted and url == CL:
            return Extraction(None, "not_extracted", 0.0, None)
        rows = GOOD if fix.name == "current" or url != CT else OTHER
        return Extraction(rows, "ok", 1.0, None)

    def fake_down(items, variant, scratch=None, gate=None, **kw):
        assert len({i["file_url"] for i in items}) == len(items)
        out = {}
        for it in items:
            u = it["file_url"]
            rec = control_records_new if (u == CT and variant != "current") else 50
            out[u] = FileOutcome(u, True, [], {}, rec, 0, {}, False)
        return out

    monkeypatch.setattr(rnd, "get_rows", fake_rows)
    monkeypatch.setattr(rnd, "run_downstream", fake_down)
    monkeypatch.setattr(rnd, "agreement", lambda a, b: 0.95 if a == b else 0.5)
    return rnd.run_round(tmp_path / "r", "c1", [CL], names[1:], [CT], [GD], content_sha(BYTES[GD]))


def test_not_extracted_file_is_counted_and_round_completes(tmp_path, monkeypatch):
    res = _run(tmp_path, monkeypatch, not_extracted="tr")
    row = res["fix_rows"][0]
    assert row["not_run"] == 1
    cf = res["files"][CL]["fixes"]["tr"]
    assert cf["status"] == "not_extracted" and cf["gate_pass"] is False and cf["records"] == 0
    assert (tmp_path / "r" / "results.json").is_file()


def test_records_recovered_subtracts_published_records(tmp_path, monkeypatch):
    res = _run(tmp_path, monkeypatch)
    assert res["fix_rows"][0]["records_recovered"] == 40  # 50 now, 10 published
    assert res["fix_rows"][0]["gold_accuracy"] == 0.97


def test_results_json_and_table_md_written(tmp_path, monkeypatch):
    res = _run(tmp_path, monkeypatch)
    d = tmp_path / "r"
    on_disk = json.loads((d / "results.json").read_text())
    assert on_disk["cluster"] == "c1" and on_disk["winner"] == res["winner"] == "tr"
    assert set(on_disk["files"][CL]) >= {"role", "sha256", "public_body_id", "name", "fixes"}
    assert on_disk["files"][CL]["role"] == "cluster" and on_disk["files"][GD]["role"] == "gold"
    fx = on_disk["files"][CL]["fixes"]["tr"]
    assert set(fx) >= {"status", "seconds", "family", "gate_pass", "failed_checks", "records", "errors",
                       "override_bound", "gold", "best_agreement", "agrees_with", "resolved"}
    assert "current" in on_disk["files"][CT]["fixes"]  # base run for controls
    assert [r["fix"] for r in on_disk["fix_rows"]] == ["tr"]
    t = (d / "TABLE.md").read_text()
    assert "files_resolved" in t and "best agreement" in t
