#!/usr/bin/env python3
"""Per-document production view over the whole snapshot (all 40 documents).

`score.py` covers only documents with gold; `compare.py` runs its own cascade.
This runs `detect_document_structure` — the entry point `process()` uses — on
every snapshot document and reports method, node count, `InvalidStructure`
count (`split_issues`) and the slug list, so a detector change can be checked
on the documents that have no gold (design D0, step 3). Read-only and offline.

    PYTHONPATH=".:../../src" python steps/detect_structure/eval/production_view.py \
        --save /tmp/before.json
    # ... change the detector ...
    PYTHONPATH=".:../../src" python steps/detect_structure/eval/production_view.py \
        --diff /tmp/before.json
"""
import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).parent
_DOC_PIPELINE = _HERE.parents[2]
sys.path.insert(0, str(_DOC_PIPELINE))
sys.path.insert(0, str(_DOC_PIPELINE.parent / "src"))

from steps.detect_structure.process import (  # noqa: E402
    detect_document_structure,
    load_overrides,
    split_issues,
)

INPUT_PATH = _HERE / "input.json"


def view(snapshot_path=INPUT_PATH) -> dict:
    documents = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))["documents"]
    result = {}
    for document in documents:
        pages = document["pages"]
        page_count = int(document.get("page_count") or len(pages))
        nodes, method, _report, problems = detect_document_structure(
            pages, document.get("outline"), page_count)
        result[document["doc_slug"]] = {
            "method": method,
            "nodes": len(nodes),
            "invalid_structure": len(split_issues(nodes, page_count)),
            "problems": sorted({p["error_type"] for p in problems}),
            "slugs": [node.slug for node in nodes],
        }
    return result


def diff(before: dict, after: dict, overrides: dict) -> list:
    lines = []
    for slug in sorted(set(before) | set(after)):
        old, new = before.get(slug), after.get(slug)
        if old is None or new is None:
            lines.append(f"{slug}: {'added' if old is None else 'removed'}")
            continue
        notes = []
        if old["method"] != new["method"]:
            notes.append(f"method {old['method']} -> {new['method']}")
        if old["invalid_structure"] != new["invalid_structure"]:
            notes.append(f"InvalidStructure {old['invalid_structure']} -> {new['invalid_structure']}")
        if old["nodes"] != new["nodes"]:
            notes.append(f"nodes {old['nodes']} -> {new['nodes']}")
        if old["slugs"] != new["slugs"]:
            gone = sorted(set(old["slugs"]) - set(new["slugs"]))
            notes.append(f"slugs changed ({len(gone)} no longer present)")
            orphaned = sorted({patch.get("slug") for patch in overrides.get(slug) or []}
                              & set(gone))
            if orphaned:
                notes.append(f"ORPHANED OVERRIDE slug(s): {', '.join(orphaned)}")
        if notes:
            lines.append(f"{slug}: " + "; ".join(notes))
    return lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--save", metavar="PATH", help="write this run's view to PATH")
    parser.add_argument("--diff", metavar="PATH", help="print changes against a saved view")
    args = parser.parse_args(argv)

    after = view()
    total_invalid = sum(v["invalid_structure"] for v in after.values())
    print(f"{len(after)} documents; InvalidStructure total {total_invalid}")
    if args.diff:
        before = json.loads(Path(args.diff).read_text(encoding="utf-8"))
        changes = diff(before, after, load_overrides(_HERE.parent))
        before_total = sum(v["invalid_structure"] for v in before.values())
        print(f"InvalidStructure {before_total} -> {total_invalid}")
        print("\n".join(changes) if changes else "no per-document change")
    else:
        for slug, v in sorted(after.items()):
            print(f"{slug:<52} {v['method']:<10} {v['nodes']:>4} nodes  invalid {v['invalid_structure']}")
    if args.save:
        Path(args.save).write_text(json.dumps(after, indent=1) + "\n", encoding="utf-8")
        print(f"Wrote {args.save}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
