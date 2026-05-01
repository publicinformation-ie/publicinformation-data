import argparse
import csv
import os
import re
import sys
import time
import urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import date
from urllib.parse import urlparse

import requests

from common.http import _request, HEADERS, RATE_LIMIT_DELAY

URL_COLUMN = 'public_body_url'
FOI_KEYWORDS = ('foi', 'freedom-of-information', 'freedom_of_information')
FOI_TEXT_KEYWORDS = FOI_KEYWORDS + ('freedom of information',)
MAX_CHILD_SITEMAPS = 10


_robots_cache: dict = {}
_redirect_cache: dict = {}


def _get_final_url(url, timeout=15):
    """Follow redirects; return final URL, or original on error."""
    if url in _redirect_cache:
        return _redirect_cache[url]
    try:
        response = _request('HEAD', url, timeout=timeout, allow_redirects=True)
        if response.status_code == 405:  # HEAD not allowed
            response = _request('GET', url, timeout=timeout, allow_redirects=True, stream=True)
        result = response.url if response.url != url else url
    except requests.RequestException:
        result = url
    _redirect_cache[url] = result
    return result


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
        if response.status_code == 404:
            # No robots.txt means no restrictions
            rp.allow_all = True
        elif response.ok:
            text = response.text
            rp.parse(text.splitlines())
            for line in text.splitlines():
                m = re.match(r'^Sitemap:\s*(\S+)', line, re.IGNORECASE)
                if m:
                    sitemaps.append(m.group(1))
        else:
            response.raise_for_status()
    except requests.RequestException as e:
        print(f"Warning: Could not fetch robots.txt for {origin}: {e}", file=sys.stderr)
    except Exception as e:
        print(f"Warning: Error parsing robots.txt for {origin}: {e}", file=sys.stderr)

    _robots_cache[origin] = (rp, sitemaps)
    return rp, sitemaps


def is_allowed_by_robots(url, user_agent):
    rp, _ = _get_robots_data(url)
    return rp.can_fetch(user_agent, url)


def _parse_sitemap_xml(content):
    """
    Parse sitemap XML content (bytes or str).
    Returns (is_index, urls):
      is_index=True  → child sitemap URLs from <sitemapindex>
      is_index=False → <loc> URLs from <urlset>
    Returns (False, []) if content is not valid XML.
    """
    try:
        root = ET.fromstring(content)
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
    """Fetch url and return raw bytes if response looks like XML, else None.

    Returns bytes so ET.fromstring can read the encoding declaration and
    handle BOMs correctly — avoiding mis-decoding when servers send UTF-8
    content with a Content-Type that implies ISO-8859-1.
    """
    try:
        response = _request('GET', url, timeout=15)
        if response.status_code != 200:
            return None
        content = response.content
        if 'xml' in response.headers.get('content-type', '') or content.lstrip().startswith(b'<'):
            return content
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
        content = _fetch_xml(sitemap_url)
        if not content:
            continue

        is_index, urls = _parse_sitemap_xml(content)
        if is_index:
            for child_url in urls[:MAX_CHILD_SITEMAPS]:
                time.sleep(RATE_LIMIT_DELAY)
                child_content = _fetch_xml(child_url)
                if child_content:
                    _, child_locs = _parse_sitemap_xml(child_content)
                    all_locs.extend(child_locs)
        else:
            all_locs.extend(urls)

    return all_locs


SERPER_ENDPOINT = 'https://google.serper.dev/search'
_NON_HTML_EXTENSIONS = ('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.csv')


def _strip_www(netloc):
    return netloc[4:] if netloc.startswith('www.') else netloc


def search_serper_for_foi_page(url, api_key, name=""):
    """Search Serper.dev for the FOI page within url's domain. Returns URL or None."""
    if not api_key:
        return None

    parsed = urlparse(url)
    domain = parsed.netloc
    prefix = f"[{name}] " if name else ""

    try:
        response = requests.post(
            SERPER_ENDPOINT,
            headers={'X-API-KEY': api_key, 'Content-Type': 'application/json'},
            json={'q': f'site:{domain} freedom of information'},
            timeout=15,
        )
        if response.status_code != 200:
            print(f"{prefix}Serper returned {response.status_code} for {domain}", file=sys.stderr)
            return None

        results = response.json().get('organic', [])
        matches = [
            r['link'] for r in results
            if 'link' in r
            and _strip_www(urlparse(r['link']).netloc) == _strip_www(domain)
            and not r['link'].lower().endswith(_NON_HTML_EXTENSIONS)
            and any(
                kw in r['link'].lower() or kw in r.get('title', '').lower()
                for kw in FOI_TEXT_KEYWORDS
            )
        ]
        if not matches:
            return None

        return min(matches, key=lambda u: len(urlparse(u).path))

    except requests.RequestException as e:
        print(f"{prefix}Serper request failed for {domain}: {e}", file=sys.stderr)
        return None


def find_foi_page(url, ignore_robots=False, serper_api_key=None, name=""):
    prefix = f"[{name}] " if name else ""
    
    # Check if the URL redirects to a different domain
    final_url = _get_final_url(url)
    final_parsed = urlparse(final_url)
    original_parsed = urlparse(url)
    
    # Check if we redirected to a different domain (not just path change)
    is_cross_domain_redirect = (
        final_parsed.netloc != original_parsed.netloc
    )
    
    # Check robots.txt for both original and final URLs if they differ
    if not ignore_robots:
        if is_cross_domain_redirect:
            # Check robots.txt for the final URL's domain
            if not is_allowed_by_robots(final_url, HEADERS['User-Agent']):
                print(f"{prefix}Skipping {url} (redirected to {final_url}): disallowed by robots.txt", file=sys.stderr)
                return None
        elif not is_allowed_by_robots(url, HEADERS['User-Agent']):
            print(f"{prefix}Skipping {url}: disallowed by robots.txt", file=sys.stderr)
            return None

    # Collect sitemap locations from both URLs if there was a cross-domain redirect
    all_locs = []
    if is_cross_domain_redirect:
        print(f"{prefix}{url} redirects to {final_url}, checking both domains", file=sys.stderr)
        try:
            locs = _collect_sitemap_locs(url)
            all_locs.extend(locs)
        except Exception as e:
            print(f"{prefix}Error collecting sitemap URLs for {url}: {e}", file=sys.stderr)

        # Restrict to the entity's path prefix so we don't match FOI pages
        # belonging to other entities on the same shared domain.
        try:
            final_locs = _collect_sitemap_locs(final_url)
            path_prefix = final_parsed.path.rstrip('/')
            if path_prefix:
                final_locs = [
                    loc for loc in final_locs
                    if urlparse(loc).path.startswith(path_prefix)
                ]
            all_locs.extend(final_locs)
        except Exception as e:
            print(f"{prefix}Error collecting sitemap URLs for {final_url}: {e}", file=sys.stderr)
    else:
        try:
            all_locs.extend(_collect_sitemap_locs(url))
        except Exception as e:
            print(f"{prefix}Error collecting sitemap URLs for {url}: {e}", file=sys.stderr)

    matches = [loc for loc in all_locs if any(kw in loc.lower() for kw in FOI_KEYWORDS)]
    if matches:
        return min(matches, key=lambda u: len(urlparse(u).path))

    if serper_api_key:
        # Use the final URL for Serper search if we redirected
        search_url = final_url if is_cross_domain_redirect else url
        print(f"{prefix}Sitemap found nothing for {url}, trying Serper fallback", file=sys.stderr)
        return search_serper_for_foi_page(search_url, api_key=serper_api_key, name=name)

    return None


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


def process_csv(input_file, output_file, force_check=False, missing_only=False, ignore_robots=False, serper_api_key=None):
    checked_today, all_existing = load_existing_output(output_file)

    if force_check:
        already_found = set()
    elif missing_only:
        # Skip rows that already have a URL; reprocess rows with empty foi_page_url
        already_found = {pid for pid, row in all_existing.items() if row.get('foi_page_url')}
    else:
        already_found = checked_today

    if already_found:
        mode_label = "already found" if missing_only else "already processed today"
        print(f"Skipping {len(already_found)} rows ({mode_label}).", file=sys.stderr)

    # missing_only and force_check both need a full rewrite so skipped rows are
    # copied through from all_existing rather than left out of the file.
    write_mode = 'a' if (not force_check and not missing_only and already_found) else 'w'

    with open(input_file, 'r', encoding='utf-8', newline='') as infile:
        reader = csv.DictReader(infile)
        if URL_COLUMN not in (reader.fieldnames or []):
            raise SystemExit(f"Input CSV missing '{URL_COLUMN}' column; found: {reader.fieldnames}")

        today = date.today().isoformat()
        with open(output_file, write_mode, encoding='utf-8', newline='') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=OUTPUT_FIELDS)
            if write_mode == 'w':
                writer.writeheader()

            for row in reader:
                pb_id = row.get('public_body_id', '')
                if pb_id in already_found:
                    if write_mode == 'w':
                        writer.writerow(all_existing[pb_id])
                    continue

                url = row.get(URL_COLUMN)
                pb_name = row.get('public_body_name', '')
                foi_url = find_foi_page(url, ignore_robots=ignore_robots, serper_api_key=serper_api_key, name=pb_name) if url else None
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
    parser.add_argument('--missing-only', action='store_true',
                        help='Reprocess only rows with no FOI page found yet; skip rows already found')
    parser.add_argument('--ignore-robots', action='store_true',
                        help='Skip robots.txt disallow checks (Sitemap: directives still read)')
    args = parser.parse_args()
    serper_api_key = os.environ.get('SERPER_API_KEY')
    if not serper_api_key:
        print("SERPER_API_KEY not set; Serper fallback disabled", file=sys.stderr)
    process_csv(args.input_file, args.output_file,
                force_check=args.force_check,
                missing_only=args.missing_only,
                ignore_robots=args.ignore_robots,
                serper_api_key=serper_api_key)


if __name__ == '__main__':
    main()
