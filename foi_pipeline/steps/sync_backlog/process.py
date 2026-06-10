#!/usr/bin/env python3
import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib.cli_utils import add_common_args
from lib.file_utils import write_json, write_status
from steps.sync_backlog.run import (
    CODEBERG_API,
    CODEBERG_REPO,
    RateLimitedSession,
    collect_issues,
    ensure_labels,
    fetch_open_issues,
    get_rate_limit_summary,
    logger,
    reconcile,
)

STEP_NAME = "sync_backlog"


def main():
    parser = argparse.ArgumentParser(description="Sync eval issues to Codeberg Issues")
    add_common_args(parser)
    args = parser.parse_args()

    pipeline_dir = Path(__file__).parent.parent.parent
    output_path = Path(args.output)

    sync_enabled = os.getenv("CODEBERG_SYNC_ENABLED", "true").lower() != "false"

    if not sync_enabled:
        print("CODEBERG_SYNC_ENABLED=false — skipping sync")
        result = {"created": 0, "updated": 0, "closed": 0, "skipped": 0, "run_at": datetime.now(timezone.utc).isoformat(), "sync_enabled": False}
        write_json(output_path, result)
        write_status(output_path.parent, 0)
        return

    token = os.getenv("CODEBERG_TOKEN")
    if not token:
        print("Error: CODEBERG_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    repo_api_url = f"{CODEBERG_API}/repos/{CODEBERG_REPO}"
    session = RateLimitedSession()
    session.session.headers.update({"Authorization": f"token {token}", "Content-Type": "application/json"})

    run_at = datetime.now(timezone.utc).isoformat()
    print("Collecting issues from eval outputs...")
    scored_dict, steps_with_eval = collect_issues(pipeline_dir)
    print(f"Found {len(scored_dict)} issues across {len(steps_with_eval)} evaluated steps")

    print("Ensuring labels exist on Codeberg...")
    label_ids = ensure_labels(session, repo_api_url, steps_with_eval)

    print("Fetching open Codeberg issues...")
    open_issues = fetch_open_issues(session, repo_api_url)
    print(f"Found {len(open_issues)} open pipeline issues on Codeberg")

    print("Reconciling...")
    result = reconcile(session, repo_api_url, scored_dict, open_issues, steps_with_eval, label_ids, run_at)
    result["sync_enabled"] = True
    
    rate_summary = get_rate_limit_summary()
    logger.info(f"Rate limit summary: {rate_summary}")
    
    print(f"Done: created={result['created']} updated={result['updated']} closed={result['closed']} skipped={result['skipped']}")
    print(f"Total API requests made: {rate_summary['total_requests']}")

    write_json(output_path, result)
    write_status(output_path.parent, result["created"] + result["updated"])


if __name__ == "__main__":
    main()
