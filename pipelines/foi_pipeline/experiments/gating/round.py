"""Run a round of competing fixes on a cluster plus controls and gold files; score and pick a winner.

Run from pipelines/foi_pipeline:
  uv run python -m experiments.gating.round --round-dir D --cluster ID --fixes current,force:pdfplumber
"""
import argparse
import hashlib
import json
import statistics
from pathlib import Path

from experiments.gating.paths import (BAKEOFF, GATING, PDF_CACHE, SCRATCH, content_sha, pdf_bytes,
                                      settings)
from experiments.gating.compare import agreement, gold_score, independent, load_gold  # noqa: E402
from experiments.gating.downstream import default_gate, item_for, run_downstream, transform_index  # noqa: E402
from experiments.gating.extract_cache import get_rows  # noqa: E402
from experiments.gating.fixes import FIX_KINDS, family_of, get, load_round_fixes  # noqa: E402
from experiments.gating.scope import FileStat, file_stats  # noqa: E402
from steps.transform_disclosure_files.process import CANDIDATE_ORDER  # noqa: E402


def pick_controls(stats: dict[str, FileStat], n: int = 10, cache_dir: Path = PDF_CACHE) -> list[str]:
    queues: dict[str, list[str]] = {name: [] for name in CANDIDATE_ORDER}
    for url, s in stats.items():
        if s.file_type != "pdf" or s.gated or s.errors != 0 or s.records < 20:
            continue
        if s.pdf_extractor not in queues:
            continue
        data = pdf_bytes(url, cache_dir)
        if data is None or load_gold(content_sha(data)) is not None:
            continue
        queues[s.pdf_extractor].append(url)
    for q in queues.values():
        q.sort(key=lambda u: hashlib.sha256(u.encode("utf-8")).hexdigest())
    picked: list[str] = []
    bodies: set = set()
    while len(picked) < n and any(queues.values()):
        for name in CANDIDATE_ORDER:
            q = queues[name]
            while q:
                url = q.pop(0)
                body = stats[url].public_body_id if stats[url].public_body_id is not None else url
                if body in bodies:
                    continue
                bodies.add(body)
                picked.append(url)
                break
            if len(picked) >= n:
                break
    return picked


def resolved(per_file: dict, fix: str, cluster_gold: float | None, s: dict) -> bool | None:
    f = per_file[fix]
    ba = f.get("best_agreement")
    if not f.get("gate_pass") or ba is None or ba < s["agreement_min"] or f.get("override_bound"):
        return False
    if cluster_gold is None:
        return None
    return cluster_gold >= s["gold_min"]


def control_worse(new: dict, base: dict) -> bool:
    if new.get("status", "ok") != "ok":
        return True
    if base.get("gate_pass") and not new.get("gate_pass"):
        return True
    if new.get("records", 0) < base.get("records", 0) or new.get("errors", 0) > base.get("errors", 0):
        return True
    ng, bg = new.get("gold"), base.get("gold")
    return ng is not None and bg is not None and ng < bg - 0.01


def pick_winner(fix_rows: list[dict]) -> str | None:
    ok = [r for r in fix_rows if not r["disqualified"] and r["files_gate_pass"] > 0]
    others = [r for r in ok if r["fix"] != "current"]
    pool = others or ok
    if not pool:
        return None

    def key(r):
        g = r.get("gold_accuracy")
        a = r.get("agreement")
        kind = FIX_KINDS.index(r["kind"]) if r["kind"] in FIX_KINDS else len(FIX_KINDS)
        return (-(g if g is not None else -1.0), a is None, -(a if a is not None else 0.0), kind)

    return sorted(pool, key=key)[0]["fix"]


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


def run_round(round_dir: Path, cluster: str, cluster_urls: list[str], fix_names: list[str],
              control_urls: list[str], gold_urls: list[str], cluster_gold_sha: str | None = None) -> dict:
    round_dir = Path(round_dir)
    round_dir.mkdir(parents=True, exist_ok=True)
    s = settings()
    stored = transform_index()
    stats = file_stats()
    fixes = {n: get(n) for n in fix_names}
    run_names = list(fix_names)
    for n in fix_names:  # base fixes run anyway, for the controls
        b = fixes[n].base
        if b not in run_names:
            fixes[b] = get(b)
            run_names.append(b)

    roles: dict[str, str] = {}
    for urls, role in ((control_urls, "control"), (gold_urls, "gold"), (cluster_urls, "cluster")):
        for u in urls:
            roles[u] = role  # cluster wins, then gold, then control
    data = {u: pdf_bytes(u) for u in roles}
    files: dict[str, dict] = {}
    for u, role in roles.items():
        st = stats.get(u)
        it = stored.get(u, {})
        sha = content_sha(data[u]) if data[u] is not None else None
        files[u] = {"role": role, "sha256": sha,
                    "public_body_id": it.get("public_body_id", st.public_body_id if st else None),
                    "name": st.name if st else it.get("name") or u.rsplit("/", 1)[-1], "fixes": {}}
    golds = {u: (load_gold(f["sha256"]) if f["sha256"] else None) for u, f in files.items()}
    cg_url = next((u for u, f in files.items() if cluster_gold_sha and f["sha256"] == cluster_gold_sha), None)

    rows: dict[str, dict[str, list | None]] = {}
    for name in run_names:
        fix = fixes[name]
        rows[name] = {}
        items, ok_urls = [], []
        for u in roles:
            if data[u] is None or u not in stored:
                files[u]["fixes"][name] = {"status": "no_bytes", "seconds": 0.0, "family": None}
                rows[name][u] = None
                continue
            ex = get_rows(fix, u, data[u], stored[u])
            rows[name][u] = ex.rows
            files[u]["fixes"][name] = {"status": ex.status, "seconds": ex.seconds,
                                       "family": family_of(fix, stored[u])}
            if ex.status == "ok":
                items.append(item_for(stored[u], ex.rows, name))
                ok_urls.append(u)
        outcomes = run_downstream(items, name, SCRATCH, fix.gate or default_gate) if items else {}
        for u in roles:
            f = files[u]["fixes"][name]
            o = outcomes.get(u)
            f.update(gate_pass=bool(o.gate_pass) if o else False,
                     failed_checks=list(o.failed_checks) if o else [],
                     records=o.records if o else 0, errors=o.errors if o else 0,
                     override_bound=bool(o.override_bound) if o else False)
            g = golds[u]
            f["gold"] = gold_score(rows[name][u], g) if g is not None else None
            f["best_agreement"] = None
            f["agrees_with"] = None
            f["resolved"] = None

    cluster_gold: dict[str, float | None] = {
        n: (files[cg_url]["fixes"][n]["gold"] if cg_url else None) for n in run_names}
    for u, f in files.items():
        if f["role"] != "cluster":
            continue
        for n in fix_names:
            best, with_ = None, None
            for m in fix_names:
                if m == n:
                    continue
                if not independent(f["fixes"][n].get("family"), f["fixes"][m].get("family")):
                    continue
                if f["fixes"][n]["status"] != "ok" or f["fixes"][m]["status"] != "ok":
                    continue
                ag = agreement(rows[n][u], rows[m][u])
                if ag is not None and (best is None or ag > best):
                    best, with_ = ag, m
            f["fixes"][n]["best_agreement"] = best
            f["fixes"][n]["agrees_with"] = with_
            f["fixes"][n]["resolved"] = resolved(f["fixes"], n, cluster_gold[n], s)

    cl = [u for u, f in files.items() if f["role"] == "cluster"]
    ct = [u for u, f in files.items() if f["role"] == "control"]
    gd = [u for u, f in files.items() if f["role"] == "gold"]
    fix_rows = []
    for n in fix_names:
        fx, base = fixes[n], fixes[n].base
        fo = {u: files[u]["fixes"][n] for u in files}
        worse = sum(1 for u in ct if n != base and control_worse(fo[u], files[u]["fixes"][base]))
        differ = sum(1 for u in ct if n != base and rows[n][u] != rows[base][u])
        gold_urls_used = gd + ([cg_url] if cg_url and cg_url not in gd else [])
        recovered = sum(fo[u]["records"] - (stats[u].records if u in stats else 0)
                        for u in cl if fo[u]["gate_pass"])
        secs = [fo[u]["seconds"] for u in files if fo[u]["status"] == "ok"]
        fix_rows.append({
            "fix": n, "kind": fx.kind, "scope": fx.scope,
            "files_resolved": sum(1 for u in cl if fo[u]["resolved"] is True),
            "files_gate_pass": sum(1 for u in cl if fo[u]["gate_pass"]),
            "records_recovered": recovered,
            "errors_after": sum(fo[u]["errors"] for u in cl),
            "gold_accuracy": _mean([fo[u]["gold"] for u in gold_urls_used]),
            "cluster_gold": cluster_gold[n],
            "agreement": _mean([fo[u]["best_agreement"] for u in cl]),
            "controls_worse": worse, "controls_differ": differ,
            "not_run": sum(1 for u in files if fo[u]["status"] != "ok"),
            "seconds_per_file": round(statistics.median(secs), 3) if secs else None,
            "disqualified": fx.scope == "global" and worse > 0,
        })
    res = {"cluster": cluster, "settings": s, "files": files, "fix_rows": fix_rows,
           "winner": pick_winner(fix_rows)}
    (round_dir / "results.json").write_text(json.dumps(res, indent=1))
    (round_dir / "TABLE.md").write_text(_table(res))
    return res


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, list):
        return ", ".join(map(str, v))
    return str(v)


def _md(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(_cell(c).replace("|", "/") for c in r) + " |" for r in rows]
    return "\n".join(out) + "\n"


def _table(res: dict) -> str:
    cols = ["fix", "kind", "scope", "files_resolved", "files_gate_pass", "records_recovered", "errors_after",
            "gold_accuracy", "cluster_gold", "agreement", "controls_worse", "controls_differ", "not_run",
            "seconds_per_file", "disqualified"]
    text = f"# Round: {res['cluster']}\n\nWinner: {res['winner']}\n\n"
    text += _md(cols, [[r[c] for c in cols] for r in res["fix_rows"]]) + "\n"
    per = []
    for u, f in res["files"].items():
        for n, x in f["fixes"].items():
            if n not in {r["fix"] for r in res["fix_rows"]}:
                continue
            per.append([f"{f['name']} ({f['role']})", n, x["status"], x.get("gate_pass"),
                        x.get("failed_checks"), x.get("records"), x.get("errors"),
                        x.get("best_agreement"), x.get("agrees_with"), x.get("resolved")])
    text += _md(["file", "fix", "status", "gate", "failed checks", "records", "errors",
                 "best agreement", "agrees with", "resolved"], per)
    return text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--round-dir", required=True, type=Path)
    ap.add_argument("--cluster", required=True)
    ap.add_argument("--fixes", required=True)
    ap.add_argument("--fixes-module", type=Path)
    ap.add_argument("--cluster-gold")
    a = ap.parse_args(argv)
    if a.fixes_module:
        load_round_fixes(a.fixes_module)
    ledger = json.loads((GATING / "ledger.json").read_text())
    cluster_urls = [e["file_url"] for e in ledger if e["cluster"] == a.cluster and e["status"] != "no_bytes"]
    controls = json.loads((GATING / "controls.json").read_text())
    control_urls = [c["file_url"] if isinstance(c, dict) else c for c in controls]
    gold_urls = [x["file_url"] for x in json.loads((BAKEOFF / "sample.json").read_text())
                 if x.get("on_disk") and load_gold(x["sha256"]) is not None]
    res = run_round(a.round_dir, a.cluster, cluster_urls, a.fixes.split(","), control_urls, gold_urls,
                    a.cluster_gold)
    print(f"winner: {res['winner']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
