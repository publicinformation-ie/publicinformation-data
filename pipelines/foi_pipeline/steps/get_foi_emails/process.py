#!/usr/bin/env python3
import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import append_error, read_json, write_json, write_status, IncrementalWriter
from lib.http_utils import fetch

STEP_NAME = "get_foi_emails"
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
FOI_EMAIL_KEYWORDS = ["foi", "freedom"]
# Non-HTML content types a foi_page_url can resolve to (e.g. a link straight to a
# disclosure-log PDF instead of a contact page). BeautifulSoup/html.parser can
# throw confusing low-level errors (e.g. ValueError from mis-decoded binary bytes)
# if handed one of these, so they're skipped before parsing.
_BINARY_CONTENT_TYPES = ("application/pdf", "application/octet-stream", "image/")


def extract_emails(html):
    soup = BeautifulSoup(html, "html.parser")
    emails = set()
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if href.startswith("mailto:"):
            addr = href[7:].split("?")[0].strip().lower()
            if addr:
                emails.add(addr)
    for match in EMAIL_PATTERN.finditer(soup.get_text()):
        emails.add(match.group().lower())
    return list(emails)


def pick_foi_email(emails):
    if not emails:
        return None, "not_found"
    if len(emails) == 1:
        email = emails[0]
        if EMAIL_PATTERN.fullmatch(email):
            return email, "found"
        return email, "invalid"
    for email in emails:
        if any(kw in email for kw in FOI_EMAIL_KEYWORDS):
            return email, "found"
    return None, "multiple_found"


def process(input_data, step_dir, writer, verbose=False):
    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])

    reachable = [r for r in input_data["results"] if r["is_reachable"]]

    for item in reachable:
        body_id = item["public_body_id"]
        if writer.is_processed(body_id):
            continue
        url = item["foi_page_url"]
        name = item.get("name", "")
        try:
            response = fetch("GET", url, allow_redirects=True)
            content_type = response.headers.get("Content-Type", "").lower()
            if any(ct in content_type for ct in _BINARY_CONTENT_TYPES):
                writer.append([{
                    "public_body_id": body_id,
                    "name": name,
                    "foi_page_url": url,
                    "foi_email": None,
                    "email_status": "not_found",
                }])
                if verbose:
                    print(".", end="", flush=True)
                continue
            emails = extract_emails(response.text)
            foi_email, email_status = pick_foi_email(emails)
            writer.append([{
                "public_body_id": body_id,
                "name": name,
                "foi_page_url": url,
                "foi_email": foi_email,
                "email_status": email_status,
            }])
        except Exception as e:
            append_error(step_dir, {
                "step": STEP_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": type(e).__name__,
                "error_message": str(e),
                "context": {"url": url, "public_body_id": body_id, "name": name},
            })
            writer.append([])
        if verbose:
            print(".", end="", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Extract FOI contact email addresses")
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
