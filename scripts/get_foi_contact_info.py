#!/usr/bin/env python3
"""
Extract FOI email addresses and disclosure log page URLs from FOI pages.

Input: CSV file with foi_page_url column (output from get_foi_pages_for_public_bodies.py)
Output: CSV with public_body_id,public_body_name,foi_email,foi_disclosure_page_url
"""

import argparse
import csv
import re
import sys
import time
import truststore
from datetime import date
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

truststore.inject_into_ssl()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; FOI-Contact-Info-Extractor/1.0)'
}

FOI_PAGE_URL_COLUMN = 'foi_page_url'
RATE_LIMIT_DELAY = 0.2  # seconds between requests


def _request(method, url, **kwargs):
    """Reusable request method with SSL fallback."""
    try:
        return requests.request(method, url, headers=HEADERS, **kwargs)
    except requests.exceptions.SSLError:
        print(f"SSL verification failed for {url}, retrying without verification", file=sys.stderr)
        return requests.request(method, url, headers=HEADERS, verify=False, **kwargs)


def find_foi_email(url):
    """Extract FOI email address from a page."""
    try:
        response = _request('GET', url, timeout=10)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for mailto links first
        for link in soup.find_all('a', href=True):
            href = link.get('href', '').lower()
            if href.startswith('mailto:'):
                email = href[7:]  # Remove 'mailto:' prefix
                if is_foi_related_email(email):
                    return email
        
        # Look for email patterns in text if no mailto links found
        text = soup.get_text()
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        
        for email in emails:
            if is_foi_related_email(email):
                return email
                
        # If no FOI-specific email found, return first email found
        if emails:
            return emails[0]
            
    except Exception as e:
        print(f"Error extracting email from {url}: {e}", file=sys.stderr)
    return None


def is_foi_related_email(email):
    """Check if email address appears to be FOI-related."""
    email_lower = email.lower()
    foi_keywords = ['foi', 'freedom', 'information', 'request', 'disclosure']
    return any(keyword in email_lower for keyword in foi_keywords)


def find_disclosure_log_page(url):
    """Find disclosure log page URL from a FOI page."""
    try:
        response = _request('GET', url, timeout=10)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')
        
        disclosure_keywords = ['disclosure', 'log', 'register', 'publication scheme']
        
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            link_text = link.get_text().lower()
            
            if href and not href.lower().startswith(('mailto:', 'tel:', 'javascript:')):
                # Check link text and URL for disclosure-related keywords
                href_lower = href.lower()
                if (any(keyword in link_text for keyword in disclosure_keywords) or
                    any(keyword in href_lower for keyword in disclosure_keywords)):
                    return urljoin(url, href)
                    
    except Exception as e:
        print(f"Error finding disclosure log page for {url}: {e}", file=sys.stderr)
    return None


def process_csv(input_file, output_file):
    """Process input CSV and extract FOI contact information."""
    with open(input_file, 'r', encoding='utf-8', newline='') as infile:
        reader = csv.DictReader(infile)
        
        if FOI_PAGE_URL_COLUMN not in (reader.fieldnames or []):
            raise SystemExit(
                f"Input CSV missing '{FOI_PAGE_URL_COLUMN}' column; found: {reader.fieldnames}"
            )
        
        output_fieldnames = ['public_body_id', 'public_body_name', 'foi_email', 'foi_disclosure_page_url']
        
        with open(output_file, 'w', encoding='utf-8', newline='') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=output_fieldnames)
            writer.writeheader()
            
            for row in reader:
                foi_page_url = row.get(FOI_PAGE_URL_COLUMN)
                
                if not foi_page_url:
                    writer.writerow({
                        'public_body_id': row.get('public_body_id', ''),
                        'public_body_name': row.get('public_body_name', ''),
                        'foi_email': '',
                        'foi_disclosure_page_url': ''
                    })
                    continue
                
                # Extract FOI email
                foi_email = find_foi_email(foi_page_url)
                
                # Extract disclosure log page
                disclosure_page_url = find_disclosure_log_page(foi_page_url)
                
                writer.writerow({
                    'public_body_id': row.get('public_body_id', ''),
                    'public_body_name': row.get('public_body_name', ''),
                    'foi_email': foi_email or '',
                    'foi_disclosure_page_url': disclosure_page_url or ''
                })
                outfile.flush()
                
                # Rate limiting
                time.sleep(RATE_LIMIT_DELAY)


def main():
    parser = argparse.ArgumentParser(
        description="Extract FOI email addresses and disclosure log page URLs from FOI pages."
    )
    parser.add_argument('--input-file', required=True, 
                       help='Path to input CSV with a foi_page_url column')
    parser.add_argument('--output-file', required=True, 
                       help='Path to write the contact info CSV')
    args = parser.parse_args()
    
    process_csv(args.input_file, args.output_file)


if __name__ == '__main__':
    main()