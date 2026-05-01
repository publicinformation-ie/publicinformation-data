#!/usr/bin/env python3
import sys
import csv
import time
import unicodedata
import re
import argparse
from pathlib import Path
from datetime import date
from bs4 import BeautifulSoup

from common.http import _request, RATE_LIMIT_DELAY, find_foi_email

FOI_GOV_IE_BASE = "https://foi.gov.ie"
FOI_GOV_IE_ALL_BODIES = FOI_GOV_IE_BASE + "/all-foi-bodies"


def normalize_name(name):
    """Normalize a name for comparison.
    
    Note: The foi.gov.ie data sometimes has punctuation without spaces (e.g., "word,word")
    which becomes "wordword" after normalization. To handle this, we first add spaces
    after certain punctuation marks before normalization.
    """
    # First, add spaces after commas and other punctuation that might be adjacent to words
    name = re.sub(r'([,;:])([^\s])', r'\1 \2', name)
    name = name.lower()
    name = ''.join(c for c in unicodedata.normalize('NFKD', name) if unicodedata.category(c) != 'Mn')
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def scrape_foi_gov_ie(rate_limit=RATE_LIMIT_DELAY):
    """Scrape foi.gov.ie for FOI body names and emails.
    
    The website structure has changed - /foi_units/ links are no longer available.
    This function now:
    1. Loads organization names from foi_dot_ie_public_body_names.txt
    2. For each name, tries to find the corresponding page to extract the email
    
    If foi_dot_ie_public_body_names.txt doesn't exist, falls back to the old method.
    """
    from pathlib import Path
    
    result = {}
    
    # Try to load names from foi_dot_ie_public_body_names.txt
    foi_names_path = Path('foi_dot_ie_public_body_names.txt')
    if foi_names_path.exists():
        with open(foi_names_path, 'r', encoding='utf-8') as f:
            next(f, None)  # Skip header
            for line in f:
                line = line.strip()
                if line:
                    normalized_name = normalize_name(line)
                    # Try to find a page for this organization
                    # Create a URL-safe version of the name
                    url_name = line.lower().replace(' ', '_').replace('&', 'and').replace(',', '')
                    test_url = f"{FOI_GOV_IE_BASE}/foi_units/{url_name}"
                    try:
                        time.sleep(rate_limit)
                        resp = _request('GET', test_url)
                        if resp.status_code == 200:
                            page_soup = BeautifulSoup(resp.text, 'html.parser')
                            email = find_foi_email(page_soup)
                            result[normalized_name] = email
                        else:
                            result[normalized_name] = None
                    except Exception:
                        result[normalized_name] = None
    else:
        # Fallback to old method
        resp = _request('GET', FOI_GOV_IE_ALL_BODIES)
        soup = BeautifulSoup(resp.text, 'html.parser')

        seen = set()
        urls = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.startswith('/foi_units/'):
                if href not in seen:
                    seen.add(href)
                    urls.append(FOI_GOV_IE_BASE + href)

        for url in urls:
            time.sleep(rate_limit)
            resp = _request('GET', url)
            page_soup = BeautifulSoup(resp.text, 'html.parser')
            h1 = page_soup.find('h1')
            if not h1:
                continue
            org_name = h1.get_text(strip=True)
            email = find_foi_email(page_soup)
            result[normalize_name(org_name)] = email

    return result


def load_aliases(aliases_file):
    aliases_path = Path(aliases_file)
    if not aliases_path.exists():
        return {}
    with open(aliases_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return {row['public_body_id']: row['foi_gov_ie_name'] for row in reader}


def enrich_rows(rows, scraped, aliases, force_update=False):
    today = date.today().isoformat()
    updated = []
    for row in rows:
        row = dict(row)
        if not force_update and row.get('foi_contact_email'):
            updated.append(row)
            continue

        pub_id = row.get('public_body_id', '')
        pub_name = row.get('public_body_name', '')

        row['last_checked'] = today

        # Try to find a match: first using alias if available, then using public_body_name
        key = None
        if str(pub_id) in aliases:
            alias_key = normalize_name(aliases[str(pub_id)])
            if alias_key in scraped:
                key = alias_key

        if key is None:
            # Try using public_body_name directly
            pub_name_key = normalize_name(pub_name)
            if pub_name_key in scraped:
                key = pub_name_key

        if key is not None:
            new_email = scraped[key] or ''
            if new_email != row.get('foi_contact_email', ''):
                row['last_modified'] = today
            row['foi_contact_email'] = new_email
        else:
            # Neither alias nor public_body_name matched
            alias_name = aliases.get(str(pub_id)) if str(pub_id) in aliases else ''
            print(
                f'No match for public_body_id={pub_id} name="{pub_name}" alias="{alias_name}" — add to public_bodies_aliases.csv',
                file=sys.stderr
            )

        updated.append(row)
    return updated


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-file', required=True)
    parser.add_argument('--output-file', required=True)
    parser.add_argument('--force-update', action='store_true', default=False)
    parser.add_argument('--rate-limit', type=float, default=0.2)
    parser.add_argument('--aliases-file', default='public_bodies_aliases.csv', help='Path to aliases CSV file')
    args = parser.parse_args()

    aliases = load_aliases(Path(args.aliases_file))

    with open(args.input_file, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    if not fieldnames:
        print("ERROR: Input file is empty or has no headers", file=sys.stderr)
        sys.exit(1)

    scraped = scrape_foi_gov_ie(rate_limit=args.rate_limit)

    updated = enrich_rows(rows, scraped, aliases, force_update=args.force_update)

    with open(args.output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated)


if __name__ == '__main__':
    main()
