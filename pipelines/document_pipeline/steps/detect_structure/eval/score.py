#!/usr/bin/env python3
"""Chapter-split accuracy report: score detection against hand-authored gold.

`validate_split` checks the tree's shape and `compare.py` checks whether output
changed; neither says whether the split is *right*. This report scores each
detected chapter list against a gold list transcribed from the document's
printed table of contents (rulebook: `gold/GUIDELINE.md`).

It scores every document twice — the raw detector tree and the tree after
`override.json` — so a hand override cannot hide a detector regression. It is
read-only and offline; the only file it writes is the baseline, and only under
`--refresh-baseline` (plus an explicit `--json` path).

Run it from the document_pipeline directory:

    PYTHONPATH=".:../../src" python steps/detect_structure/eval/score.py
    PYTHONPATH=".:../../src" python steps/detect_structure/eval/score.py --live
    PYTHONPATH=".:../../src" python steps/detect_structure/eval/score.py --refresh-baseline
    PYTHONPATH=".:../../src" python steps/detect_structure/eval/score.py \
        --compare-gold eval/gold/national-cycle-network-plan.json /tmp/reviewed.json
"""
import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).parent
_STEP_DIR = _HERE.parent
_DOC_PIPELINE = _HERE.parents[2]
sys.path.insert(0, str(_DOC_PIPELINE))
sys.path.insert(0, str(_DOC_PIPELINE.parent / "src"))
sys.path.insert(0, str(_HERE))

from steps.detect_structure.process import (  # noqa: E402
    detect_document_structure,
    load_overrides,
    merge_overrides,
)

try:  # imported as a module from the test suite
    from . import gold as gold_module
    from . import metrics
    from .snapshot import spans_sha256
except ImportError:  # run as a script, as the docstring says
    import gold as gold_module
    import metrics
    from snapshot import spans_sha256

INPUT_PATH = _HERE / "input.json"
GOLD_DIR = _HERE / "gold"
BASELINE_PATH = _HERE / "baseline.json"
EXTRACT_PAGES_OUTPUT = _DOC_PIPELINE / "steps" / "extract_pages" / "output.json"
FETCH_PDFS_OUTPUT = _DOC_PIPELINE / "steps" / "fetch_pdfs" / "output.json"

EXCLUDED_MALFORMED = "malformed gold file"
EXCLUDED_UNREVIEWED = "unreviewed"
EXCLUDED_NO_TOC = "no printed TOC"
EXCLUDED_PDF_MISMATCH = "gold/PDF mismatch"
EXCLUDED_MISSING = "not in the source"
EXCLUDED_DETECTION = "detection error"


# --------------------------------------------------------------------------
# Sources: the committed snapshot (default) or live extract_pages output
# --------------------------------------------------------------------------

def _read_source_sha256(path=FETCH_PDFS_OUTPUT) -> dict:
    if not Path(path).exists():
        return {}
    records = json.loads(Path(path).read_text(encoding="utf-8"))["results"]
    return {record["doc_slug"]: record.get("source_sha256") for record in records}


def load_snapshot(path=None) -> dict:
    """The committed snapshot: `doc_slug` -> document with its fingerprints."""
    path = Path(path or INPUT_PATH)
    if not path.exists():
        raise SystemExit(f"{path} is missing — run steps/detect_structure/eval/make_input.py")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path} is not JSON ({exc}); if it is an LFS pointer, run `git lfs pull`")
    return {
        "kind": "snapshot",
        "documents": {doc["doc_slug"]: doc for doc in payload["documents"]},
        "drifted": [],
    }


def load_live(snapshot: dict | None = None) -> dict:
    """Current local `extract_pages` output, with a drift check against the snapshot."""
    if not EXTRACT_PAGES_OUTPUT.exists():
        raise SystemExit(f"{EXTRACT_PAGES_OUTPUT} is missing — run the extract_pages step first")
    records = json.loads(EXTRACT_PAGES_OUTPUT.read_text(encoding="utf-8"))["results"]
    source_sha = _read_source_sha256()
    documents = {}
    for record in records:
        pages = []
        for entry in sorted(record["pages"], key=lambda e: e["number"]):
            path = EXTRACT_PAGES_OUTPUT.parent / entry["file"]
            raw = json.loads(path.read_text(encoding="utf-8"))
            pages.append({"number": raw["number"], "width": raw.get("width"),
                          "height": raw.get("height"), "spans": raw.get("spans", [])})
        outline = record.get("outline") or []
        documents[record["doc_slug"]] = {
            "doc_slug": record["doc_slug"],
            "page_count": record.get("page_count"),
            "outline": outline,
            "spans_sha256": spans_sha256(pages, outline),
            "source_sha256": source_sha.get(record["doc_slug"]),
            "pages": pages,
        }

    drifted = []
    snapshot_docs = (snapshot or {}).get("documents") or {}
    for slug, doc in documents.items():
        known = snapshot_docs.get(slug)
        if known is None:
            drifted.append({"doc_slug": slug, "detail": "not in the snapshot"})
        elif known.get("spans_sha256") != doc["spans_sha256"]:
            drifted.append({"doc_slug": slug,
                            "detail": "spans or outline differ from the snapshot"})
    for slug in snapshot_docs:
        if slug not in documents:
            drifted.append({"doc_slug": slug, "detail": "in the snapshot, missing from live output"})
    return {"kind": "live", "documents": documents,
            "drifted": sorted(drifted, key=lambda d: d["doc_slug"])}


# --------------------------------------------------------------------------
# Detection and scoring
# --------------------------------------------------------------------------

def detect_document(document: dict):
    """Run the production detector on one document's pages.

    Goes through `detect_document_structure`, the same entry point `process()`
    uses, so the outline filter and position resolution are never skipped.
    """
    pages = document["pages"]
    page_count = int(document.get("page_count") or len(pages))
    nodes, method, _report, _problems = detect_document_structure(
        pages, document.get("outline"), page_count)
    return nodes, method, page_count


def score_document(slug: str, document: dict, gold_doc, overrides: dict) -> dict:
    """Build one document's result row: method, raw score, post-override score."""
    nodes, method, page_count = detect_document(document)
    predicted = metrics.predicted_chapters(nodes)
    raw = metrics.score(gold_doc.chapters, predicted, page_count)

    patches = overrides.get(slug) or []
    post = None
    if patches:
        # Score the raw tree above before merging: merge_overrides may rewrite
        # slugs through dedupe_slugs.
        merged, _errors = merge_overrides(nodes, patches, page_count)
        post = metrics.score(gold_doc.chapters, metrics.predicted_chapters(merged), page_count)

    return {
        "doc_slug": slug,
        "method": method,
        "has_overrides": bool(patches),
        "held_out": bool(getattr(gold_doc, "held_out", False)),
        "raw": raw,
        "post_override": post,
        "warnings": list(gold_doc.warnings),
    }


def build_report(source: dict, gold_load, overrides: dict) -> dict:
    """Score every reviewed gold document in the source, and list exclusions."""
    excluded = list(gold_load.excluded)
    documents = []
    warnings = {}

    for slug in sorted(gold_load.documents):
        gold_doc = gold_load.documents[slug]
        document = source["documents"].get(slug)
        if document is None:
            excluded.append({"doc_slug": slug, "reason": EXCLUDED_MISSING,
                             "detail": f"not found in the {source['kind']}"})
            continue

        gold_doc.warnings = gold_module.consistency_warnings(gold_doc, document["pages"])
        if gold_doc.warnings:
            warnings[slug] = gold_doc.warnings

        recorded_sha = document.get("source_sha256")
        if recorded_sha and recorded_sha != gold_doc.pdf_sha256:
            excluded.append({
                "doc_slug": slug, "reason": EXCLUDED_PDF_MISMATCH,
                "detail": f"gold {gold_doc.pdf_sha256[:12]}… vs source {recorded_sha[:12]}…; "
                          "page numbers may be stale"})
            continue

        try:
            documents.append(score_document(slug, document, gold_doc, overrides))
        except Exception as exc:  # one bad document must not lose the rest
            excluded.append({"doc_slug": slug, "reason": EXCLUDED_DETECTION,
                             "detail": f"{type(exc).__name__}: {exc}"})

    def summarise_group(group: list) -> dict:
        return {
            "raw": metrics.summarise([doc["raw"] for doc in group]),
            "post_override": metrics.summarise(
                [doc["post_override"] or doc["raw"] for doc in group]),
        }

    # `raw` / `post_override` stay the all-documents summary; the tuning and
    # held-out groups sit alongside. A held-out file is read only at acceptance.
    summary = summarise_group(documents)
    summary["tuning"] = summarise_group([d for d in documents if not d["held_out"]])
    summary["held_out"] = summarise_group([d for d in documents if d["held_out"]])
    return {
        "source": {"kind": source["kind"], "drifted": source["drifted"]},
        "documents": documents,
        "summary": summary,
        "excluded": excluded,
        "warnings": warnings,
    }


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

def _pct(value) -> str:
    return "   -" if value is None else f"{value * 100:4.0f}%"


def _num(value) -> str:
    return "  -" if value is None else f"{value:5.2f}"


def format_table(report: dict) -> str:
    header = (f"{'document':<44} {'method':<10} {'tree':<12} {'gold':>4} {'pred':>4} "
              f"{'P':>6} {'R':>6} {'F1':>6} {'P±1':>6} {'R±1':>6} {'F1±1':>6} "
              f"{'pages':>6} {'titles':>6}  ok")
    lines = [header, "-" * len(header)]
    for doc in report["documents"]:
        variants = [("raw", doc["raw"])]
        if doc["post_override"] is not None:
            variants.append(("post=publish", doc["post_override"]))
        for label, score in variants:
            lines.append(
                f"{doc['doc_slug']:<44} {doc['method']:<10} {label:<12} "
                f"{score['gold_chapters']:>4} {score['predicted_chapters']:>4} "
                f"{_num(score['exact']['precision']):>6} {_num(score['exact']['recall']):>6} "
                f"{_num(score['exact']['f1']):>6} "
                f"{_num(score['tolerant']['precision']):>6} {_num(score['tolerant']['recall']):>6} "
                f"{_num(score['tolerant']['f1']):>6} "
                f"{_pct(score['page_accuracy']):>6} {_pct(score['title_accuracy']):>6} "
                f" {'yes' if score['fully_correct'] else 'no'}"
                + ("  [held out]" if doc.get("held_out") else ""))
    return "\n".join(lines)


def format_summary(report: dict) -> str:
    lines = []
    documents = report["documents"]
    has_held_out = any(doc.get("held_out") for doc in documents)
    # Without held-out documents there is one group, exactly as before.
    groups = [("", report["summary"], documents)]
    if has_held_out:
        groups = [
            (" [all]", report["summary"], documents),
            (" [tuning]", report["summary"]["tuning"],
             [d for d in documents if not d.get("held_out")]),
            (" [held out]", report["summary"]["held_out"],
             [d for d in documents if d.get("held_out")]),
        ]
    for suffix, group_summary, group_docs in groups:
        for name in ("raw", "post_override"):
            summary = group_summary[name]
            if name == "post_override" and not any(
                    doc["post_override"] is not None for doc in group_docs):
                continue
            label = "published tree (post-override)" if name == "post_override" else "raw tree"
            lines.append(f"\n{label}{suffix}: {summary['documents']} documents, "
                         f"{summary['fully_correct']}/{summary['documents']} fully correct")
            lines.append(f"  {'metric':<28} {'macro':>8} {'micro':>8}")
            for key in metrics.METRIC_KEYS:
                lines.append(f"  {key:<28} {_num(summary['macro'][key]):>8} "
                             f"{_num(summary['micro'][key]):>8}")
    return "\n".join(lines)


def format_warnings(report: dict) -> str:
    lines = []
    for slug in sorted(report["warnings"]):
        lines.append(f"\ngold warnings — {slug}:")
        for warning in report["warnings"][slug]:
            lines.append(f"  - {warning}")
    return "\n".join(lines)


def format_excluded(report: dict) -> str:
    if not report["excluded"]:
        return ""
    lines = ["\nnot scored:"]
    for entry in report["excluded"]:
        detail = f" — {entry['detail']}" if entry.get("detail") else ""
        lines.append(f"  {entry['doc_slug']}: {entry['reason']}{detail}")
    return "\n".join(lines)


def format_drift(report: dict) -> str:
    drifted = report["source"]["drifted"]
    if not drifted:
        return ""
    lines = [f"\nwarning: {len(drifted)} document(s) drifted from the snapshot "
             "(run eval/make_input.py to rebuild it):"]
    for entry in drifted:
        lines.append(f"  {entry['doc_slug']}: {entry['detail']}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Baseline
# --------------------------------------------------------------------------

def baseline_payload(report: dict) -> dict:
    return {
        "schema": 1,
        "source": report["source"]["kind"],
        "documents": [
            {"doc_slug": doc["doc_slug"], "method": doc["method"],
             "has_overrides": doc["has_overrides"], "held_out": doc["held_out"],
             "raw": doc["raw"], "post_override": doc["post_override"]}
            for doc in report["documents"]
        ],
        "summary": report["summary"],
    }


def _flatten(score: dict) -> dict:
    flat = {}
    for prefix in ("exact", "tolerant"):
        for key, value in score[prefix].items():
            flat[f"{prefix}_{key}"] = value
    for key in ("page_accuracy", "title_accuracy"):
        flat[key] = score.get(key)
    return flat


def format_baseline_diff(report: dict, baseline: dict) -> str:
    old_docs = {entry["doc_slug"]: entry for entry in baseline.get("documents", [])}
    new_docs = {doc["doc_slug"]: doc for doc in report["documents"]}
    lines = ["\nchange from baseline (eval/baseline.json):"]
    changed = False
    for slug in sorted(set(old_docs) | set(new_docs)):
        if slug not in old_docs:
            lines.append(f"  {slug}: new document (not in baseline)")
            changed = True
            continue
        if slug not in new_docs:
            lines.append(f"  {slug}: no longer scored")
            changed = True
            continue
        old, new = old_docs[slug], new_docs[slug]
        for label, old_score, new_score in (("raw", old.get("raw"), new.get("raw")),
                                            ("published", old.get("post_override") or old.get("raw"),
                                             new.get("post_override") or new.get("raw"))):
            if not old_score or not new_score:
                continue
            old_flat, new_flat = _flatten(old_score), _flatten(new_score)
            deltas = []
            for key in ("page_accuracy", "title_accuracy", "exact_f1", "tolerant_f1",
                        "exact_precision", "exact_recall"):
                old_value, new_value = old_flat.get(key), new_flat.get(key)
                if old_value is None or new_value is None:
                    continue
                delta = new_value - old_value
                if abs(delta) > 1e-9:
                    deltas.append(f"{key} {old_value:.2f} -> {new_value:.2f} ({delta:+.2f})")
            if deltas:
                lines.append(f"  {slug} [{label}]: " + "; ".join(deltas))
                changed = True
    if not changed:
        lines.append("  no per-document change")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Gold-versus-gold comparison
# --------------------------------------------------------------------------

def load_gold_file(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    errors = gold_module.validate_gold(data)
    if errors:
        raise SystemExit(f"{path} is not a valid gold file: " + "; ".join(errors))
    return data


def compare_gold(first_path, second_path, baseline_path=None) -> str:
    first = load_gold_file(first_path)
    second = load_gold_file(second_path)
    if first["doc_slug"] != second["doc_slug"]:
        raise SystemExit(
            f"the two gold files are for different documents: "
            f"{first['doc_slug']!r} and {second['doc_slug']!r}")
    slug = first["doc_slug"]
    page_count = max(chapter["pdf_page"] for chapter in first["chapters"])
    page_count = max(page_count, max(chapter["pdf_page"] for chapter in second["chapters"]))
    snapshot = None
    if INPUT_PATH.exists():
        try:
            snapshot = load_snapshot()
        except SystemExit:
            snapshot = None
    if snapshot and slug in snapshot["documents"]:
        page_count = int(snapshot["documents"][slug].get("page_count") or page_count)

    predicted = metrics.gold_as_predicted(second["chapters"])
    result = metrics.score(first["chapters"], predicted, page_count)
    differences = metrics.disagreements(first["chapters"], predicted)
    lines = [
        f"gold reference: {first_path}  (reviewed: {first['reviewed']})",
        f"other gold:     {second_path}  (reviewed: {second['reviewed']})",
        f"document:       {slug}  ({page_count} pages)",
        "",
        f"exact boundary   P {_num(result['exact']['precision'])}  "
        f"R {_num(result['exact']['recall'])}  F1 {_num(result['exact']['f1'])}",
        f"±1 boundary      P {_num(result['tolerant']['precision'])}  "
        f"R {_num(result['tolerant']['recall'])}  F1 {_num(result['tolerant']['f1'])}",
        f"page attribution {_pct(result['page_accuracy'])}   "
        f"title accuracy {_pct(result['title_accuracy'])}   "
        f"fully correct: {'yes' if result['fully_correct'] else 'no'}",
        "",
        f"disagreements: {len(differences)}",
    ]
    lines.extend(f"  - {item}" for item in differences)
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Gold-file check (validation + warnings, including unreviewed drafts)
# --------------------------------------------------------------------------

def check_gold(gold_dir, source: dict | None) -> tuple:
    """Validate every gold file and print consistency warnings.

    Unlike the report, this includes drafts (`reviewed: false`), so a reviewer
    can see the outstanding warnings before flipping the flag. Returns
    `(lines, error_count)`.
    """
    gold_dir = Path(gold_dir)
    lines = [f"gold check: {gold_dir}"]
    errors_found = 0
    paths = sorted(path for path in gold_dir.glob("*.json")
                   if path.name != gold_module.NO_TOC_FILENAME)
    if not paths:
        return lines + ["  no gold files"], 0
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            lines.append(f"  {path.stem}: MALFORMED — invalid JSON ({exc})")
            errors_found += 1
            continue
        errors = gold_module.validate_gold(data, expected_slug=path.stem)
        if errors:
            lines.append(f"  {path.stem}: MALFORMED — " + "; ".join(errors))
            errors_found += 1
            continue

        state = "reviewed" if data["reviewed"] is True else "DRAFT (reviewed is not true)"
        lines.append(f"  {path.stem}: valid, {state}, {len(data['chapters'])} chapters")
        document = (source or {}).get("documents", {}).get(data["doc_slug"])
        if document is None:
            lines.append("    (not in the source — title warnings cannot be checked)")
            continue
        gold_doc = gold_module.GoldDocument(
            doc_slug=data["doc_slug"], pdf_sha256=data["pdf_sha256"],
            toc_pdf_pages=data["toc_pdf_pages"], reviewed=bool(data["reviewed"]),
            chapters=[dict(chapter) for chapter in data["chapters"]],
            annotator=data["annotator"], annotated_on=data["annotated_on"],
            notes=data["notes"])
        if data["pdf_sha256"] != document.get("source_sha256"):
            lines.append("    gold/PDF mismatch — page numbers may be stale")
            errors_found += 1
        for warning in gold_module.consistency_warnings(gold_doc, document["pages"]):
            lines.append(f"    warning: {warning}")
    return lines, errors_found


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Score detect_structure's chapter split against gold chapter lists")
    parser.add_argument("--live", action="store_true",
                        help="score current extract_pages output instead of the committed snapshot")
    parser.add_argument("--gold", default=str(GOLD_DIR), metavar="DIR",
                        help=f"gold directory (default: {GOLD_DIR})")
    parser.add_argument("--json", metavar="PATH",
                        help="also write the machine-readable result to PATH")
    parser.add_argument("--baseline", default=str(BASELINE_PATH), metavar="PATH",
                        help=f"baseline to diff against (default: {BASELINE_PATH})")
    parser.add_argument("--refresh-baseline", action="store_true",
                        help="rewrite the baseline from this run (the only default-mode write)")
    parser.add_argument("--compare-gold", nargs=2, metavar=("A", "B"),
                        help="score one gold file against another (re-annotation agreement)")
    parser.add_argument("--check-gold", action="store_true",
                        help="validate every gold file and print its warnings, drafts included")
    args = parser.parse_args(argv)

    if args.check_gold:
        snapshot = None
        if INPUT_PATH.exists():
            try:
                snapshot = load_snapshot()
            except SystemExit:
                snapshot = None
        lines, errors_found = check_gold(args.gold, snapshot)
        print("\n".join(lines))
        return 1 if errors_found else 0

    if args.compare_gold:
        print(compare_gold(args.compare_gold[0], args.compare_gold[1]))
        return 0

    snapshot = None
    if INPUT_PATH.exists():
        try:
            snapshot = load_snapshot()
        except SystemExit:
            snapshot = None
    source = load_live(snapshot) if args.live else load_snapshot()

    gold_load = gold_module.load_gold(Path(args.gold))
    overrides = load_overrides(_STEP_DIR)
    report = build_report(source, gold_load, overrides)

    print(format_table(report))
    print(format_summary(report))
    print(format_drift(report))
    print(format_warnings(report))
    print(format_excluded(report))

    baseline_path = Path(args.baseline)
    if args.refresh_baseline:
        baseline_path.write_text(
            json.dumps(baseline_payload(report), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
        print(f"\nWrote baseline {baseline_path}")
    elif baseline_path.exists():
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        print(format_baseline_diff(report, baseline))

    if args.json:
        Path(args.json).write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nWrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
