"""List distinct raw requester/status values in a canonicalize_rows errors.json
that now resolve (via the punctuation-insensitive fallback): raw, target, count, bodies.
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

_SRC = Path(__file__).resolve().parents[4] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from lib.requester_type_map import canonicalize_requester_type  # noqa: E402
from lib.status_map import canonicalize_status  # noqa: E402

_FIELDS = {
    "UnrecognizedRequesterType": ("raw_requester_type", canonicalize_requester_type),
    "UnrecognizedDecisionStatus": ("raw_status", canonicalize_status),
    "StatusValueIsDate": ("raw_status", canonicalize_status),
    "StatusValueIsColumnHeader": ("raw_status", canonicalize_status),
}


def newly_resolved(errors: list) -> tuple[list[dict], int]:
    groups: dict[tuple, dict] = {}
    total = 0
    for e in errors:
        spec = _FIELDS.get(e.get("error_type"))
        if not spec:
            continue
        key, canon = spec
        ctx = e.get("context") or {}
        raw = ctx.get(key)
        if not isinstance(raw, str):
            continue
        target = canon(raw)
        if target is None:
            continue
        total += 1
        g = groups.setdefault((e["error_type"], raw), {
            "error_type": e["error_type"], "raw": raw, "target": target,
            "count": 0, "bodies": Counter()})
        g["count"] += 1
        g["bodies"][ctx.get("public_body_id")] += 1
    return sorted(groups.values(), key=lambda g: -g["count"]), total


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--errors", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    rows, total = newly_resolved(json.loads(a.errors.read_text()))
    L = ["# WP1 newly resolved values", "",
         f"{total} errors across {len(rows)} distinct raw values now resolve.", "",
         "| error_type | raw | target | count | bodies |", "|---|---|---|---|---|"]
    for g in rows:
        bodies = ", ".join(f"{b}:{n}" for b, n in g["bodies"].most_common())
        L.append(f"| {g['error_type']} | `{g['raw']!r}` | {g['target']} | {g['count']} | {bodies} |")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
