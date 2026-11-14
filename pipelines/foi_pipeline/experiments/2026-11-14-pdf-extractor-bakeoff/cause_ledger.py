"""Cause ledger: classify every canonicalize_rows error by likely cause.

Acceptance instrument for role-aware selection. Run with --label to write a
markdown ledger; build_ledger / per_file_cross_role_rate are reused by later tasks.
"""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

_HERE = Path(__file__).resolve()
_SRC = _HERE.parents[4] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from lib.requester_type_map import canonicalize_requester_type  # noqa: E402
from lib.status_map import _STATUS_LOOKUP, _normalize_status, canonicalize_status  # noqa: E402
from lib.value_kinds import cell_kinds, foreign_kind, strip_value_punctuation  # noqa: E402

CLASSES = ["text_variant", "glyph_split", "composite_cell", "cross_role",
           "header_mapping", "unknown_value", "other"]
_GLYPH_RE = re.compile(r"\b[A-Z](?:\s+[A-Z])*\s+[a-z]")
_REQUESTER_TYPES = {"UnrecognizedRequesterType"}
_STATUS_TYPES = {"UnrecognizedDecisionStatus", "StatusValueIsDate", "StatusValueIsColumnHeader"}
HEADER_SHARE = 0.8
UNIFORMITY_MIN = 0.92
CANON = "extract_disclosures_canonicalize_rows"
ASSESS = "assess_table_structure"


def _exact_status(text: str) -> bool:
    """Exact synonym match; canonicalize_status also matches substrings."""
    return _normalize_status(text) in _STATUS_LOOKUP


def _field_value(error: dict):
    etype = error.get("error_type")
    ctx = error.get("context") or {}
    if etype in _REQUESTER_TYPES:
        return "requester_type", ctx.get("raw_requester_type")
    if etype in _STATUS_TYPES:
        return "decision_status", ctx.get("raw_status")
    return None, None


def classify_error(error: dict) -> str:
    field, value = _field_value(error)
    if field is None or value is None:
        return "other"
    value = str(value)
    stripped = strip_value_punctuation(value)
    canon = canonicalize_requester_type if field == "requester_type" else canonicalize_status
    if canon(stripped) is not None:
        return "text_variant"
    if _GLYPH_RE.search(" ".join(value.split())):
        return "glyph_split"
    tokens = stripped.split()
    if len(tokens) > 1 and not _exact_status(stripped) and _exact_status(tokens[0]):
        return "composite_cell"
    if foreign_kind(value, field) is not None:
        return "cross_role"
    return "unknown_value"


def _load_list(path: Path, key: str | None = None) -> list:
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    if isinstance(data, dict):
        data = data.get(key or "results", [])
    return data if isinstance(data, list) else []


def _is_misplaced(rec: dict) -> bool:
    ref = rec.get("foi_reference_id")
    if ref:
        kinds = cell_kinds(ref)
        if kinds & {"status", "requester"} and "reference" not in kinds:
            return True
    desc = rec.get("request_description")
    if desc:
        s = strip_value_punctuation(desc)
        if s and (_exact_status(s)
                  or canonicalize_requester_type(s) is not None):
            return True
    return False


def _load(steps_dir: Path):
    errors = _load_list(steps_dir / CANON / "errors.json")
    records = _load_list(steps_dir / CANON / "output.json")
    assess = {r.get("file_url"): r for r in _load_list(steps_dir / ASSESS / "output.json")}
    return errors, records, assess


def _file_classes(errors: list, assess: dict) -> dict[str, list[str]]:
    """Per-file class list, with cross_role upgraded to header_mapping per file."""
    by_file: dict[str, list[str]] = defaultdict(list)
    for e in errors:
        by_file[(e.get("context") or {}).get("file_url")].append(classify_error(e))
    out = {}
    for url, classes in by_file.items():
        u = ((assess.get(url) or {}).get("table_structure") or {}).get("width_uniformity")
        if (u is not None and u >= UNIFORMITY_MIN
                and classes.count("cross_role") / len(classes) >= HEADER_SHARE):
            classes = ["header_mapping" if c == "cross_role" else c for c in classes]
        out[url] = classes
    return out


def build_ledger(steps_dir: Path) -> dict:
    errors, records, assess = _load(Path(steps_dir))
    file_classes = _file_classes(errors, assess)
    # reconstruct per-error class aligned with errors, using the file-level upgrade
    upgraded = {u for u, c in file_classes.items() if "header_mapping" in c}
    by_class: Counter = Counter()
    by_class_body: dict[str, Counter] = defaultdict(Counter)
    files: dict = {}
    unknown: dict = {}
    for e in errors:
        ctx = e.get("context") or {}
        cls = classify_error(e)
        url = ctx.get("file_url")
        if cls == "cross_role" and url in upgraded:
            cls = "header_mapping"
        body = ctx.get("public_body_id")
        by_class[cls] += 1
        by_class_body[cls][body] += 1
        f = files.setdefault(url, {"file_url": url, "body": body, "errors": 0,
                                   "classes": Counter(),
                                   "pdf_extractor": (assess.get(url) or {}).get("pdf_extractor"),
                                   "rows": 0})
        f["errors"] += 1
        f["classes"][cls] += 1
        if cls == "unknown_value":
            _, v = _field_value(e)
            u = unknown.setdefault(str(v), {"value": str(v), "count": 0, "bodies": Counter()})
            u["count"] += 1
            u["bodies"][body] += 1
    rec_counts = Counter(r.get("file_url") for r in records)
    for url, f in files.items():
        f["rows"] = rec_counts.get(url, 0)
        f["class"] = f["classes"].most_common(1)[0][0]
    top = sorted(files.values(), key=lambda f: -f["errors"])[:30]
    misplaced = [r for r in records if _is_misplaced(r)]
    return {
        "total": sum(by_class.values()),
        "by_class": dict(by_class),
        "by_class_body": {c: dict(b) for c, b in by_class_body.items()},
        "top_files": top,
        "misplaced_published": len(misplaced),
        "misplaced_examples": [
            {"file_url": r.get("file_url"), "foi_reference_id": r.get("foi_reference_id"),
             "request_description": str(r.get("request_description"))[:60]}
            for r in misplaced[:20]],
        "unknown_values": sorted(unknown.values(), key=lambda u: -u["count"]),
    }


def per_file_cross_role_rate(steps_dir: Path) -> dict[str, float]:
    errors, records, assess = _load(Path(steps_dir))
    fc = _file_classes(errors, assess)
    rec_counts = Counter(r.get("file_url") for r in records)
    rates = {}
    for url, classes in fc.items():
        n = sum(1 for c in classes if c in ("cross_role", "header_mapping"))
        denom = rec_counts.get(url, 0) + len(classes)
        rates[url] = n / denom if denom else 0.0
    return rates


def render(ledger: dict, label: str) -> str:
    L = [f"# Cause ledger: {label}", "", f"Total errors: {ledger['total']}", "",
         "## Totals by class", "", "| class | errors |", "|---|---|"]
    for c in CLASSES:
        L.append(f"| {c} | {ledger['by_class'].get(c, 0)} |")
    L += ["", "## Class by top-10 bodies (public_body_id: errors)", ""]
    for c in CLASSES:
        b = ledger["by_class_body"].get(c)
        if b:
            top = sorted(b.items(), key=lambda kv: -kv[1])[:10]
            L.append(f"- **{c}**: " + ", ".join(f"{k}: {v}" for k, v in top))
    L += ["", "## Top 30 files by errors", "",
          "| class | pdf_extractor | rows | errors | body | file |", "|---|---|---|---|---|---|"]
    for f in ledger["top_files"]:
        L.append(f"| {f['class']} | {f['pdf_extractor']} | {f['rows']} | {f['errors']} "
                 f"| {f['body']} | {f['file_url']} |")
    L += ["", f"## misplaced_published: {ledger['misplaced_published']}", ""]
    for m in ledger["misplaced_examples"]:
        L.append(f"- {m['file_url']}: ref={m['foi_reference_id']!r} desc={m['request_description']!r}")
    L += ["", "## unknown_value list", "", "| value | count | bodies |", "|---|---|---|"]
    for u in ledger["unknown_values"]:
        bodies = ", ".join(str(b) for b, _ in u["bodies"].most_common(5))
        value = u["value"].replace("|", "\\|").replace("\n", " ")
        L.append(f"| {value} | {u['count']} | {bodies} |")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps-dir", type=Path, required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    ledger = build_ledger(a.steps_dir)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(render(ledger, a.label))
    print(f"{ledger['total']} errors; by class: {ledger['by_class']}; "
          f"misplaced_published={ledger['misplaced_published']}")


if __name__ == "__main__":
    main()
