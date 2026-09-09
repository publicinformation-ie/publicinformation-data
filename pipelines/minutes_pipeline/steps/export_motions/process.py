#!/usr/bin/env python3
import argparse
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import read_json, write_json, write_status

STEP_NAME = "export_motions"


def group_by_authority(motions):
    grouped = defaultdict(list)
    for m in motions:
        grouped[m["public_body_slug"]].append(m)
    return dict(grouped)


def write_per_authority(grouped, out_dir):
    """Write one public/motions/<slug>.json per authority."""
    written = {}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for slug, motions in sorted(grouped.items()):
        authority = motions[0]
        payload = {
            "public_body_slug": slug,
            "public_body_name": authority["public_body_name"],
            "public_body_id": authority["public_body_id"],
            "motions": motions,
        }
        write_json(out_dir / f"{slug}.json", payload)
        written[slug] = payload
    return written


def build_index(grouped):
    return {"authorities": sorted(grouped.keys())}


def main():
    parser = argparse.ArgumentParser(
        description="Export canonical motions grouped by authority under public/motions/"
    )
    add_common_args(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)

    try:
        input_data = read_json(args.input)
    except Exception as e:
        print(f"Fatal: could not read input: {e}", file=sys.stderr)
        sys.exit(1)
    input_data = filter_by_public_body(input_data, args.public_body)

    motions = input_data.get("results", [])
    grouped = group_by_authority(motions)

    write_json(output_path, {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "total_motions": len(motions),
            "authorities": sorted(grouped.keys()),
        },
        "results": motions,
    })
    write_status(step_dir, len(motions))

    # Write public output (reviewed before scripts/publish_pages.sh).
    repo_root = step_dir.parent.parent.parent.parent
    public_motions = repo_root / "public" / "motions"
    written = write_per_authority(grouped, public_motions)
    write_json(public_motions / "index.json", build_index(grouped))

    print(f"Wrote {len(motions)} motions across {len(written)} authorities to "
          f"{public_motions}")
    print("Note: review public/motions/ before running scripts/publish_pages.sh",
          file=sys.stderr)


if __name__ == "__main__":
    main()
