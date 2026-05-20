#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from scripts.file_utils import read_json, write_json, write_status

STEP_NAME = "generate_topics"


def sort_disclosures(disclosures):
    return sorted(
        disclosures,
        key=lambda d: (d.get("decision_date") is not None, d.get("decision_date") or ""),
        reverse=True,
    )


def process_topics(topics_config, disclosures):
    results = []
    for topic in topics_config:
        keywords = [kw.lower() for kw in topic["keywords"]]
        matched = [
            d for d in disclosures
            if any(kw in (d.get("request_description") or "").lower() for kw in keywords)
        ]
        sorted_matched = sort_disclosures(matched)
        results.append({
            "slug": topic["slug"],
            "label": topic["label"],
            "keywords": topic["keywords"],
            "match_count": len(sorted_matched),
            "disclosures": sorted_matched,
        })
    return results


def write_public_topics(results, repo_root):
    public_dir = repo_root / "public"
    public_dir.mkdir(parents=True, exist_ok=True)
    public_path = public_dir / "topics.json"
    write_json(public_path, results)
    return public_path


def main():
    parser = argparse.ArgumentParser(description="Generate topic-matched FOI disclosure sets")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)

    if not args.force and output_path.exists():
        print(f"Output exists at {output_path}, skipping (use --force to re-run)")
        sys.exit(0)

    steps_dir = step_dir.parent
    pipeline_dir = steps_dir.parent
    repo_root = pipeline_dir.parent

    topics_config_path = step_dir / "topics-config.json"
    topics_config = read_json(topics_config_path)

    canonicalize_path = steps_dir / "extract_disclosures_canonicalize" / "output.json"
    if not canonicalize_path.exists():
        print(f"Fatal: input not found at {canonicalize_path}", file=sys.stderr)
        sys.exit(1)

    input_data = read_json(canonicalize_path)
    disclosures = input_data["results"]

    results = process_topics(topics_config, disclosures)

    write_json(output_path, {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
        "results": results,
    })
    write_status(step_dir, len(results))

    public_path = write_public_topics(results, repo_root)

    print(f"Wrote {len(results)} topics to {output_path}")
    print(f"Wrote public data to {public_path}")


if __name__ == "__main__":
    main()
