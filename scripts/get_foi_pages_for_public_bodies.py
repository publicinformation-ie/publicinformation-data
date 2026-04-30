import argparse
import csv
import re
import sys
import time
import truststore
import urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import date
from urllib.parse import urlparse

import requests

truststore.inject_into_ssl()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; FOI-Page-Finder/1.0)'
}

URL_COLUMN = 'public_body_url'
RATE_LIMIT_DELAY = 0.2  # seconds between requests
FOI_KEYWORDS = ('foi', 'freedom-of-information', 'freedom_of_information')
MAX_CHILD_SITEMAPS = 10


def _request(method, url, **kwargs):
    # SSL fallback for sites with broken certificate chains
    try:
        return requests.request(method, url, headers=HEADERS, **kwargs)
    except requests.exceptions.SSLError:
        print(f"SSL verification failed for {url}, retrying without verification", file=sys.stderr)
        return requests.request(method, url, headers=HEADERS, verify=False, **kwargs)


_robots_cache: dict = {}


def _get_robots_data(base_url):
    """Return (RobotFileParser, sitemap_urls) for the origin of base_url, cached per origin."""
    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        return urllib.robotparser.RobotFileParser(), []
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin in _robots_cache:
        return _robots_cache[origin]

    rp = urllib.robotparser.RobotFileParser()
    sitemaps = []
    try:
        response = _request('GET', f"{origin}/robots.txt", timeout=10)
        if response.status_code != 404:
            response.raise_for_status()
            text = response.text
            rp.parse(text.splitlines())
            for line in text.splitlines():
                m = re.match(r'^Sitemap:\s*(\S+)', line, re.IGNORECASE)
                if m:
                    sitemaps.append(m.group(1))
    except requests.RequestException as e:
        print(f"Warning: Could not fetch robots.txt for {origin}: {e}", file=sys.stderr)
    except Exception as e:
        print(f"Warning: Error parsing robots.txt for {origin}: {e}", file=sys.stderr)

    _robots_cache[origin] = (rp, sitemaps)
    return rp, sitemaps


def is_allowed_by_robots(url, user_agent):
    rp, _ = _get_robots_data(url)
    return rp.can_fetch(user_agent, url)


def _parse_sitemap_xml(text):
    """
    Parse sitemap XML text.
    Returns (is_index, urls):
      is_index=True  → child sitemap URLs from <sitemapindex>
      is_index=False → <loc> URLs from <urlset>
    Returns (False, []) if text is not valid XML.
    """
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return False, []

    tag = root.tag
    ns = (tag.split('}')[0] + '}') if '}' in tag else ''
    local = tag.replace(ns, '')

    if local == 'sitemapindex':
        return True, [
            loc.text.strip()
            for child in root.findall(f'{ns}sitemap')
            for loc in [child.find(f'{ns}loc')]
            if loc is not None and loc.text
        ]
    if local == 'urlset':
        return False, [
            loc.text.strip()
            for child in root.findall(f'{ns}url')
            for loc in [child.find(f'{ns}loc')]
            if loc is not None and loc.text
        ]
    return False, []


def _fetch_xml(url):
    """Fetch url and return text if response looks like XML, else None."""
    try:
        response = _request('GET', url, timeout=15)
        if response.status_code != 200:
            return None
        text = response.text
        if 'xml' in response.headers.get('content-type', '') or text.lstrip().startswith('<'):
            return text
    except requests.RequestException:
        pass
    return None


def _collect_sitemap_locs(base_url):
    """
    Collect all <loc> URLs from sitemaps for base_url's origin.
    Reads robots.txt for Sitemap: directives; falls back to /sitemap.xml
    then /sitemap_index.xml. Recurses one level into sitemapindex entries.
    """
    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    _, robots_sitemaps = _get_robots_data(base_url)
    candidates = robots_sitemaps or [f"{origin}/sitemap.xml", f"{origin}/sitemap_index.xml"]

    all_locs = []
    for sitemap_url in candidates:
        time.sleep(RATE_LIMIT_DELAY)
        text = _fetch_xml(sitemap_url)
        if not text:
            continue

        is_index, urls = _parse_sitemap_xml(text)
        if is_index:
            for child_url in urls[:MAX_CHILD_SITEMAPS]:
                time.sleep(RATE_LIMIT_DELAY)
                child_text = _fetch_xml(child_url)
                if child_text:
                    _, child_locs = _parse_sitemap_xml(child_text)
                    all_locs.extend(child_locs)
        else:
            all_locs.extend(urls)

    return all_locs


def find_foi_page(url, ignore_robots=False):
    if not ignore_robots and not is_allowed_by_robots(url, HEADERS['User-Agent']):
        print(f"Skipping {url}: disallowed by robots.txt", file=sys.stderr)
        return None

    try:
        locs = _collect_sitemap_locs(url)
    except Exception as e:
        print(f"Error collecting sitemap URLs for {url}: {e}", file=sys.stderr)
        return None

    matches = [loc for loc in locs if any(kw in loc.lower() for kw in FOI_KEYWORDS)]
    if not matches:
        return None

    return min(matches, key=lambda u: len(urlparse(u).path))


def is_url_reachable(url):
    for method in ('HEAD', 'GET'):
        try:
            response = _request(method, url, timeout=15, allow_redirects=True, stream=True)
            if 200 <= response.status_code < 400:
                return True
        except requests.RequestException:
            continue
    print(f"Unreachable: {url}", file=sys.stderr)
    return False


def load_existing_output(output_file):
    """Return (checked_today_ids, all_rows_by_id) from the output file."""
    today = date.today().isoformat()
    try:
        with open(output_file, 'r', encoding='utf-8', newline='') as f:
            rows = {row['public_body_id']: row for row in csv.DictReader(f)}
        checked_today = {pid for pid, row in rows.items() if row.get('last_checked') == today}
        return checked_today, rows
    except FileNotFoundError:
        return set(), {}


OUTPUT_FIELDS = ['public_body_id', 'public_body_name', 'foi_page_url', 'is_reachable', 'last_checked', 'last_modified']


def process_csv(input_file, output_file, force_check=False, ignore_robots=False):
    checked_today, all_existing = load_existing_output(output_file)
    already_done = set() if force_check else checked_today
    if already_done:
        print(f"Resuming: skipping {len(already_done)} already-processed rows.", file=sys.stderr)

    with open(input_file, 'r', encoding='utf-8', newline='') as infile:
        reader = csv.DictReader(infile)
        if URL_COLUMN not in (reader.fieldnames or []):
            raise SystemExit(f"Input CSV missing '{URL_COLUMN}' column; found: {reader.fieldnames}")

        today = date.today().isoformat()
        write_mode = 'a' if (not force_check and already_done) else 'w'
        with open(output_file, write_mode, encoding='utf-8', newline='') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=OUTPUT_FIELDS)
            if write_mode == 'w':
                writer.writeheader()

            for row in reader:
                pb_id = row.get('public_body_id', '')
                if pb_id in already_done:
                    continue

                url = row.get(URL_COLUMN)
                foi_url = find_foi_page(url, ignore_robots=ignore_robots) if url else None
                reachable = is_url_reachable(foi_url) if foi_url else False

                prev = all_existing.get(pb_id)
                prev_foi_url = prev.get('foi_page_url', '') if prev else ''
                new_foi_url = foi_url or ''
                if new_foi_url != prev_foi_url:
                    last_modified = today
                else:
                    last_modified = (prev.get('last_modified') or today) if prev else today

                writer.writerow({
                    'public_body_id': pb_id,
                    'public_body_name': row.get('public_body_name', ''),
                    'foi_page_url': new_foi_url,
                    'is_reachable': 'true' if reachable else 'false',
                    'last_checked': today,
                    'last_modified': last_modified,
                })
                outfile.flush()

                if url:
                    time.sleep(RATE_LIMIT_DELAY)


def main():
    parser = argparse.ArgumentParser(
        description="Find FOI disclosure pages for public bodies via sitemap discovery."
    )
    parser.add_argument('--input-file', required=True)
    parser.add_argument('--output-file', required=True)
    parser.add_argument('--force-check', action='store_true',
                        help='Reprocess all rows, ignoring previous output')
    parser.add_argument('--ignore-robots', action='store_true',
                        help='Skip robots.txt disallow checks (Sitemap: directives still read)')
    args = parser.parse_args()
    process_csv(args.input_file, args.output_file,
                force_check=args.force_check, ignore_robots=args.ignore_robots)


if __name__ == '__main__':
    main()
