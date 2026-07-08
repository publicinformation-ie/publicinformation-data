#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, unquote

from bs4 import BeautifulSoup

from lib.file_utils import write_json, write_status

STEP_NAME = "parse_wdw_bodies"
HTML_FILENAME = "who-does-what.html"
CAMPAIGN_BODY_CLASS = "campaign-body"


def extract_wdw_slug(wdw_url: str) -> str:
    """URL path segment immediately after /en/ in wdw_url, percent-decoded.

    This is gov.ie's own slug for the body (e.g. "publicjobs"), preserved
    as the wdw_slug alias field — not used to rename our canonical slug.
    """
    segments = [s for s in urlparse(wdw_url).path.split("/") if s]
    idx = segments.index("en")
    return unquote(segments[idx + 1])


def parse_html(html: str) -> list:
    """Parse the WDW campaign page HTML and return one record per linked body.

    Selects only links inside div.campaign-body, which on the real gov.ie
    page contains exactly the 27 body links (English-language only,
    excluding nav/footer chrome and the "Who Does What" campaign link
    itself — that self-link lives outside this container).
    """
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find("div", class_=CAMPAIGN_BODY_CLASS)
    if container is None:
        print(f"Fatal: no div.{CAMPAIGN_BODY_CLASS} found in {HTML_FILENAME} "
              f"— page structure may have changed", file=sys.stderr)
        sys.exit(1)

    records = []
    for link in container.find_all("a", href=True):
        name = link.get_text(strip=True)
        url = link["href"]
        if not name or not url:
            continue
        records.append({
            "wdw_name": name,
            "wdw_url": url,
            "wdw_slug": extract_wdw_slug(url),
        })
    return records


def main():
    parser = argparse.ArgumentParser(
        description="Parse the committed Who Does What campaign HTML into one record per linked body"
    )
    parser.add_argument("--input", required=True,
                        help="Previous step output (unused — first step in pipeline)")
    parser.add_argument("--output", default=None, help="Path to write output.json")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output")
    parser.add_argument("--verbose", action="store_true", help="Print progress")
    parser.add_argument("--data-dir", default=None,
                        help="Directory containing who-does-what.html "
                             "(defaults to <pipeline_dir>/data/)")
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    pipeline_dir = step_dir.parent.parent  # pipelines/wdw_pipeline/
    output_path = Path(args.output) if args.output else step_dir / "output.json"
    data_dir = Path(args.data_dir) if args.data_dir else pipeline_dir / "data"
    html_path = data_dir / HTML_FILENAME

    if not args.force and output_path.exists():
        print(f"Output exists at {output_path}, skipping (use --force to re-run)")
        return

    if not html_path.exists():
        print(f"Fatal: source HTML not found at {html_path}\n"
              f"Place {HTML_FILENAME} in {data_dir}/", file=sys.stderr)
        sys.exit(1)

    html = html_path.read_text(encoding="utf-8")
    records = parse_html(html)

    if not records:
        print("Fatal: parsed 0 records — page structure may have changed", file=sys.stderr)
        sys.exit(1)

    output = {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
        "wdw_bodies": records,
    }
    write_json(output_path, output)
    write_status(step_dir, len(records))
    print(f"Wrote {len(records)} WDW body records to {output_path}")


if __name__ == "__main__":
    main()
