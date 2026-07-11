#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

from lib.cli_utils import add_common_args
from lib.file_utils import read_json, write_json, write_status, IncrementalWriter
from lib.body_matching import normalise, best_match, load_candidates, MATCH_THRESHOLD

STEP_NAME = "match_public_bodies"
CANDIDATES_PATH = "pipelines/cso_pipeline/steps/resolve_website_urls/output.json"


def process(input_data, candidates, writer, verbose=False):
    match_log = []
    for record in input_data.get("datagovie_orgs", []):
        slug = record["datagovie_slug"]
        if writer.is_processed(slug):
            continue
        norm = normalise(record["datagovie_name"])
        matched_id, score = best_match(norm, candidates)
        match_log.append({
            "datagovie_slug": slug,
            "datagovie_name": record["datagovie_name"],
            "normalised": norm,
            "matched_public_body_id": matched_id,
            "match_score": round(score, 4),
        })
        writer.append([{**record, "public_body_id": matched_id}])
        if verbose:
            print(".", end="", flush=True)
    return match_log


def main():
    parser = argparse.ArgumentParser(
        description="Fuzzy-match data.gov.ie organisations against public bodies by name"
    )
    add_common_args(parser)
    parser.add_argument("--candidates", default=None,
                        help="Path to resolve_website_urls output.json "
                             f"(defaults to <repo_root>/{CANDIDATES_PATH})")
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    pipeline_dir = step_dir.parent.parent  # pipelines/datagovie_pipeline/
    repo_root = pipeline_dir.parent.parent
    output_path = Path(args.output)
    candidates_path = Path(args.candidates) if args.candidates else repo_root / CANDIDATES_PATH

    try:
        input_data = read_json(args.input)
    except Exception as e:
        print(f"Fatal: could not read input: {e}", file=sys.stderr)
        sys.exit(1)

    if not candidates_path.exists():
        print(f"Fatal: candidates file not found at {candidates_path}\n"
              f"Run cso_pipeline through resolve_website_urls first.", file=sys.stderr)
        sys.exit(1)
    candidates = load_candidates(candidates_path)

    writer = IncrementalWriter(output_path, STEP_NAME, key_field="datagovie_slug", force=args.force)

    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")

    match_log = process(input_data, candidates, writer, verbose=args.verbose)
    write_json(step_dir / "match_log.json", match_log)

    count = writer.finalize()
    write_status(step_dir, count)
    if args.verbose:
        print()
    print(f"Wrote {count} records to {output_path}")


if __name__ == "__main__":
    main()
