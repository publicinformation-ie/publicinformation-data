#!/usr/bin/env python3
"""
Scrape public body contact details from foi.gov.ie/foi_units pages.

Input: Text file with one URL per line (foi_body_urls.txt)
Output: CSV with public_body_name, public_body_contact_email, public_body_contact_name
"""

import csv
import re
import sys
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def fetch_page(url):
    """Fetch a page with retries and proper encoding."""
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        return response.text
    except Exception as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        return None


def extract_details(html, url):
    """Extract Organisation, Name, and Email from the page."""
    if not html:
        return None, None, None
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find the table with the contact details
    # The table has rows like: **Organisation:** | Value
    org_name = None
    contact_name = None
    contact_email = None
    
    # Find all rows in tables
    for table in soup.find_all('table'):
        for row in table.find_all('tr'):
            cells = row.find_all(['th', 'td'])
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True)
                value = cells[1].get_text(strip=True)
                
                if label == '**Organisation:**' or label == 'Organisation:' or 'Organisation' in label:
                    org_name = value
                elif label == '**Name:**' or label == 'Name:' or 'Name:' in label:
                    contact_name = value
                elif label == '**Email:**' or label == 'Email:' or 'Email:' in label:
                    # Extract email from mailto link if present
                    link = cells[1].find('a', href=True)
                    if link:
                        href = link.get('href', '')
                        if href.startswith('mailto:'):
                            contact_email = href[7:]  # Remove mailto: prefix
                        else:
                            contact_email = value
                    else:
                        contact_email = value
    
    return org_name, contact_name, contact_email


def main():
    input_file = 'foi_body_urls.txt'
    output_file = 'public_body_contact_details.csv'
    
    # Read URLs
    with open(input_file, 'r') as f:
        urls = [line.strip() for line in f if line.strip()]
    
    print(f"Processing {len(urls)} URLs...")
    
    # Add trailing slash if not present
    urls = [url if url.endswith('/') else url + '/' for url in urls]
    
    # Write CSV header
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['public_body_name', 'public_body_contact_email', 'public_body_contact_name'])
        
        for i, url in enumerate(urls, 1):
            print(f"Processing {i}/{len(urls)}: {url}")
            
            html = fetch_page(url)
            if not html:
                # Write empty row if fetch failed
                writer.writerow(['', '', ''])
                continue
            
            org_name, contact_name, contact_email = extract_details(html, url)
            
            # Write to CSV
            writer.writerow([
                org_name if org_name else '',
                contact_email if contact_email else '',
                contact_name if contact_name else ''
            ])
            
            csvfile.flush()
            
            # Rate limiting - be polite
            time.sleep(0.5)
    
    print(f"Done! Results saved to {output_file}")


if __name__ == '__main__':
    main()
