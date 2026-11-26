#!/usr/bin/env python3
"""Extract decisions and COFOG/subdomain topics with one paid model call per meeting.

This is a PAID step (``paid_steps: {"extract_spc_items": ["llm"]}``). Run a
bounded deterministic window with ``--to render_spc_minutes``; reaching this
step needs the user's explicit permission.

Results are cached by source sha256, model and prompt version, so a re-run
with unchanged inputs makes no model call. A schema failure withholds that
meeting's decisions and topics; per-item violations withhold the affected
item's topics or decision. Neither stops the pipeline.
"""
import argparse
import sys
from pathlib import Path

from lib.cli_utils import add_common_args
from lib.file_utils import append_errors, read_json, write_json, write_status

from steps.extract_spc_items.extraction import (
    PROMPT_VERSION,
    STEP_NAME,
    load_overrides,
    load_taxonomy,
    run,
    spc_model,
)
from steps.resolve_attendees.resolving import load_register

PIPELINE_DIR = Path(__file__).resolve().parents[2]
CACHE_DIR = PIPELINE_DIR / "cache"
REGISTER_PATH = PIPELINE_DIR / "reference" / "people.json"
OVERRIDE_PATH = Path(__file__).parent / "override.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(step_dir / "errors.json", [])

    input_data = read_json(args.input)
    cofog, subdomains = load_taxonomy(PIPELINE_DIR)
    register = load_register(REGISTER_PATH)
    overrides = load_overrides(OVERRIDE_PATH)

    results, errors = run(input_data, CACHE_DIR, register, cofog, subdomains,
                          overrides=overrides)
    append_errors(step_dir, errors)

    write_json(output_path, {"metadata": {"step": STEP_NAME}, "results": results})
    write_status(step_dir, len(results))

    failed = [r["meeting_id"] for r in results if r["extraction_failed"]]
    decisions = sum(len(r["decisions"]) for r in results)
    print(f"Extracted {len(results)} meeting(s): {decisions} decision(s), "
          f"{len(errors)} error(s); model={spc_model()} prompt={PROMPT_VERSION}")
    for meeting_id in failed:
        print(f"Extraction failed (decisions and topics withheld): {meeting_id}",
              file=sys.stderr)
    # Withheld parts are visible in errors.json and the export report; the
    # meeting's minutes still publish. Only missing inputs are fatal.


if __name__ == "__main__":
    main()
