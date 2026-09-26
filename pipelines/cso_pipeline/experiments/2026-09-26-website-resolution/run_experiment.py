#!/usr/bin/env python3
"""CSO website-resolution experiment: compare search cascades and judges on the gold set.

Run from the repo root:
    uv run python pipelines/cso_pipeline/experiments/2026-09-26-website-resolution/run_experiment.py --approach seed_only
    uv run python .../run_experiment.py --approach all --judge ollama:gemma4:latest
Paid approaches (haiku, apify, haiku_then_apify) need ANTHROPIC_API_KEY / APIFY_TOKEN.
Raw responses are cached under pipelines/cso_pipeline/cache/ and never re-bought.
"""
import argparse
import importlib.util as _ilu
import json
import sys
from datetime import datetime, timezone
from functools import partial
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_CSO = _HERE.parents[1]
_REPO = _CSO.parents[1]
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_CSO))

from website_eval.website_metrics import load_gold, score  # noqa: E402
from lib.response_cache import ResponseCache  # noqa: E402
from lib.website_decide import OWN_STATUSES, decide  # noqa: E402
from lib.website_judge import judge_cascade  # noqa: E402
from lib.website_probe import probe_url  # noqa: E402
from lib.website_verify import verify_candidates  # noqa: E402

RESULTS = _HERE / "results"
CACHE_DIR = _CSO / "cache"
GOLD = _CSO / "website_eval" / "website_gold.csv"
NORMALIZED = _CSO / "steps" / "normalize_cso_fields" / "output.json"
GOV_IE = _CSO / "steps" / "match_gov_urls" / "output.json"
RESOLVED = _CSO / "steps" / "resolve_website_urls" / "output.json"
FOIGOVIE = _REPO / "pipelines" / "foigovie_pipeline" / "steps" / "apply_overrides" / "output.json"
APPROACHES = ["seed_only", "haiku", "apify", "haiku_then_apify"]
_SETTLED = OWN_STATUSES | {"no_own_site", "defunct"}


def load_approach(name):
    spec = _ilu.spec_from_file_location(f"wr_{name}", _HERE / "approaches" / f"{name}.py")
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_ctx(cache_dir, *, gov_ie, foigovie, prior, refresh):
    return {"cache_dir": Path(cache_dir), "gov_ie": gov_ie, "foigovie": foigovie, "prior": prior,
            "refresh": refresh,
            "spend": {"apify_paid_queries": 0, "haiku_paid_calls": 0, "haiku_searches": 0,
                      "haiku_input_tokens": 0, "haiku_output_tokens": 0}}


def _merge(parts):
    out = {"candidates": [], "directory_hits": [], "signals": {}, "tiers": [], "pending_reason": None}
    for p in parts:
        out["candidates"] += p["candidates"]
        out["directory_hits"] += p["directory_hits"]
        out["signals"].update({k: v for k, v in p["signals"].items() if v is not None})
        out["tiers"] += p["tiers"]
        out["pending_reason"] = out["pending_reason"] or p["pending_reason"]
    return out


def _resolve(body, gathered, probe_fn, judge_fn, parent_lookup, required):
    verified = verify_candidates(body, gathered["candidates"], probe_fn=probe_fn, judge_fn=judge_fn)
    return decide(body, verified, signals=gathered["signals"], directory_hits=gathered["directory_hits"],
                  parent_site_url=parent_lookup.get(body.get("parent_id")),
                  tiers_exhausted=gathered["tiers"], required_tiers=required,
                  pending_reason=gathered["pending_reason"])


def _row(body, decision):
    return {"public_body_id": body["public_body_id"], "name": body.get("name"),
            "gold_status": body.get("gold_status"), "gold_url": body.get("gold_url"), **decision}


def evaluate(bodies, approach_names, ctx, probe_fn, judge_fn, parent_lookup):
    mods = {n: load_approach(n) for n in ("seed_only", "haiku", "apify")}
    results = {}
    for name in approach_names:
        if name == "haiku_then_apify":
            mods["haiku"].prefetch(bodies, ctx)
            first = {}
            for b in bodies:
                g = _merge([mods["seed_only"].gather(b, ctx), mods["haiku"].gather(b, ctx)])
                first[b["public_body_id"]] = (g, _resolve(b, g, probe_fn, judge_fn, parent_lookup,
                                                          ("seed", "haiku_search", "apify_search")))
            residue = [b for b in bodies if first[b["public_body_id"]][1]["website_status"] not in _SETTLED]
            mods["apify"].prefetch(residue, ctx)
            rows = []
            for b in bodies:
                g, d = first[b["public_body_id"]]
                if d["website_status"] not in _SETTLED:
                    g = _merge([g, mods["apify"].gather(b, ctx)])
                    d = _resolve(b, g, probe_fn, judge_fn, parent_lookup,
                                 ("seed", "haiku_search", "apify_search"))
                rows.append(_row(b, d))
            results[name] = rows
            continue
        parts = ["seed_only"] + ([name] if name != "seed_only" else [])
        required = tuple(t for p in parts for t in mods[p].TIERS)
        for p in parts:
            mods[p].prefetch(bodies, ctx)
        results[name] = [
            _row(b, _resolve(b, _merge([mods[p].gather(b, ctx) for p in parts]),
                             probe_fn, judge_fn, parent_lookup, required))
            for b in bodies
        ]
    return results


def _load(path):
    if not Path(path).exists():
        return []
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data.get("results") or data.get("public_bodies") or []


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--approach", choices=APPROACHES + ["all"], required=True)
    ap.add_argument("--judge", default="ollama:gemma4:latest")
    ap.add_argument("--no-fallback", action="store_true", help="disable Haiku escalation of unsure")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--refresh-search", action="store_true")
    args = ap.parse_args()

    gold = {r["public_body_id"]: r for r in load_gold(GOLD) if r["gold_status"] != "unknown"}
    facts = {b["public_body_id"]: b for b in _load(NORMALIZED)}
    bodies = [{**facts.get(i, {}), **g} for i, g in gold.items()]
    if args.limit:
        bodies = bodies[: args.limit]

    resolved = _load(RESOLVED)
    prior = {b["public_body_id"]: b["official_website_url"] for b in resolved
             if b.get("official_website_url") and b["public_body_id"] not in gold}
    parent_lookup = {b["public_body_id"]: b["official_website_url"] for b in resolved
                     if b.get("official_website_url")}
    gov_ie = {b["public_body_id"]: b["official_website_url"] for b in _load(GOV_IE)
              if b.get("official_website_url")}
    foigovie = {r["public_body_id"]: r["foigovie_website"] for r in _load(FOIGOVIE)
                if r.get("public_body_id") and r.get("foigovie_website")}
    # gold bodies must not see their own existing URL as "prior", or the resolved-sample precision check is circular
    ctx = make_ctx(CACHE_DIR, gov_ie=gov_ie, foigovie=foigovie, prior=prior, refresh=args.refresh_search)

    probe_fn = partial(probe_url, cache=ResponseCache(CACHE_DIR / "probe"))
    judge_cache = ResponseCache(CACHE_DIR / "judge")
    judge_fn = partial(judge_cascade, primary=args.judge,
                       fallback=None if args.no_fallback or args.judge == "haiku" else "haiku",
                       cache=judge_cache)

    names = APPROACHES if args.approach == "all" else [args.approach]
    out = evaluate(bodies, names, ctx, probe_fn, judge_fn, parent_lookup)
    RESULTS.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    slug = args.judge.replace(":", "-").replace("/", "-")
    for name, rows in out.items():
        summary = score(rows)
        path = RESULTS / f"{name}__{slug}__{stamp}.json"
        path.write_text(json.dumps({"approach": name, "judge": args.judge, "summary": summary,
                                    "spend": ctx["spend"], "rows": rows},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{name}: {json.dumps(summary)}  -> {path.name}")
    print(f"spend (cumulative this run): {json.dumps(ctx['spend'])}")


if __name__ == "__main__":
    main()
