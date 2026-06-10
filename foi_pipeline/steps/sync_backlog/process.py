#!/usr/bin/env python3
import argparse
from datetime import datetime, timezone
from pathlib import Path

from lib.cli_utils import add_common_args
from lib.file_utils import write_json, write_status
from steps.sync_backlog.run import (
    collect_issues,
    load_backlog,
    save_backlog,
    reconcile,
)

STEP_NAME = "sync_backlog"
BACKLOG_PATH_RELATIVE = "steps/sync_backlog/backlog.yml"


def main():
    parser = argparse.ArgumentParser(description="Sync eval issues to backlog.yml")
    add_common_args(parser)
    args = parser.parse_args()

    pipeline_dir = Path(__file__).parent.parent.parent
    step_dir = Path(__file__).parent
    output_path = Path(args.output)
    backlog_path = pipeline_dir / BACKLOG_PATH_RELATIVE

    run_at = datetime.now(timezone.utc).isoformat()

    print("Collecting issues from eval outputs...")
    scored_dict, steps_with_eval = collect_issues(pipeline_dir)
    print(f"Found {len(scored_dict)} issues across {len(steps_with_eval)} evaluated steps")

    existing = load_backlog(backlog_path)
    print(f"Loaded {len(existing)} existing backlog entries from {backlog_path}")

    updated_issues, stats = reconcile(scored_dict, existing, steps_with_eval, run_at)
    save_backlog(backlog_path, updated_issues, run_at)
    print(f"Saved {len(updated_issues)} entries to {backlog_path}")

    result = {**stats, "run_at": run_at, "total": len(updated_issues)}
    print(f"Done: created={stats['created']} updated={stats['updated']} resolved={stats['resolved']} unchanged={stats['unchanged']}")

    write_json(output_path, result)
    write_status(step_dir, len(updated_issues))


if __name__ == "__main__":
    main()
