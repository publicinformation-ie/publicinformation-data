"""Agreement between two extractions, gold scoring and agreement-threshold calibration.

GOLD_KEY check (Task 4): `gold_accuracy` returns `raw` and `normalised`. Over the 10 gold files in
BAKEOFF/results/bakeoff.json, the docling mean is 0.9130 for `normalised` and also 0.9130 for `raw`
(the published 0.913), so `normalised` reproduces the bake-off headline and is kept.

CLI: `uv run python -m experiments.gating.compare --calibrate` (Task 9 only; fills the extraction cache).
"""
import argparse
import json
from itertools import combinations
from pathlib import Path

from experiments.gating.paths import BAKEOFF, GATING, GOLD_DIR, PDF_CACHE, content_sha, pdf_bytes  # noqa: F401  (sets sys.path)
from experiments.gating.fixes import REGISTRY, family_of  # noqa: E402

import sys  # noqa: E402
if str(BAKEOFF) not in sys.path:
    sys.path.insert(0, str(BAKEOFF))
from bakeoff import _norm, gold_accuracy  # noqa: E402
from lib.table_structure import _cell_type, _data_rows  # noqa: E402

GOLD_KEY = "normalised"
THRESHOLDS = [round(0.80 + 0.01 * i, 2) for i in range(20)]
GOLD_MIN = 0.90


def _prep(rows: list[list]) -> list[list[str]]:
    _, data, _ = _data_rows(rows)
    data = [[_norm("" if c is None else c) for c in r] for r in data]
    width = max((len(r) for r in data), default=0)
    data = [r + [""] * (width - len(r)) for r in data]
    keep = [i for i in range(width) if any(r[i] for r in data)]
    return [[r[i] for i in keep] for r in data]


def _keyed(data: list[list[str]]) -> list[tuple[str, list[str]]]:
    out = []
    for r in data:
        key = next((c for c in r if _cell_type(c) == "reference"), None)
        if key is None:
            key = next((c for c in r if _cell_type(c) == "date"), None)
        if key is not None:
            out.append((key, r))
    return out


def _directed(x: list[tuple[str, list[str]]], y: list[tuple[str, list[str]]]) -> float:
    hit = total = 0
    for key, r in x:
        best = 0
        for _, r2 in y:
            if key in r2:
                best = max(best, sum(1 for a, b in zip(r, r2) if a == b))
        hit += best
        total += len(r)
    return hit / total if total else 0.0


def agreement(a: list[list] | None, b: list[list] | None) -> float | None:
    if a is None or b is None:
        return None
    pa, pb = _prep(a), _prep(b)
    if len(pa[0] if pa else []) != len(pb[0] if pb else []):
        return None
    ka, kb = _keyed(pa), _keyed(pb)
    if len(ka) < 3 or len(kb) < 3:
        return None
    return min(_directed(ka, kb), _directed(kb, ka))


def independent(family_a: str | None, family_b: str | None) -> bool:
    return bool(family_a) and bool(family_b) and family_a != family_b


def load_gold(content_sha: str, gold_dir: Path = GOLD_DIR) -> dict | None:
    p = Path(gold_dir) / f"{content_sha}.json"
    return json.loads(p.read_text()) if p.is_file() else None


def gold_score(rows: list[list] | None, gold: dict) -> float:
    if rows is None:
        return 0.0
    return gold_accuracy(rows, gold)[GOLD_KEY]


def _violates(s: dict, t: float) -> bool:
    return s["agreement"] >= t and min(s["gold_a"], s["gold_b"]) < GOLD_MIN


def calibrate(samples: list[dict]) -> dict:
    threshold = next((t for t in THRESHOLDS if not any(_violates(s, t) for s in samples)), None)
    return {"threshold": threshold, "pairs": len(samples),
            "violations_at_0_90": [s for s in samples if _violates(s, 0.90)]}


def collect_samples() -> tuple[list[dict], list[str]]:
    """Run every registered fix over the gold files; return independent-pair samples and notes."""
    from experiments.gating.downstream import transform_index
    from experiments.gating.extract_cache import get_rows
    sample = json.loads((BAKEOFF / "sample.json").read_text())
    stored = transform_index()
    samples, notes = [], []
    for s in sample:
        gold = load_gold(s["sha256"])
        if gold is None or not s.get("on_disk"):
            continue
        url = s["file_url"]
        data = pdf_bytes(url)
        item = stored.get(url)
        if data is None or item is None:
            notes.append(f"{s['sha256'][:8]}: missing bytes or stored item")
            continue
        res = {}
        for name, fix in REGISTRY.items():
            ex = get_rows(fix, url, data, item)
            res[name] = (ex.rows, family_of(fix, item), ex.status)
        for (na, (ra, fa, _)), (nb, (rb, fb, _)) in combinations(res.items(), 2):
            if not independent(fa, fb):
                continue
            ag = agreement(ra, rb)
            if ag is None:
                continue
            samples.append(dict(sha=s["sha256"], fix_a=na, fix_b=nb, agreement=ag,
                                gold_a=gold_score(ra, gold), gold_b=gold_score(rb, gold)))
    return samples, notes


def write_report(samples: list[dict], result: dict, notes: list[str], path: Path) -> None:
    lines = ["# Agreement calibration", "",
             f"Independent pairs with a defined agreement: {result['pairs']}",
             f"Lowest safe threshold (0.80-0.99): {result['threshold']}",
             f"Violations at 0.90 (agreement >= 0.90, min gold < {GOLD_MIN}): {len(result['violations_at_0_90'])}",
             "", "settings.json stays at 0.90; any change is the user's decision.", ""]
    if result["violations_at_0_90"]:
        lines += ["| sha | fix_a | fix_b | agreement | gold_a | gold_b |", "|---|---|---|---|---|---|"]
        for v in result["violations_at_0_90"]:
            lines.append(f"| {v['sha'][:8]} | {v['fix_a']} | {v['fix_b']} | {v['agreement']:.3f} | "
                         f"{v['gold_a']:.3f} | {v['gold_b']:.3f} |")
        lines.append("")
    lines += [f"- {n}" for n in notes]
    Path(path).write_text("\n".join(lines) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--calibrate", action="store_true", help="run every fix on the gold files, write calibration.md")
    args = ap.parse_args(argv)
    if not args.calibrate:
        ap.print_help()
        return
    samples, notes = collect_samples()
    result = calibrate(samples)
    write_report(samples, result, notes, GATING / "calibration.md")
    print(json.dumps({k: v for k, v in result.items() if k != "violations_at_0_90"}))


if __name__ == "__main__":
    main()
