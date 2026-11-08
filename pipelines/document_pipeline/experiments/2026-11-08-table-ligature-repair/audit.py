#!/usr/bin/env python3
"""Before/after audit for the table ligature repair.

Usage: audit.py BEFORE_DIR AFTER_DIR
Each dir holds extract_actions/output.json, extract_action_status/output.json
and <step>/errors.json copies. Exits 1 if any hard check fails.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ALLOWLIST_LETTER_CHANGES = {"emra-regional-spatial-and-economic-strategy"}
DAMAGED = re.compile(r"batet|difef|staf\.f")


def load(d, step):
    p = Path(d) / step / "output.json"
    return {r["doc_slug"]: r for r in json.loads(p.read_text())["results"]}


def texts(a):
    out = {"action": a.get("action") or ""}
    for k, v in (a.get("columns") or {}).items():
        out[f"columns.{k}"] = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    return out


def letters(s):
    return Counter(re.sub(r"\s+", "", s))


def error_counts(d):
    out = {}
    for p in Path(d).glob("*/errors.json"):
        try:
            out[p.parent.name] = len(json.loads(p.read_text()))
        except Exception:
            out[p.parent.name] = -1
    return out


def main(before, after):
    fails = []
    b, a = load(before, "extract_actions"), load(after, "extract_actions")
    if set(b) != set(a):
        fails.append(f"(a) doc slugs differ: {sorted(set(b) ^ set(a))}")
    changed_per_doc, new_words = {}, Counter()
    dam_before = dam_after = 0
    for slug in sorted(set(b) & set(a)):
        if b[slug]["action_count"] != a[slug]["action_count"]:
            fails.append(f"(a) {slug} action_count {b[slug]['action_count']} -> {a[slug]['action_count']}")
        ba = {x["action_id"]: x for x in b[slug]["actions"]}
        aa = {x["action_id"]: x for x in a[slug]["actions"]}
        if set(ba) != set(aa):
            fails.append(f"(b) {slug} action_ids differ: {len(set(ba) ^ set(aa))}")
        n = 0
        for aid in set(ba) & set(aa):
            tb, ta = texts(ba[aid]), texts(aa[aid])
            dam_before += sum(len(DAMAGED.findall(v)) for v in tb.values())
            dam_after += sum(len(DAMAGED.findall(v)) for v in ta.values())
            diff = False
            for k in set(tb) | set(ta):
                x, y = tb.get(k, ""), ta.get(k, "")
                if x == y:
                    continue
                diff = True
                if letters(x) != letters(y) and slug not in ALLOWLIST_LETTER_CHANGES:
                    fails.append(f"(c) {slug} {aid} {k}: letters changed: {x[:60]!r} -> {y[:60]!r}")
                wb, wa = set(re.findall(r"[A-Za-z]+", x)), set(re.findall(r"[A-Za-z]+", y))
                new_words.update(wa - wb)
            n += diff
        changed_per_doc[slug] = n
    sb, sa = load(before, "extract_action_status"), load(after, "extract_action_status")
    if set(sb) != set(sa):
        fails.append(f"(d) status doc slugs differ: {sorted(set(sb) ^ set(sa))}")
    for slug in set(sb) & set(sa):
        for k in ("report_format", "observation_count"):
            if sb[slug].get(k) != sa[slug].get(k):
                fails.append(f"(d) {slug} {k}: {sb[slug].get(k)} -> {sa[slug].get(k)}")
    eb, ea = error_counts(before), error_counts(after)
    for step, n in ea.items():
        if n > eb.get(step, 0):
            fails.append(f"(e) {step} errors rose {eb.get(step, 0)} -> {n}")
    print("Changed actions per doc:", json.dumps(changed_per_doc, indent=1))
    print("Top new words:", new_words.most_common(15))
    print(f"Damaged tokens before/after: {dam_before} / {dam_after}")
    for f in fails:
        print("FAIL", f)
    print("RESULT:", "FAIL" if fails else "PASS")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
