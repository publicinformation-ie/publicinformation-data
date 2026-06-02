#!/usr/bin/env python3
"""North-star metric: valid FOI records + bodies with >=1 valid record.

Label-free — scores the pipeline's own canonical output against a validity
rule, so it is cheap and runs every --headline. Field names map via
eval_utils.HEADLINE_FIELDS (spec uses aspirational names; output uses
request_description / decision_status).
"""
import json
from datetime import datetime
from pathlib import Path

DATE_FIELD = "decision_date"
SUMMARY_FIELD = "request_description"        # spec: disclosure_request_summary
BONUS_FIELDS = ["decision_status", "foi_reference_id"]
FUNNEL_STEPS = [
    "find_disclosure_files", "transform_disclosure_files",
    "extract_disclosures_detect_header_row", "extract_disclosures_canonicalize",
]


def _parses_as_date(value) -> bool:
    if not value:
        return False
    try:
        datetime.fromisoformat(str(value))
        return True
    except ValueError:
        return False


def is_valid_record(rec) -> bool:
    """decision_date parses to a real date AND summary is non-empty."""
    return _parses_as_date(rec.get(DATE_FIELD)) and bool((rec.get(SUMMARY_FIELD) or "").strip())


def compute_headline(records: list) -> dict:
    valid = [r for r in records if is_valid_record(r)]
    bodies = {r.get("public_body_id") for r in valid}
    n = len(records) or 1
    bonus = {f: round(sum(1 for r in records if r.get(f) not in (None, "")) / n, 3)
             for f in BONUS_FIELDS}
    return {"valid_records": len(valid), "bodies_with_record": len(bodies),
            "bonus_coverage": bonus}


def compute_funnel(steps_dir: Path) -> dict:
    """Files surviving each stage (len of results array per step output.json)."""
    funnel = {}
    for step in FUNNEL_STEPS:
        out = Path(steps_dir) / step / "output.json"
        if out.exists():
            data = json.loads(out.read_text())
            funnel[step] = len(data.get("results", []))
    return funnel


def print_headline(pipeline_dir: Path):
    steps_dir = Path(pipeline_dir) / "steps"
    out = steps_dir / "extract_disclosures_canonicalize" / "output.json"
    records = json.loads(out.read_text())["results"]
    h = compute_headline(records)
    funnel = compute_funnel(steps_dir)

    baseline_path = Path(pipeline_dir) / "baseline.json"
    base = json.loads(baseline_path.read_text()).get("headline", {}) if baseline_path.exists() else {}

    def delta(key):
        if key in base:
            d = h[key] - base[key]
            arrow = "▲" if d > 0 else ("▼" if d < 0 else "■")
            return f"   (baseline {base[key]}  {arrow} {d:+d})"
        return ""

    print("\nEnd-to-end " + "─" * 40)
    print(f"Valid FOI records:    {h['valid_records']:>7}{delta('valid_records')}")
    print(f"Bodies with >=1 record:{h['bodies_with_record']:>6}{delta('bodies_with_record')}")
    print(f"Bonus coverage: {h['bonus_coverage']}")
    if funnel:
        print("Funnel: " + " → ".join(f"{k}={v}" for k, v in funnel.items()))
    return h, funnel
