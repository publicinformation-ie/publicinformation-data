"""Councillor motion league table (top 5 overall and per calendar year).

Scoring per motion, by outcome:
  carried / carried_as_amended -> 5
  deferred / withdrawn / not_carried -> 2
  not_recorded -> 1
The proposer scores in full, the seconder scores half. Names resolve through
pipelines/minutes_pipeline/reference/councillor_aliases.csv; joint, group and
unresolved names are excluded and counted.

Run: python3 -I scripts/councillor_league_table.py > report.md
"""
import csv
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "pipelines/minutes_pipeline/reference"
POINTS = {"carried": 5, "carried_as_amended": 5, "deferred": 2, "withdrawn": 2,
          "not_carried": 2, "not_recorded": 1}
SECONDER_SHARE = 0.5
TOP_N = 5


def fmt(x: float) -> str:
    return f"{x:g}"


def main() -> None:
    aliases = {r["raw_name"]: r["councillor_id"]
               for r in csv.DictReader(open(REF / "councillor_aliases.csv", encoding="utf-8"))}
    names = {r["councillor_id"]: r["canonical_name"]
             for r in csv.DictReader(open(REF / "councillors.csv", encoding="utf-8"))}

    # (year or "all") -> councillor_id -> Counter
    tables: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    skipped = Counter()
    for r in csv.DictReader(open(ROOT / "public/latest/motions/motions.csv", encoding="utf-8")):
        pts = POINTS[r["status"]]
        year = r["meeting_date"][:4]
        for role, share in (("proposer", 1.0), ("seconder", SECONDER_SHARE)):
            raw = r[role].strip()
            if not raw:
                skipped[f"{role} blank"] += 1
                continue
            cid = aliases.get(raw, "")
            if not cid:
                skipped[f"{role} excluded/unresolved"] += 1
                continue
            for key in ("all", year):
                c = tables[key][cid]
                c[role] += 1
                c["carried" if pts == 5 else "other" if pts == 2 else "unrecorded"] += 1
                c["points"] += pts * share

    def render(key: str, title: str) -> list[str]:
        rows = sorted(tables[key].items(), key=lambda kv: (-kv[1]["points"], names[kv[0]]))[:TOP_N]
        out = [f"## {title}", "", "| # | Councillor | Proposed | Seconded | Points |", "|--:|---|--:|--:|--:|"]
        for i, (cid, c) in enumerate(rows, 1):
            out.append(f"| {i} | {names[cid]} | {int(c['proposer'])} | {int(c['seconder'])} | {fmt(c['points'])} |")
        return out + [""]

    lines = ["# Meath County Council: councillor motion league table", "",
             "Points per motion: carried (incl. as amended) 5, other outcome 2, outcome not recorded 1. "
             "Proposer scores in full, seconder half. Year = calendar year of meeting. "
             "Council and Municipal District meetings combined.", ""]
    lines += render("all", "Overall (2009-2026)")
    for y in sorted(k for k in tables if k != "all"):
        lines += render(y, y)
    lines += ["## Excluded", ""] + [f"- {k}: {v}" for k, v in sorted(skipped.items())]
    print("\n".join(lines))


if __name__ == "__main__":
    main()
