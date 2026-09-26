"""Load the hand-labelled website gold set and score predictions against it."""
import csv
from collections import Counter
from pathlib import Path

from lib.website_decide import OWN_STATUSES
from lib.website_domains import site_key

GOLD_STATUSES = {"own_site", "no_own_site", "defunct", "unknown"}


def load_gold(path) -> list[dict]:
    with open(Path(path), newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    bad = [r["public_body_id"] for r in rows
           if r.get("gold_status", "").strip() not in GOLD_STATUSES
           or (r["gold_status"].strip() == "own_site" and not r.get("gold_url", "").strip())]
    if bad:
        raise ValueError(f"Unlabelled or invalid gold rows (public_body_id): {', '.join(bad)}")
    for r in rows:
        r["public_body_id"] = int(r["public_body_id"])
        r["gold_status"] = r["gold_status"].strip()
        r["gold_url"] = r.get("gold_url", "").strip()
    return rows


def _ratio(num, den):
    return num / den if den else None


def score(rows: list[dict]) -> dict:
    rows = [r for r in rows if r["gold_status"] != "unknown"]
    gold_own = [r for r in rows if r["gold_status"] == "own_site"]
    pred_own = [r for r in rows if r["website_status"] in OWN_STATUSES]

    def correct(r):
        return (r["gold_status"] == "own_site" and r["website_status"] in OWN_STATUSES
                and site_key(r["official_website_url"] or "") == site_key(r["gold_url"]))

    hits = sum(1 for r in rows if correct(r))
    gold_no = [r for r in rows if r["gold_status"] == "no_own_site"]
    pred_no = [r for r in rows if r["website_status"] == "no_own_site"]
    gold_def = [r for r in rows if r["gold_status"] == "defunct"]
    return {
        "n": len(rows),
        "own_coverage": _ratio(hits, len(gold_own)),
        "own_precision": _ratio(hits, len(pred_own)),
        "no_own_precision": _ratio(sum(1 for r in pred_no if r["gold_status"] == "no_own_site"), len(pred_no)),
        "no_own_recall": _ratio(sum(1 for r in gold_no if r["website_status"] == "no_own_site"), len(gold_no)),
        "false_not_found_rate": _ratio(sum(1 for r in gold_own if r["website_status"] == "not_found"),
                                       len(gold_own)),
        "defunct_recall": _ratio(sum(1 for r in gold_def if r["website_status"] == "defunct"), len(gold_def)),
        "status_counts": dict(Counter(r["website_status"] for r in rows)),
    }
