"""Reconcile extracted Climate Action Plan annex actions against the XLSX annexes.

The DCEE publishes the same annexes as XLSX workbooks. They are an independent
reference list: this script checks that every reference printed there for an
edition was extracted from that edition's PDF.

  * missing   - in the XLSX, not extracted from the PDF (blocking)
  * text      - in both, but the action text differs (fix or record a reason)
  * extra     - extracted, in no XLSX (informational)

An XLSX row belongs to the edition named by the year in its code (EL/24/6/A is
a 2024 action wherever it is printed), matching the pipeline's year rule.
The workbooks are untrusted input: read them with `python -I`.

Usage:
    python -I scripts/reconcile_climate_action_plan_annexes.py XLSX_DIR [--json]
"""
import argparse
import difflib
import json
import re
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RESOLVED = REPO / "pipelines/actions_pipeline/steps/resolve_action_identity/output.json"
EDITION_SLUG = "climate-action-plan-{year}-annex-of-actions"
CODE = re.compile(r"^[A-Z]{2}/(\d{2})/\d+(?:/[A-Z])?$")
REFERENCE_COLUMN, TEXT_COLUMN = 3, 4
SIMILARITY = 0.85
PLACEHOLDERS = {"", "-"}


def edition_of(reference):
    m = CODE.match(reference)
    return 2000 + int(m.group(1)) if m else None


def normalise(text):
    text = unicodedata.normalize("NFKC", str(text or "")).casefold()
    return re.sub(r"[^a-z0-9]+", "", text)


def load_reference(xlsx_dir):
    import openpyxl
    out = {}
    for path in sorted(Path(xlsx_dir).glob("*.xlsx")):
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        for ws in wb.worksheets:
            for row in list(ws.iter_rows(values_only=True))[1:]:
                if len(row) <= REFERENCE_COLUMN or row[REFERENCE_COLUMN] is None:
                    continue
                ref = re.sub(r"\s+", "", str(row[REFERENCE_COLUMN]).replace("\xa0", " "))
                year = edition_of(ref)
                if year is None:
                    continue
                text = row[TEXT_COLUMN] if len(row) > TEXT_COLUMN else ""
                entry = out.setdefault(year, {}).setdefault(
                    ref, {"text": " ".join(str(text or "").split()), "sources": []})
                entry["sources"].append(f"{path.name}:{ws.title}")
    return out


def _same_text(a, b):
    na, nb = normalise(a), normalise(b)
    if na == nb or (na and nb and (na in nb or nb in na)):
        return True
    return difflib.SequenceMatcher(None, na, nb).ratio() >= SIMILARITY


def _parent_text(ref, extracted):
    parts = ref.split("/")
    while len(parts) > 3:
        parts.pop()
        text = extracted.get("/".join(parts))
        if text is not None and text.strip() not in PLACEHOLDERS:
            return text
    return None


def reconcile(extracted, reference):
    """extracted: {reference: text}; reference: {reference: {"text", "sources"}}."""
    missing = sorted(set(reference) - set(extracted))
    extra = sorted(set(extracted) - set(reference))
    mismatches, placeholders, matched = [], [], 0
    for ref in sorted(set(reference) & set(extracted)):
        if extracted[ref].strip() in PLACEHOLDERS:
            # The PDF prints "-" in a sub-action's Actions cell: the text is
            # the parent row's. Accepted when the XLSX text is the parent's.
            parent = _parent_text(ref, extracted)
            if parent is not None and _same_text(parent, reference[ref]["text"]):
                placeholders.append(ref)
                continue
        if _same_text(extracted[ref], reference[ref]["text"]):
            matched += 1
        else:
            mismatches.append({"reference": ref, "extracted": extracted[ref],
                               "xlsx": reference[ref]["text"]})
    return {"matched": matched, "placeholder_text": placeholders,
            "missing": missing, "text_mismatches": mismatches, "extra": extra}


def extracted_by_edition(path=RESOLVED):
    actions = json.loads(Path(path).read_text())["actions"]
    out = {}
    for a in actions:
        slug = a["plan_slug"]
        m = re.fullmatch(r"climate-action-plan-(20\d{2})-annex-of-actions", slug)
        if m:
            out.setdefault(int(m.group(1)), {})[a["action_number"]] = a["action_text"]
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("xlsx_dir")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    reference = load_reference(args.xlsx_dir)
    extracted = extracted_by_edition()
    report = {}
    for year in sorted(set(reference) | set(extracted)):
        r = reconcile(extracted.get(year, {}), reference.get(year, {}))
        r.update(edition=EDITION_SLUG.format(year=year),
                 extracted=len(extracted.get(year, {})),
                 xlsx=len(reference.get(year, {})))
        report[year] = r
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for year, r in report.items():
            print(f"{r['edition']}: extracted {r['extracted']}, xlsx {r['xlsx']}, "
                  f"matched {r['matched']}, dash-for-parent {len(r['placeholder_text'])}, missing {len(r['missing'])}, "
                  f"text {len(r['text_mismatches'])}, extra {len(r['extra'])}")
            for ref in r["missing"]:
                print(f"  MISSING {ref}")
            for m in r["text_mismatches"]:
                print(f"  TEXT {m['reference']}\n    pdf : {m['extracted'][:110]}\n    xlsx: {m['xlsx'][:110]}")
            for ref in r["extra"]:
                print(f"  extra {ref}")
    return 1 if any(r["missing"] for r in report.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
