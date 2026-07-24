#!/usr/bin/env python3
import argparse
import copy
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import read_json, write_json, write_status

STEP_NAME = "export_status"


def merge_resolve_website_urls(body_map, step_data):
    for r in step_data["results"]:
        bid = r["public_body_id"]
        if bid in body_map:
            url = r.get("status", {}).get("website_url", {}).get("url")
            if url:
                body_map[bid]["status"]["website_url"]["url"] = url


def merge_validate_websites(body_map, step_data):
    for r in step_data["results"]:
        bid = r["public_body_id"]
        if bid in body_map:
            body_map[bid]["status"]["website_url"]["status"] = (
                "success" if r["is_reachable"] else "failed"
            )
            if r.get("overridden"):
                body_map[bid]["status"]["website_url"]["verified"] = True


def merge_find_foi_pages(body_map, step_data):
    for r in step_data["results"]:
        bid = r["public_body_id"]
        if bid in body_map:
            body_map[bid]["status"]["foi_page"]["url"] = r["foi_page_url"]
            body_map[bid]["status"]["foi_page"]["status"] = "success"
            if r.get("overridden"):
                body_map[bid]["status"]["foi_page"]["verified"] = True


def merge_check_foi_pages(body_map, step_data):
    for r in step_data["results"]:
        bid = r["public_body_id"]
        if bid in body_map:
            body_map[bid]["status"]["foi_page"]["status"] = (
                "success" if r["is_reachable"] else "failed"
            )


def merge_get_foi_emails(body_map, step_data):
    for r in step_data["results"]:
        bid = r["public_body_id"]
        if bid in body_map:
            body_map[bid]["status"]["foi_email"]["email"] = r.get("foi_email")
            body_map[bid]["status"]["foi_email"]["status"] = (
                "success" if r.get("email_status") == "found" else "failed"
            )
            if r.get("overridden"):
                body_map[bid]["status"]["foi_email"]["verified"] = True


def merge_find_disclosure_pages(body_map, step_data):
    for r in step_data["results"]:
        bid = r["public_body_id"]
        if bid in body_map:
            body_map[bid]["status"]["disclosures_page"]["url"] = r["disclosure_page_url"]
            body_map[bid]["status"]["disclosures_page"]["status"] = "success"
            if r.get("overridden"):
                body_map[bid]["status"]["disclosures_page"]["verified"] = True


def merge_find_disclosure_files(body_map, step_data):
    counts = defaultdict(int)
    for r in step_data["results"]:
        counts[r["public_body_id"]] += 1
    for bid, body in body_map.items():
        if bid in counts:
            total = counts[bid]
            body["status"]["disclosure_files"]["total"] = total
            body["status"]["disclosure_files"]["valid"] = total
            body["status"]["disclosure_files"]["failed"] = 0
            body["status"]["disclosure_files"]["status"] = "success" if total > 0 else "failed"
        else:
            body["status"]["disclosure_files"]["status"] = "failed"


def merge_transform_disclosure_files(body_map, step_data):
    counts = defaultdict(int)
    for r in step_data["results"]:
        if r.get("rows") is not None:
            counts[r["public_body_id"]] += 1
    for bid, body in body_map.items():
        if body["status"]["disclosure_files"]["total"] > 0:
            body["status"]["disclosure_files"]["valid"] = counts.get(bid, 0)


def merge_extract_disclosures_canonicalize(body_map, step_data):
    counts = defaultdict(int)
    for r in step_data["results"]:
        counts[r["public_body_id"]] += 1
    for bid, body in body_map.items():
        if bid in counts:
            total = counts[bid]
            body["status"]["foi_requests"]["valid"] = total
            body["status"]["foi_requests"]["errors"] = 0
            body["status"]["foi_requests"]["status"] = "success" if total > 0 else "failed"
        else:
            body["status"]["foi_requests"]["status"] = "failed"


STEP_MERGERS = {
    "validate_websites": merge_validate_websites,
    "find_foi_pages": merge_find_foi_pages,
    "check_foi_pages": merge_check_foi_pages,
    "get_foi_emails": merge_get_foi_emails,
    "find_disclosure_pages": merge_find_disclosure_pages,
    "find_disclosure_files": merge_find_disclosure_files,
    "transform_disclosure_files": merge_transform_disclosure_files,
    "extract_disclosures_canonicalize": merge_extract_disclosures_canonicalize,
    "extract_disclosures_deduplicate": merge_extract_disclosures_canonicalize,
}  # NOTE: disclosure-counting mergers must also be listed in DISCLOSURE_STEPS

# Steps whose output records MUST resolve to a canonical body. The orphan
# guard in merge() raises if any of these reference a public_body_id not in
# body_map. NON-disclosure mergers are deliberately EXEMPT: they may
# legitimately reference bodies outside the subject-to-FOI subset and skip
# them via `if bid in body_map`, so guarding them would false-positive.
# If you add a new merger that COUNTS disclosure records per body, add it here.
DISCLOSURE_STEPS = {
    "find_disclosure_files",
    "transform_disclosure_files",
    "extract_disclosures_canonicalize",
    "extract_disclosures_deduplicate",
}

# Per-body steps that resolve exactly one status field per canonical body via a
# `present` set. Coverage is measured for these: a canonical id absent from the
# step's output is a gap (now 'not_attempted', see merge_* funcs). Disclosure-
# counting steps are excluded — they legitimately produce zero records per body.
PER_BODY_STEPS = {
    "validate_websites",
    "find_foi_pages",
    "check_foi_pages",
    "get_foi_emails",
    "find_disclosure_pages",
}


def collect_disclosure_ids(step_data):
    """Return the set of public_body_ids referenced by a disclosure step's
    output. Mirrors how the mergers locate ids: each record under "results"
    carries a "public_body_id". Records missing the key are ignored here (the
    mergers would skip them too)."""
    return {
        r["public_body_id"]
        for r in step_data.get("results", [])
        if "public_body_id" in r
    }


def write_public_output(output, repo_root):
    public_dir = repo_root / "public"
    public_dir.mkdir(parents=True, exist_ok=True)
    public_path = public_dir / "pipeline-data.json"
    write_json(public_path, output)
    return public_path


def write_disclosure_files_output(steps_dir, repo_root):
    input_path = Path(steps_dir) / "find_disclosure_files" / "output.json"
    if not input_path.exists():
        return None
    data = read_json(input_path)
    records = [
        {
            "public_body_id": r["public_body_id"],
            "document_url": r["file_url"],
            "source_page_url": r["disclosure_page_url"],
            "file_type": r["file_type"],
            "date_added": None,
        }
        for r in data["results"]
    ]
    public_dir = Path(repo_root) / "public"
    public_dir.mkdir(parents=True, exist_ok=True)
    output_path = public_dir / "disclosure-files.json"
    write_json(output_path, records)
    return output_path


def write_foi_disclosures_output(steps_dir, repo_root):
    input_path = Path(steps_dir) / "extract_disclosures_deduplicate" / "output.json"
    if not input_path.exists():
        return None
    data = read_json(input_path)
    public_dir = Path(repo_root) / "public"
    public_dir.mkdir(parents=True, exist_ok=True)
    output_path = public_dir / "foi-disclosures.json"
    write_json(output_path, data["results"])
    return output_path


def merge(steps_dir, pipeline_steps, target_public_body=None, coverage=None):
    base_data = read_json(steps_dir / "find_public_bodies_subject_to_foi" / "output.json")
    base_data = filter_by_public_body(base_data, target_public_body)
    bodies = copy.deepcopy(base_data["public_bodies"])
    body_map = {b["public_body_id"]: b for b in bodies}
    for body in body_map.values():
        body["public_body_name"] = body.pop("name")
        body["public_body_url"] = body.pop("official_website_url")
        body["public_body_category"] = body.pop("category")
        body.pop("short_name", None)

    orphans_by_step = {}
    for step_name in pipeline_steps:
        if step_name in ("find_public_bodies", STEP_NAME):
            continue
        merger = STEP_MERGERS.get(step_name)
        if merger is None:
            continue
        output_path = steps_dir / step_name / "output.json"
        if not output_path.exists():
            continue
        step_data = filter_by_public_body(read_json(output_path), target_public_body)
        merger(body_map, step_data)
        if coverage is not None and step_name in PER_BODY_STEPS:
            covered_ids = {
                r["public_body_id"] for r in step_data["results"]
            } & set(body_map)
            coverage[step_name] = {
                "covered": len(covered_ids),
                "missing": sorted(set(body_map) - covered_ids),
            }
        if step_name in DISCLOSURE_STEPS:
            orphans = collect_disclosure_ids(step_data) - set(body_map)
            if orphans:
                orphans_by_step[step_name] = sorted(orphans)

    if orphans_by_step:
        all_ids = sorted({oid for ids in orphans_by_step.values() for oid in ids})
        details = "; ".join(
            f"{step}: {ids}" for step, ids in sorted(orphans_by_step.items())
        )
        raise ValueError(
            f"export_status: {len(all_ids)} disclosure public_body_id(s) "
            f"not in the canonical body map: {all_ids} (from steps: {details})"
        )

    return list(body_map.values())


def format_coverage_summary(coverage, canonical_count):
    lines = [f"Coverage report (canonical bodies: {canonical_count}):"]
    for step_name in sorted(coverage):
        info = coverage[step_name]
        covered = info["covered"]
        missing = info["missing"]
        line = f"  {step_name}: {covered}/{canonical_count} covered"
        if missing:
            line += f" — MISSING {len(missing)}: {missing}"
        lines.append(line)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Export merged pipeline status for all public bodies")
    add_common_args(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)

    if not args.force and output_path.exists() and args.public_body is None:
        print(f"Output exists at {output_path}, skipping (use --force to re-run)")
        sys.exit(0)

    steps_dir = step_dir.parent
    pipeline_dir = steps_dir.parent
    pipelines_dir = pipeline_dir.parent
    pipeline_config = read_json(pipeline_dir / "pipeline.json")

    coverage = {}
    bodies = merge(steps_dir, pipeline_config["steps"], target_public_body=args.public_body, coverage=coverage)
    output = {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
        "public_bodies": bodies,
    }
    write_json(output_path, output)
    write_status(step_dir, len(bodies))

    if args.public_body is None:
        coverage_report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "canonical_body_count": len(bodies),
            "steps": coverage,
        }
        write_json(step_dir / "coverage.json", coverage_report)
        print(format_coverage_summary(coverage, len(bodies)))

    repo_root = pipelines_dir.parent
    public_path = write_public_output(output, repo_root)
    disclosure_path = write_disclosure_files_output(steps_dir, repo_root)
    foi_disclosures_path = write_foi_disclosures_output(steps_dir, repo_root)

    print(f"Wrote {len(bodies)} public bodies to {output_path}")
    print(f"Wrote public data to {public_path}")
    if disclosure_path:
        print(f"Wrote disclosure files to {disclosure_path}")
    if foi_disclosures_path:
        print(f"Wrote FOI disclosures to {foi_disclosures_path}")
    if args.public_body is not None:
        print("Note: scoped export is derived/best-effort; run a full pipeline before publishing public/ artifacts.",
              file=sys.stderr)


if __name__ == "__main__":
    main()
