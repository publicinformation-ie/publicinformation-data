#!/usr/bin/env python3
"""Migrate CSV files to updated schema."""

import csv
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
TODAY = date.today().isoformat()


def read_csv(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def write_csv(path, fieldnames, rows):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_date(value):
    """Normalise DD/MM/YYYY to YYYY-MM-DD."""
    return datetime.strptime(value, '%d/%m/%Y').date().isoformat()


def migrate_public_bodies():
    rows = read_csv(ROOT / 'public_bodies_ireland.csv')
    fieldnames = [
        'public_body_id', 'public_body_name', 'public_body_short_name',
        'public_body_url', 'public_body_category', 'last_checked', 'last_modified',
    ]
    write_csv(ROOT / 'public_bodies.csv', fieldnames, [
        {
            'public_body_id': r['public_body_id'],
            'public_body_name': r['public_body_name'],
            'public_body_short_name': r['public_body_short_name'],
            'public_body_url': r['public_body_url'],
            'public_body_category': r['public_body_category'],
            'last_checked': TODAY,
            'last_modified': TODAY,
        }
        for r in rows
    ])
    return len(rows)


def migrate_foi_pages():
    rows = read_csv(ROOT / 'public_body_foi_page_urls.csv')
    fieldnames = [
        'public_body_id', 'public_body_name', 'foi_page_url',
        'is_reachable', 'last_checked', 'last_modified',
    ]
    write_csv(ROOT / 'public_body_foi_pages.csv', fieldnames, [
        {
            'public_body_id': r['public_body_id'],
            'public_body_name': r['public_body_name'],
            'foi_page_url': r['foi_page_url'],
            'is_reachable': r['is_reachable'],
            'last_checked': r['last_checked_date'],
            'last_modified': r['last_checked_date'],
        }
        for r in rows
    ])
    return len(rows)


def migrate_foi_details():
    contact = {r['public_body_id']: r for r in read_csv(ROOT / 'public_body_foi_contact.csv')}
    disclosure = {r['public_body_id']: r for r in read_csv(ROOT / 'public_body_foi_disclosure_page_urls.csv')}
    all_ids = sorted(set(contact) | set(disclosure), key=lambda x: int(x))
    fieldnames = [
        'public_body_id', 'public_body_name', 'foi_contact_email',
        'foi_disclosure_page_url', 'last_checked', 'last_modified',
    ]
    write_csv(ROOT / 'public_body_foi_details.csv', fieldnames, [
        {
            'public_body_id': body_id,
            'public_body_name': (contact.get(body_id) or disclosure.get(body_id, {})).get('public_body_name', ''),
            'foi_contact_email': contact.get(body_id, {}).get('foi_email', ''),
            'foi_disclosure_page_url': disclosure.get(body_id, {}).get('foi_disclosure_url', ''),
            'last_checked': TODAY,
            'last_modified': TODAY,
        }
        for body_id in all_ids
    ])
    return len(all_ids)


def migrate_disclosure_files():
    rows = read_csv(ROOT / 'public_body_foi_disclosure_file_urls.csv')
    fieldnames = [
        'public_body_id', 'public_body_name', 'source_page_url',
        'document_url', 'date_added', 'last_checked', 'last_modified',
    ]
    write_csv(ROOT / 'public_body_foi_disclosure_files.csv', fieldnames, [
        {
            'public_body_id': r['public_body_id'],
            'public_body_name': r['Public Entity Name'],
            'source_page_url': r['Source Page'],
            'document_url': r['Document Link'],
            'date_added': parse_date(r['Date Added']),
            'last_checked': TODAY,
            'last_modified': TODAY,
        }
        for r in rows
    ])
    return len(rows)


if __name__ == '__main__':
    print(f'  public_bodies.csv: {migrate_public_bodies()} rows')
    print(f'  public_body_foi_pages.csv: {migrate_foi_pages()} rows')
    print(f'  public_body_foi_details.csv: {migrate_foi_details()} rows')
    print(f'  public_body_foi_disclosure_files.csv: {migrate_disclosure_files()} rows')
    print('Done.')
