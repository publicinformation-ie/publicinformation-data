import argparse
import csv
import sys
import time
import truststore
import urllib.robotparser
from datetime import date
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

truststore.inject_into_ssl()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; FOI-Page-Finder/1.0)'
}

URL_COLUMN = 'public_body_url'
RATE_LIMIT_DELAY = 0.2  # seconds between requests


def _request(method, url, **kwargs):
    # SSL fallback for sites with broken certificate chains
    try:
        return requests.request(method, url, headers=HEADERS, **kwargs)
    except requests.exceptions.SSLError:
        print(f"SSL verification failed for {url}, retrying without verification", file=sys.stderr)
        return requests.request(method, url, headers=HEADERS, verify=False, **kwargs)


_robots_cache: dict = {}


def is_allowed_by_robots(base_url, user_agent):
    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        return True
    cache_key = f"{parsed.scheme}://{parsed.netloc}"
    if cache_key in _robots_cache:
        return _robots_cache[cache_key]
    try:
        response = _request('GET', f"{cache_key}/robots.txt", timeout=10)
        if response.status_code == 404:
            _robots_cache[cache_key] = True
            return True
        response.raise_for_status()
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(response.text.splitlines())
        result = rp.can_fetch(user_agent, base_url)
    except requests.RequestException as e:
        print(f"Warning: Could not fetch robots.txt for {base_url}: {e}", file=sys.stderr)
        result = True
    except Exception as e:
        print(f"Warning: Error parsing robots.txt for {base_url}: {e}", file=sys.stderr)
        result = True
    _robots_cache[cache_key] = result
    return result


def find_foi_page(url, ignore_robots=False):
    if not ignore_robots and not is_allowed_by_robots(url, HEADERS['User-Agent']):
        print(f"Skipping {url}: disallowed by robots.txt", file=sys.stderr)
        return None
    
    try:
        response = _request('GET', url, timeout=10)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')

        for link in soup.find_all('a'):
            if 'foi' in link.text.lower() or 'freedom of information' in link.text.lower():
                href = link.get('href')
                if href and not href.lower().startswith('mailto:'):
                    return urljoin(url, href)
    except Exception as e:
        print(f"Error processing {url}: {e}", file=sys.stderr)
    return None


def is_url_reachable(url):
    for method in ('HEAD', 'GET'):
        try:
            response = _request(
                method, url, timeout=15,
                allow_redirects=True, stream=True
            )
            if 200 <= response.status_code < 400:
                return True
        except requests.RequestException:
            continue
    print(f"Unreachable: {url}", file=sys.stderr)
    return False


def load_existing_output(output_file):
    try:
        with open(output_file, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            return {
                row['public_body_id']
                for row in reader
                if row.get('last_checked_date') and row.get('foi_page_url')
            }
    except FileNotFoundError:
        return set()


def process_csv(input_file, output_file, force_check=False, ignore_robots=False):
    already_done = set() if force_check else load_existing_output(output_file)
    if already_done:
        print(f"Resuming: skipping {len(already_done)} already-processed rows.", file=sys.stderr)

    with open(input_file, 'r', encoding='utf-8', newline='') as infile:
        reader = csv.DictReader(infile)

        if URL_COLUMN not in (reader.fieldnames or []):
            raise SystemExit(
                f"Input CSV missing '{URL_COLUMN}' column; found: {reader.fieldnames}"
            )

        output_fieldnames = ['public_body_id', 'public_body_name', 'foi_page_url', 'last_checked_date', 'is_reachable']
        today = date.today().isoformat()

        write_mode = 'a' if (not force_check and already_done) else 'w'
        with open(output_file, write_mode, encoding='utf-8', newline='') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=output_fieldnames)
            if write_mode == 'w':
                writer.writeheader()

            for row in reader:
                if row.get('public_body_id') in already_done:
                    continue

                url = row.get(URL_COLUMN)
                foi_url = find_foi_page(url, ignore_robots=ignore_robots) if url else None
                reachable = is_url_reachable(foi_url) if foi_url else False

                writer.writerow({
                    'public_body_id': row.get('public_body_id', ''),
                    'public_body_name': row.get('public_body_name', ''),
                    'foi_page_url': foi_url or '',
                    'last_checked_date': today,
                    'is_reachable': 'true' if reachable else 'false',
                })
                outfile.flush()

                if url:
                    time.sleep(RATE_LIMIT_DELAY)


def main():
    parser = argparse.ArgumentParser(
        description="Find FOI disclosure pages for public bodies and check reachability."
    )
    parser.add_argument('--input-file', required=True, help='Path to input CSV with a public_body_url column')
    parser.add_argument('--output-file', required=True, help='Path to write the augmented CSV')
    parser.add_argument('--force-check', action='store_true',
                        help='Ignore any existing output and recheck all rows from scratch')
    parser.add_argument('--ignore-robots', action='store_true',
                        help='Skip robots.txt checks and scrape all URLs regardless')
    args = parser.parse_args()
    process_csv(args.input_file, args.output_file, force_check=args.force_check,
                ignore_robots=args.ignore_robots)


if __name__ == '__main__':
    main()
