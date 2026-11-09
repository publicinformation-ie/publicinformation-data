"""Build councillor reference tables from the published motions CSV.

Proposer/seconder are free text in the minutes. This resolves each raw string
to a stable councillor_id and writes:

  councillors.csv         one row per councillor (incl. meath.ie slug where listed)
  councillor_aliases.csv  one row per raw name string -> councillor_id (or blank)

Run: python3 -I build_councillor_reference.py
"""
import csv
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOTIONS = HERE.parents[2] / "public/latest/motions/motions.csv"

TITLE = re.compile(r"^(councillors?|cllrs?\.?)\s+", re.I)
JOINT = re.compile(r"\s(&|and)\s|^councillors\s", re.I)
NON_PERSON = re.compile(r"members|sinn f|county manager|^councillor xx$|^xx$", re.I)

# First-name variants -> one form (only applied together with a surname).
FIRST = {"eddie": "edward", "nick": "nicholas", "jim": "james", "willie": "william",
         "ashling": "aisling", "susanne": "suzanne", "phillip": "philip",
         "damian": "damien", "mike": "michael", "tommy": "tom", "padraig": "padraig",
         "annie": "annie", "anne": "ann"}
# Whole-key corrections: typos and initials the rules above can't infer.
KEY_FIX = {"edward fennesy": "edward fennessy", "michael gallager": "michael gallagher",
           "sarah reily": "sarah reilly", "eoin homes": "eoin holmes",
           "francis dean": "francis deane", "padraig fitzimons": "padraig fitzsimons",
           "emer teibin": "emer toibin", "j v farrelly": "john farrelly",
           "john v farrelly": "john farrelly", "john farrelly": "john farrelly",
           "dillon gallagher": "ann dillon gallagher",
           "gerry o connor": "gerry oconnor", "claire o driscoll": "claire odriscoll",
           "damien o reilly": "damien oreilly", "darren o rourke": "darren orourke",
           "maria o kane": "maria okane", "seamus o neill": "seamus oneill",
           "aisling o neill": "aisling oneill", "caroline o reilly": "caroline oreilly",
           "paul o rourke": "paul orourke", "patsy o neill": "patsy oneill"}


def key(raw: str) -> str:
    s = TITLE.sub("", raw.strip())
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[’‘`']\s*", "", s)   # apostrophes vanish: o'connor / o' connor -> oconnor
    s = re.sub(r"[-.\u2010-\u2015]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = KEY_FIX.get(s, s)
    toks = s.split()
    if len(toks) >= 2 and toks[0] in FIRST:
        toks[0] = FIRST[toks[0]]
    return " ".join(toks)


def slug(k: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", k).strip("-")


def main() -> None:
    raw_counts: Counter = Counter()
    seen: dict[str, list] = defaultdict(lambda: [None, None])
    body_id = None
    with open(MOTIONS, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            body_id = r["public_body_id"]
            for col in ("proposer", "seconder"):
                n = r[col].strip()
                if not n:
                    continue
                raw_counts[n] += 1
                lo, hi = seen[n]
                d = r["meeting_date"]
                seen[n] = [min(lo or d, d), max(hi or d, d)]

    # Pass 1: full names (>=2 tokens, not initials) define the councillors.
    people: dict = defaultdict(Counter)
    for n, c in raw_counts.items():
        if NON_PERSON.search(n) or JOINT.search(n):
            continue
        k = key(n)
        t = k.split()
        if len(t) >= 2 and len(t[0]) > 1:
            people[k][TITLE.sub("", n).strip()] += c

    by_surname: dict = defaultdict(set)
    for k in people:
        by_surname[k.split()[-1]].add(k)

    aliases = []
    for n, c in sorted(raw_counts.items()):
        if NON_PERSON.search(n):
            cid, method = "", "excluded_non_person"
        elif JOINT.search(n):
            cid, method = "", "excluded_joint"
        else:
            k, t = key(n), key(n).split()
            if k in people:
                cid, method = k, "name"
            elif len(t) == 1 and len(by_surname[t[0]]) == 1:
                cid, method = next(iter(by_surname[t[0]])), "surname_only"
            elif len(t) == 2 and len(t[0]) == 1:
                m = [p for p in by_surname[t[1]] if p.startswith(t[0])]
                cid, method = (m[0], "initial_surname") if len(m) == 1 else ("", "unresolved")
            else:
                cid, method = "", "unresolved"
        aliases.append((n, cid, method, c))

    # Canonical display name = most common surface form in the group.
    ids = {k: f"meath/{slug(k)}" for k in people}
    canon, stats = {}, defaultdict(lambda: [0, None, None])
    for k, forms in people.items():
        best = forms.most_common(1)[0][0]
        best = re.sub(r"[’‘`]\s*", "'", best)
        best = re.sub(r"'\s+", "'", best)
        canon[k] = re.sub(r"[\u2010-\u2015]", "-", best)
    for n, k, m, c in aliases:
        if k:
            s = stats[k]
            s[0] += c
            lo, hi = seen[n]
            s[1] = min(filter(None, [s[1], lo]))
            s[2] = max(filter(None, [s[2], hi]))

    # council_slug / site_status: from meath.ie's councillor pages (current + former 2024-2029).
    with open(HERE / "councillor_site_slugs.csv", newline="", encoding="utf-8") as f:
        site = {r["councillor_id"]: (r["council_slug"], r["site_status"]) for r in csv.DictReader(f)}
    assert set(site) <= {ids[k] for k in people}, "site slug for unknown councillor"

    with open(HERE / "councillors.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["councillor_id", "canonical_name", "public_body_id", "first_seen", "last_seen",
                    "council_slug", "site_status"])
        for k in sorted(people, key=lambda k: canon[k]):
            slug_, status = site.get(ids[k], ("", ""))
            w.writerow([ids[k], canon[k], body_id, stats[k][1], stats[k][2], slug_, status])
    with open(HERE / "councillor_aliases.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["raw_name", "councillor_id", "method", "occurrences"])
        for n, k, m, c in aliases:
            w.writerow([n, ids.get(k, ""), m, c])

    print(f"{len(people)} councillors from {len(raw_counts)} raw strings")
    for n, k, m, c in aliases:
        if m not in ("name",):
            print(f"{m:22} {c:4} {n!r} -> {ids.get(k, '-')}")


if __name__ == "__main__":
    main()
