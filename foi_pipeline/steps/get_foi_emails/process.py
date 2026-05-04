#!/usr/bin/env python3
import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

from scripts.file_utils import append_error, read_json, write_json, write_status
from scripts.http_utils import fetch

STEP_NAME = "get_foi_emails"
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
FOI_EMAIL_KEYWORDS = ["foi", "freedom"]


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


def process(input_data, step_dir):
    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])

    reachable = [r for r in input_data["results"] if r["is_reachable"]]
    results = []

    for item in reachable:
        url = item["foi_page_url"]
        name = item.get("name", "")
        try:
            response = fetch("GET", url, allow_redirects=True)
            emails = extract_emails(response.text)
            foi_email, email_status = pick_foi_email(emails)
            results.append({
                "public_body_id": item["public_body_id"],
                "name": name,
                "foi_page_url": url,
                "foi_email": foi_email,
                "email_status": email_status,
            })
        except Exception as e:
            append_error(step_dir, {
                "step": STEP_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": type(e).__name__,
                "error_message": str(e),
                "context": {"url": url, "public_body_id": item["public_body_id"], "name": name},
            })

    return results


def main():
    parser = argparse.ArgumentParser(description="Extract FOI contact email addresses")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)

    if not args.force and output_path.exists():
        print(f"Output exists at {output_path}, skipping (use --force to re-run)")
        sys.exit(0)

    try:
        input_data = read_json(args.input)
    except Exception as e:
        print(f"Fatal: could not read input: {e}", file=sys.stderr)
        sys.exit(1)

    results = process(input_data, step_dir)
    output = {
        "metadata": {"step": STEP_NAME, "completed_at": datetime.now(timezone.utc).isoformat()},
        "results": results,
    }
    write_json(output_path, output)
    write_status(step_dir, len(results))
    print(f"Wrote {len(results)} records to {output_path}")


if __name__ == "__main__":
    main()
