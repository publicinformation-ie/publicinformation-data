#!/usr/bin/env python3
"""PDF extractor comparison: pdfplumber vs camelot lattice vs camelot stream.

Run from repo root:
    cd foi_pipeline && uv run python experiments/2026-06-09-pdf-extraction-comparison/run.py
"""
import argparse
import hashlib
import io
import json
import os
import re
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).parent
_FOI_PIPELINE = _HERE.parents[1]
sys.path.insert(0, str(_FOI_PIPELINE))

from steps.transform_disclosure_files.process import _DEFAULT_PDF_TABLE_SETTINGS, serialise_cell

_CACHE_DIR = _FOI_PIPELINE / "steps/transform_disclosure_files/cache"
_OUTPUT_JSON = _FOI_PIPELINE / "steps/transform_disclosure_files/output.json"
_LABELS_PATH = _HERE / "labels.jsonl"
_RESULTS_PATH = _HERE / "results.json"

_DATE_RE = re.compile(r"\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}")


# ---------------------------------------------------------------------------
# Scoring utilities
# ---------------------------------------------------------------------------

def apply_merge_groups(rows, merge_groups):
    """Apply merge_groups to rows, returning ground-truth rows.

    merge_groups is a list of index lists, e.g. [[0, 1], [3, 4, 5]].
    The first index in each group is the primary row; subsequent indices are
    continuation rows whose non-null cells are appended to the primary.
    Continuation rows are dropped from the output.
    """
    primary_to_conts = {}
    absorbed = set()
    for group in merge_groups:
        if len(group) < 2:
            continue
        primary_to_conts[group[0]] = group[1:]
        absorbed.update(group[1:])

    result = []
    for i, row in enumerate(rows):
        if i in absorbed:
            continue
        if i in primary_to_conts:
            merged = list(row)
            ncols = len(merged)
            for cont_idx in primary_to_conts[i]:
                if cont_idx >= len(rows):
                    continue
                for col_idx, cell in enumerate(rows[cont_idx]):
                    if cell is not None and col_idx < ncols:
                        if merged[col_idx] is not None:
                            merged[col_idx] = str(merged[col_idx]) + " " + str(cell)
                        else:
                            merged[col_idx] = str(cell)
            result.append(merged)
        else:
            result.append(list(row))
    return result


def row_to_text(row):
    """Concatenate non-null cells, whitespace-normalised."""
    parts = [str(cell).strip() for cell in row if cell is not None and str(cell).strip()]
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def score_extractor(ground_truth, extracted):
    """Score an extractor's output against ground truth rows.

    Returns dict with row_count_match (bool), exact_row_match (bool),
    expected_rows (int), actual_rows (int), exact_matches (int).
    """
    extracted_texts = {row_to_text(r) for r in extracted}
    exact_matches = sum(
        1 for expected in ground_truth if row_to_text(expected) in extracted_texts
    )
    return {
        "row_count_match": len(extracted) == len(ground_truth),
        "exact_row_match": exact_matches == len(ground_truth),
        "expected_rows": len(ground_truth),
        "actual_rows": len(extracted),
        "exact_matches": exact_matches,
    }


# ---------------------------------------------------------------------------
# Extractors
# ---------------------------------------------------------------------------

def extract_with_pdfplumber(file_bytes):
    """Extract rows using pdfplumber with pipeline's default settings."""
    import pdfplumber
    rows = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables(table_settings=_DEFAULT_PDF_TABLE_SETTINGS):
                for row in table:
                    rows.append([serialise_cell(cell)[0] for cell in row])
    return rows


def extract_with_camelot(file_bytes, flavor):
    """Extract rows using camelot. Returns None if camelot is unavailable or fails."""
    try:
        import camelot  # type: ignore[import-untyped]
    except ImportError:
        print(f"WARNING: camelot not installed (brew install ghostscript && uv add camelot-py[cv])",
              file=sys.stderr)
        return None

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(file_bytes)
        tmp_path = f.name

    try:
        tables = camelot.read_pdf(tmp_path, flavor=flavor, pages="all")
        rows = []
        for table in tables:
            for _, row in table.df.iterrows():
                rows.append([cell if cell != "" else None for cell in row.tolist()])
        return rows
    except Exception as e:
        print(f"WARNING: camelot {flavor} failed: {e}", file=sys.stderr)
        return None
    finally:
        os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Comparison loop
# ---------------------------------------------------------------------------

_EXTRACTORS = [
    ("pdfplumber", lambda b: extract_with_pdfplumber(b)),
    ("camelot_lattice", lambda b: extract_with_camelot(b, "lattice")),
    ("camelot_stream", lambda b: extract_with_camelot(b, "stream")),
]


def _cache_bytes(file_url):
    """Return bytes from cache, or None if not cached."""
    key = hashlib.sha256(file_url.encode()).hexdigest()
    path = _CACHE_DIR / f"{key}.bytes"
    return path.read_bytes() if path.exists() else None


def run_comparison(labels_path):
    """Load labels.jsonl, run all extractors, return per_file results list."""
    labels = [
        json.loads(line)
        for line in labels_path.read_text().splitlines()
        if line.strip()
    ]

    per_file = []
    for item in labels:
        file_url = item["file_url"]
        file_bytes = _cache_bytes(file_url)
        if file_bytes is None:
            print(f"WARNING: cache miss — skipping {file_url}", file=sys.stderr)
            continue

        baseline_rows = extract_with_pdfplumber(file_bytes)
        ground_truth = apply_merge_groups(baseline_rows, item.get("merge_groups", []))

        record = {
            "file_url": file_url,
            "public_body_id": item["public_body_id"],
            "tier": item["tier"],
            "ground_truth_rows": len(ground_truth),
        }

        for name, extractor_fn in _EXTRACTORS:
            extracted = extractor_fn(file_bytes)
            record[name] = (
                {"error": "extraction_failed"}
                if extracted is None
                else score_extractor(ground_truth, extracted)
            )

        per_file.append(record)
        print(f"  [{item['tier']}] {file_url[-60:]}: gt={len(ground_truth)}")

    return per_file


def aggregate_results(per_file):
    """Aggregate per-file scores into a summary dict keyed by extractor name."""
    extractor_names = [name for name, _ in _EXTRACTORS]
    summary = {
        ext: {
            "row_count_match": 0, "exact_row_match": 0, "total": 0,
            "tier_1": {"row_count_match": 0, "exact_row_match": 0, "total": 0},
            "tier_2": {"row_count_match": 0, "exact_row_match": 0, "total": 0},
            "tier_3": {"row_count_match": 0, "exact_row_match": 0, "total": 0},
        }
        for ext in extractor_names
    }

    for r in per_file:
        tier_key = f"tier_{r['tier']}"
        for ext in extractor_names:
            data = r.get(ext, {})
            if "error" in data:
                continue
            summary[ext]["total"] += 1
            summary[ext][tier_key]["total"] += 1
            if data.get("row_count_match"):
                summary[ext]["row_count_match"] += 1
                summary[ext][tier_key]["row_count_match"] += 1
            if data.get("exact_row_match"):
                summary[ext]["exact_row_match"] += 1
                summary[ext][tier_key]["exact_row_match"] += 1

    return summary


def print_table(summary):
    """Print a formatted comparison table to stdout."""
    cols = ["pdfplumber", "camelot_lattice", "camelot_stream"]
    headers = ["pdfplumber", "camelot-lattice", "camelot-stream"]

    def fmt(val, total):
        return f"{val}/{total}"

    rows = [
        ("Row count match (all 30)", [
            fmt(summary[c]["row_count_match"], summary[c]["total"]) for c in cols
        ]),
        ("Exact row match (all 30)", [
            fmt(summary[c]["exact_row_match"], summary[c]["total"]) for c in cols
        ]),
        ("Tier 1 — row count match", [
            fmt(summary[c]["tier_1"]["row_count_match"], summary[c]["tier_1"]["total"]) for c in cols
        ]),
        ("Tier 2 — row count match", [
            fmt(summary[c]["tier_2"]["row_count_match"], summary[c]["tier_2"]["total"]) for c in cols
        ]),
        ("Tier 3 — row count match", [
            fmt(summary[c]["tier_3"]["row_count_match"], summary[c]["tier_3"]["total"]) for c in cols
        ]),
    ]

    col_w = 18
    print(f"\n{'Metric':<38}" + "".join(h.rjust(col_w) for h in headers))
    print("-" * (38 + col_w * 3))
    for label, vals in rows:
        print(f"{label:<38}" + "".join(v.rjust(col_w) for v in vals))
    print()


# ---------------------------------------------------------------------------
# Corpus-wide proxy scoring
# ---------------------------------------------------------------------------

def _count_null_heavy(rows):
    """Count rows where >50% of cells are None."""
    count = 0
    for row in rows:
        if not row:
            continue
        null_fraction = sum(1 for c in row if c is None) / len(row)
        if null_fraction > 0.5:
            count += 1
    return count


def _run_all_pdfs(flavor):
    """Proxy comparison: run camelot on all 1035 cached PDFs, report null-heavy reduction."""
    print(f"Loading transform output…")
    output_data = json.loads(_OUTPUT_JSON.read_text()).get("results", [])
    pdfs = [r for r in output_data if r.get("file_type") == "pdf"]

    null_heavy_baseline = 0
    null_heavy_challenger = 0
    total = 0
    skipped_cache = 0
    challenger_failures = 0

    for item in pdfs:
        key = hashlib.sha256(item["file_url"].encode()).hexdigest()
        cache_path = _CACHE_DIR / f"{key}.bytes"
        if not cache_path.exists():
            skipped_cache += 1
            continue

        file_bytes = cache_path.read_bytes()
        baseline = extract_with_pdfplumber(file_bytes)
        challenger = extract_with_camelot(file_bytes, flavor)

        total += 1
        null_heavy_baseline += _count_null_heavy(baseline)
        if challenger is None:
            challenger_failures += 1
            null_heavy_challenger += _count_null_heavy(baseline)
        else:
            null_heavy_challenger += _count_null_heavy(challenger)

        if total % 50 == 0:
            print(f"  {total}/{len(pdfs) - skipped_cache} files processed…")

    reduction = null_heavy_baseline - null_heavy_challenger
    proxy = {
        "flavor": flavor,
        "total_pdfs": total,
        "skipped_no_cache": skipped_cache,
        "challenger_failures": challenger_failures,
        "null_heavy_rows_pdfplumber": null_heavy_baseline,
        f"null_heavy_rows_camelot_{flavor}": null_heavy_challenger,
        "null_heavy_reduction": reduction,
        "reduction_pct": round(100 * reduction / null_heavy_baseline, 1) if null_heavy_baseline else 0,
    }

    proxy_path = _HERE / f"proxy_results_{flavor}.json"
    proxy_path.write_text(json.dumps(proxy, indent=2))
    print(f"\nWrote {proxy_path}")
    print(f"Null-heavy rows: pdfplumber={null_heavy_baseline}, "
          f"camelot-{flavor}={null_heavy_challenger}, "
          f"reduction={reduction} ({proxy['reduction_pct']}%)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Compare pdfplumber vs camelot on labeled PDF ground truth"
    )
    parser.add_argument(
        "--all-pdfs",
        metavar="FLAVOR",
        choices=["lattice", "stream"],
        help="Run proxy comparison on all 1035 PDFs (lattice or stream)",
    )
    args = parser.parse_args()

    if args.all_pdfs:
        _run_all_pdfs(args.all_pdfs)
        return

    if not _LABELS_PATH.exists():
        print(
            f"ERROR: {_LABELS_PATH} not found.\n"
            "Run sample.py first, fill in merge_groups, then copy to labels.jsonl.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("Running comparison…")
    per_file = run_comparison(_LABELS_PATH)
    summary = aggregate_results(per_file)

    results = {"per_file": per_file, "summary": summary}
    _RESULTS_PATH.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {_RESULTS_PATH}")

    print_table(summary)

    # Decision guidance
    lattice_delta = (
        summary["camelot_lattice"]["row_count_match"]
        - summary["pdfplumber"]["row_count_match"]
    )
    tier3_pdfplumber = summary["pdfplumber"]["tier_3"]["row_count_match"]
    tier3_lattice = summary["camelot_lattice"]["tier_3"]["row_count_match"]

    print("Decision guidance:")
    if lattice_delta >= 5 and tier3_lattice >= tier3_pdfplumber:
        print(f"  ADOPT camelot-lattice (delta={lattice_delta:+d}, tier3 no regression)")
    elif lattice_delta >= 5:
        print(f"  MIXED: lattice wins overall (+{lattice_delta}) but regresses on tier 3 — use hybrid detection")
    else:
        print(f"  INCONCLUSIVE: delta={lattice_delta:+d} < 5 — implement downstream reassembly instead")


if __name__ == "__main__":
    main()
