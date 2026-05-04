#!/usr/bin/env python3
import argparse
import copy
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from scripts.file_utils import read_json, write_json, write_status

STEP_NAME = "export_status"


def merge_validate_websites(body_map, step_data):
    present = {r["public_body_id"] for r in step_data["results"]}
    for r in step_data["results"]:
        bid = r["public_body_id"]
        if bid in body_map:
            body_map[bid]["status"]["website_url"]["status"] = (
                "success" if r["is_reachable"] else "failed"
            )
    for bid, body in body_map.items():
        if bid not in present:
            body["status"]["website_url"]["status"] = "failed"


def merge_find_foi_pages(body_map, step_data):
    present = {r["public_body_id"] for r in step_data["results"]}
    for r in step_data["results"]:
        bid = r["public_body_id"]
        if bid in body_map:
            body_map[bid]["status"]["foi_page"]["url"] = r["foi_page_url"]
            body_map[bid]["status"]["foi_page"]["status"] = "success"
    for bid, body in body_map.items():
        if bid not in present:
            body["status"]["foi_page"]["status"] = "failed"


def merge_check_foi_pages(body_map, step_data):
    present = {r["public_body_id"] for r in step_data["results"]}
    for r in step_data["results"]:
        bid = r["public_body_id"]
        if bid in body_map:
            body_map[bid]["status"]["foi_page"]["status"] = (
                "success" if r["is_reachable"] else "failed"
            )
    for bid, body in body_map.items():
        if bid not in present:
            body["status"]["foi_page"]["status"] = "failed"


def merge_get_foi_emails(body_map, step_data):
    present = {r["public_body_id"] for r in step_data["results"]}
    for r in step_data["results"]:
        bid = r["public_body_id"]
        if bid in body_map:
            body_map[bid]["status"]["foi_email"]["email"] = r.get("foi_email")
            body_map[bid]["status"]["foi_email"]["status"] = (
                "success" if r.get("email_status") == "found" else "failed"
            )
    for bid, body in body_map.items():
        if bid not in present:
            body["status"]["foi_email"]["status"] = "failed"


def merge_find_disclosure_pages(body_map, step_data):
    present = {r["public_body_id"] for r in step_data["results"]}
    for r in step_data["results"]:
        bid = r["public_body_id"]
        if bid in body_map:
            body_map[bid]["status"]["disclosures_page"]["url"] = r["disclosure_page_url"]
            body_map[bid]["status"]["disclosures_page"]["status"] = "success"
    for bid, body in body_map.items():
        if bid not in present:
            body["status"]["disclosures_page"]["status"] = "failed"


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


STEP_MERGERS = {
    "validate_websites": merge_validate_websites,
    "find_foi_pages": merge_find_foi_pages,
    "check_foi_pages": merge_check_foi_pages,
    "get_foi_emails": merge_get_foi_emails,
    "find_disclosure_pages": merge_find_disclosure_pages,
    "find_disclosure_files": merge_find_disclosure_files,
}


def merge(steps_dir, pipeline_steps):
    base_data = read_json(steps_dir / "find_public_bodies" / "output.json")
    bodies = copy.deepcopy(base_data["public_bodies"])
    body_map = {b["public_body_id"]: b for b in bodies}

    for step_name in pipeline_steps:
        if step_name in ("find_public_bodies", STEP_NAME):
            continue
        merger = STEP_MERGERS.get(step_name)
        if merger is None:
            continue
        output_path = steps_dir / step_name / "output.json"
        if not output_path.exists():
            continue
        step_data = read_json(output_path)
        merger(body_map, step_data)

    return list(body_map.values())


def main():
    parser = argparse.ArgumentParser(description="Export merged pipeline status for all public bodies")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)

    if not args.force and output_path.exists():
        print(f"Output exists at {output_path}, skipping (use --force to re-run)")
        sys.exit(0)

    steps_dir = step_dir.parent
    pipeline_dir = steps_dir.parent
    pipeline_config = read_json(pipeline_dir / "pipeline.json")

    bodies = merge(steps_dir, pipeline_config["steps"])
    output = {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
        "public_bodies": bodies,
    }
    write_json(output_path, output)
    write_status(step_dir, len(bodies))
    print(f"Wrote {len(bodies)} public bodies to {output_path}")


if __name__ == "__main__":
    main()
