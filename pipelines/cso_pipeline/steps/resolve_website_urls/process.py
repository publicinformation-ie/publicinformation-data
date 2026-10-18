#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import append_error, read_json, write_json, write_status, IncrementalWriter
from lib.http_utils import fetch, is_safe_url
from lib.website_probe import STUB_MARKER, resolve_stub_url  # noqa: F401  (re-exported for tests)

STEP_NAME = "resolve_website_urls"


def candidate_urls(body: dict) -> list[str]:
    """URL sources to try, best first, deduplicated.

    Priority: apify > llm (direct+high) > official (gov.ie stub) > llm (related).
    url_type=parent is excluded: it points to a different legal entity, not this body.

    Returns an ordered list rather than a single pick: a candidate that cannot be
    fetched says nothing about the next one, so a failure must fall through to
    the remaining candidates instead of ending the search (see process()).
    """
    candidates = []
    if url := body.get("apify_website_url"):
        candidates.append(url)
    if (url := body.get("llm_website_url")) and body.get("llm_url_type") == "direct" and body.get("llm_confidence") == "high":
        candidates.append(url)
    if url := body.get("official_website_url"):
        candidates.append(url)
    if (url := body.get("llm_website_url")) and body.get("llm_url_type") != "parent":
        candidates.append(url)
    return list(dict.fromkeys(candidates))


def pick_best_url(body: dict) -> str | None:
    """Highest-priority candidate, or None. Kept for callers that only need the
    first choice; process() walks the whole candidate list."""
    candidates = candidate_urls(body)
    return candidates[0] if candidates else None


def process(input_data, step_dir, writer, verbose=False):
    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])

    bodies = input_data.get("public_bodies") or input_data.get("results", [])
    for body in bodies:
        body_id = body["public_body_id"]
        if writer.is_processed(body_id):
            continue
        candidates = candidate_urls(body)
        if not candidates:
            writer.append([body])
            continue
        attempts = []
        for url in candidates:
            try:
                response = fetch("GET", url, allow_redirects=True)
                response.raise_for_status()
                final_url = response.url if is_safe_url(response.url) else url
                resolved_url = resolve_stub_url(response.text, final_url)
            except Exception as e:
                # A failed fetch does NOT prove the URL is wrong: the host may
                # not exist, but it may equally be bot-blocked (403/challenge),
                # which is evidence the site is alive. Try the next candidate
                # instead of nulling a value the source already carried, which
                # is a confirmed-silent data loss. The failure is only escalated
                # to errors.json if no candidate resolves (see below) — logging
                # recovered candidates would make the next run evict and re-fetch
                # the body forever.
                attempts.append({
                    "url": url,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                })
                continue
            writer.append([{**body, "official_website_url": resolved_url}])
            break
        else:
            # No candidate resolved: keep the source value untouched (usually
            # None) and log the body so the next run retries it.
            append_error(step_dir, {
                "step": STEP_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": "NoUsableCandidate",
                "error_message": f"none of {len(attempts)} candidate URL(s) could be fetched",
                "context": {"public_body_id": body_id, "attempts": attempts},
            })
            writer.append([body])
        if verbose:
            print(".", end="", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Resolve gov.ie stub portal URLs to real external websites")
    add_common_args(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)
    override_path = step_dir / "override.json"

    try:
        input_data = read_json(args.input)
    except Exception as e:
        print(f"Fatal: could not read input: {e}", file=sys.stderr)
        sys.exit(1)
    input_data = filter_by_public_body(input_data, args.public_body)
    if args.public_body is not None and not (
        input_data.get("results") or input_data.get("public_bodies")
    ):
        print(f"No input record for public_body_id={args.public_body}", file=sys.stderr)
        sys.exit(0)

    writer = IncrementalWriter(output_path, STEP_NAME, force=args.force,
                               override_path=override_path,
                               target_public_body=args.public_body)

    errors_path = step_dir / "errors.json"
    if errors_path.exists():
        prior_errors = read_json(errors_path)
        failed_ids = {
            e["context"]["public_body_id"]
            for e in prior_errors
            if isinstance(e, dict) and "context" in e and "public_body_id" in e["context"]
        }
        if failed_ids:
            writer._evict_keys(failed_ids)

    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")

    process(input_data, step_dir, writer, verbose=args.verbose)
    count = writer.finalize()
    write_status(step_dir, count)
    if args.verbose:
        print()
    print(f"Wrote {count} records to {output_path}")


if __name__ == "__main__":
    main()
