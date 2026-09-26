#!/usr/bin/env python3
"""Sample a stratified gold set of CSO bodies for website-resolution labelling.

Writes a CSV pre-filled with suggestions; a human fills gold_status/gold_url.
Refuses to overwrite an existing CSV unless --overwrite (it may hold labels).

    uv run python pipelines/cso_pipeline/website_eval/sample_gold.py
"""
import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path

_CSO = Path(__file__).resolve().parents[1]
_REPO = _CSO.parents[1]
DEFAULT_OUT = _CSO / "website_eval" / "website_gold.csv"
RESOLVE_OUTPUT = _CSO / "steps" / "resolve_website_urls" / "output.json"
FOIGOVIE_OUTPUT = _REPO / "pipelines" / "foigovie_pipeline" / "steps" / "apply_overrides" / "output.json"

GOLD_COLUMNS = ["public_body_id", "name", "parent_name", "sub_sector", "legal_status", "cro",
                "existing_url", "foigovie_website", "llm_website_url",
                "gold_status", "gold_url", "notes"]


def _row(b: dict, foigovie: dict) -> dict:
    return {"public_body_id": b["public_body_id"], "name": b.get("name", ""),
            "parent_name": b.get("parent_name") or "", "sub_sector": b.get("description_for_sub_sector") or "",
            "legal_status": b.get("legal_status") or "", "cro": b.get("cro") or "",
            "existing_url": b.get("official_website_url") or "",
            "foigovie_website": foigovie.get(b["public_body_id"], ""),
            "llm_website_url": b.get("llm_website_url") or "",
            "gold_status": "", "gold_url": "", "notes": ""}


def sample(bodies, foigovie, n_unresolved=80, n_resolved=20, seed=20260926):
    rng = random.Random(seed)
    unresolved = sorted((b for b in bodies if not b.get("official_website_url")),
                        key=lambda b: b["public_body_id"])
    resolved = sorted((b for b in bodies if b.get("official_website_url")),
                      key=lambda b: b["public_body_id"])

    strata = defaultdict(list)
    for b in unresolved:
        strata[b.get("description_for_sub_sector") or ""].append(b)
    total = len(unresolved) or 1
    picked = []
    for key in sorted(strata):
        members = strata[key]
        k = min(len(members), max(1, round(n_unresolved * len(members) / total)))
        picked += rng.sample(members, k)
    rng.shuffle(picked)
    picked = picked[:n_unresolved]
    picked += rng.sample(resolved, min(n_resolved, len(resolved)))
    return [_row(b, foigovie) for b in picked]


def write_csv(rows, path, overwrite: bool):
    path = Path(path)
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} exists and may contain labels; pass --overwrite to replace it")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=GOLD_COLUMNS)
        w.writeheader()
        w.writerows(rows)


def _load(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data.get("results") or data.get("public_bodies") or []


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--n-unresolved", type=int, default=80)
    ap.add_argument("--n-resolved", type=int, default=20)
    args = ap.parse_args()
    bodies = _load(RESOLVE_OUTPUT)
    foigovie = {r["public_body_id"]: r["foigovie_website"] for r in _load(FOIGOVIE_OUTPUT)
                if r.get("public_body_id") and r.get("foigovie_website")}
    rows = sample(bodies, foigovie, n_unresolved=args.n_unresolved, n_resolved=args.n_resolved)
    write_csv(rows, args.out, args.overwrite)
    print(f"Wrote {len(rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
