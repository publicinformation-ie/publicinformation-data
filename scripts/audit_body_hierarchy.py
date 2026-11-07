"""Audit the public-bodies parent / sponsoring-department hierarchy.

`parent_id` is the owning parent body; `government_department_id` is the
sponsoring department. See docs/body-hierarchy.md.

Usage:
    python scripts/audit_body_hierarchy.py [--path FILE] [--json] [--check]

`--check` exits 1 only when a hard finding exists.
"""
import argparse
import json
import sys
from pathlib import Path

HARD = "hard"
SOFT = "soft"
INFO = "info"

DEFAULT_PATH = (Path(__file__).resolve().parent.parent
                / "public/latest/public-bodies/public-bodies.jsonld")

GROUP_PARENTS = {
    "daa": "daa plc",
    "Shannon Group": "Shannon Group PLC",
    "Port of Cork": "Port of Cork Company",
    "Córas Iompair Éireann": "Córas Iompair Éireann",
    "Bord na Móna": "Bord na Móna PLC",
}


def _finding(severity, code, message, body_id):
    return {"severity": severity, "code": code, "message": message,
            "body_id": body_id}


def load_records(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("@graph", [])
    return data


def check_hierarchy(records):
    by_id = {r["@id"]: r for r in records if "@id" in r}
    findings = []

    for r in records:
        rid = r.get("@id")
        name = r.get("name", "")
        parent = r.get("parent_id")

        if parent:
            if parent == rid:
                findings.append(_finding(
                    HARD, "self_parent", f"{name} is its own parent", rid))
            elif parent not in by_id:
                findings.append(_finding(
                    HARD, "dangling_parent",
                    f"{name} has parent_id {parent} that resolves to no record",
                    rid))
            else:
                dept, pdept = (r.get("government_department_id"),
                               by_id[parent].get("government_department_id"))
                if dept and pdept and dept != pdept:
                    findings.append(_finding(
                        SOFT, "department_mismatch",
                        f"{name} department {dept} differs from parent "
                        f"{by_id[parent].get('name')} department {pdept}", rid))

        # Cycle detection over parent_id only (self-parent reported above).
        seen = {rid}
        cur = parent
        while cur and cur != rid and cur in by_id:
            if cur in seen:
                break
            seen.add(cur)
            cur = by_id[cur].get("parent_id")
        if parent and parent != rid and cur == rid:
            findings.append(_finding(
                HARD, "parent_cycle", f"{name} is part of a parent cycle", rid))

        if not parent:
            for token, canonical in GROUP_PARENTS.items():
                if name.startswith(token) and name != canonical:
                    findings.append(_finding(
                        INFO, "group_without_parent",
                        f"{name} looks like part of the {token} group but has "
                        f"no parent_id", rid))
                    break

    return findings


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--path", default=str(DEFAULT_PATH))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 only if a hard finding exists")
    args = ap.parse_args(argv)

    findings = check_hierarchy(load_records(args.path))
    hard = [f for f in findings if f["severity"] == HARD]

    if args.json:
        print(json.dumps(findings, indent=2, ensure_ascii=False))
    else:
        counts = {s: sum(f["severity"] == s for f in findings)
                  for s in (HARD, SOFT, INFO)}
        print(f"hard: {counts[HARD]}  soft: {counts[SOFT]}  info: {counts[INFO]}")
        for f in sorted(findings, key=lambda f: (f["severity"], f["code"])):
            print(f"[{f['severity']}] {f['code']}: {f['message']} ({f['body_id']})")

    return 1 if args.check and hard else 0


if __name__ == "__main__":
    sys.exit(main())
