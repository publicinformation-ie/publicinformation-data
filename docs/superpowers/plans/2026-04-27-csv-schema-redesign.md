# CSV Schema Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename four CSV files, standardise all column names to snake_case, merge two related files, and add `last_checked`/`last_modified` tracking columns to every file.

**Architecture:** A single Python migration script (`scripts/migrate_schema.py`) reads the five source files and writes four replacement files. The script runs from the project root. Old files are deleted by hand after the migration is verified. A pytest test suite in `scripts/test_migrate_schema.py` validates every transformation before the migration runs against real data.

**Tech Stack:** Python 3 stdlib (`csv`, `datetime`, `pathlib`), pytest 9+

---

## Files

| Action | Path |
|---|---|
| Create | `scripts/migrate_schema.py` |
| Create | `scripts/test_migrate_schema.py` |
| Create (output) | `public_bodies.csv` |
| Create (output) | `public_body_foi_pages.csv` |
| Create (output) | `public_body_foi_details.csv` |
| Create (output) | `public_body_foi_disclosure_files.csv` |
| Delete (after verify) | `public_bodies_ireland.csv` |
| Delete (after verify) | `public_body_foi_page_urls.csv` |
| Delete (after verify) | `public_body_foi_contact.csv` |
| Delete (after verify) | `public_body_foi_disclosure_page_urls.csv` |
| Delete (after verify) | `public_body_foi_disclosure_file_urls.csv` |

---

## Notes on key decisions

- **`last_checked`/`last_modified` initial values:** New files (`public_bodies.csv`, `public_body_foi_details.csv`, `public_body_foi_disclosure_files.csv`) use today's date for both. `public_body_foi_pages.csv` seeds both from the existing `last_checked_date` column since that's the most accurate available value.
- **Merge strategy for `public_body_foi_details.csv`:** `foi_contact_email` comes from `public_body_foi_contact.csv`; `foi_disclosure_page_url` comes from `public_body_foi_disclosure_page_urls.csv` (the authoritative collections URL used in the pipeline). The contact file's `foi_disclosure_page_url` column (which contains page anchors, e.g. `#disclosure-logs`) is intentionally dropped.
- **`date_added` in disclosure files:** Source data uses `DD/MM/YYYY`; migration normalises to `YYYY-MM-DD` ISO format to match all other date columns.

---

## Task 1: Write the migration script

**Files:**
- Create: `scripts/migrate_schema.py`

- [ ] **Step 1: Create the script**

```python
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
    new_rows = [
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
    ]
    write_csv(ROOT / 'public_bodies.csv', fieldnames, new_rows)
    return len(new_rows)


def migrate_foi_pages():
    rows = read_csv(ROOT / 'public_body_foi_page_urls.csv')
    fieldnames = [
        'public_body_id', 'public_body_name', 'foi_page_url',
        'is_reachable', 'last_checked', 'last_modified',
    ]
    new_rows = [
        {
            'public_body_id': r['public_body_id'],
            'public_body_name': r['public_body_name'],
            'foi_page_url': r['foi_page_url'],
            'is_reachable': r['is_reachable'],
            'last_checked': r['last_checked_date'],
            'last_modified': r['last_checked_date'],
        }
        for r in rows
    ]
    write_csv(ROOT / 'public_body_foi_pages.csv', fieldnames, new_rows)
    return len(new_rows)


def migrate_foi_details():
    contact = {r['public_body_id']: r for r in read_csv(ROOT / 'public_body_foi_contact.csv')}
    disclosure = {r['public_body_id']: r for r in read_csv(ROOT / 'public_body_foi_disclosure_page_urls.csv')}
    all_ids = sorted(set(contact) | set(disclosure), key=lambda x: int(x))
    fieldnames = [
        'public_body_id', 'public_body_name', 'foi_contact_email',
        'foi_disclosure_page_url', 'last_checked', 'last_modified',
    ]
    new_rows = [
        {
            'public_body_id': body_id,
            'public_body_name': (contact.get(body_id) or disclosure.get(body_id, {})).get('public_body_name', ''),
            'foi_contact_email': contact.get(body_id, {}).get('foi_email', ''),
            'foi_disclosure_page_url': disclosure.get(body_id, {}).get('foi_disclosure_url', ''),
            'last_checked': TODAY,
            'last_modified': TODAY,
        }
        for body_id in all_ids
    ]
    write_csv(ROOT / 'public_body_foi_details.csv', fieldnames, new_rows)
    return len(new_rows)


def migrate_disclosure_files():
    rows = read_csv(ROOT / 'public_body_foi_disclosure_file_urls.csv')
    fieldnames = [
        'public_body_id', 'public_body_name', 'source_page_url',
        'document_url', 'date_added', 'last_checked', 'last_modified',
    ]
    new_rows = [
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
    ]
    write_csv(ROOT / 'public_body_foi_disclosure_files.csv', fieldnames, new_rows)
    return len(new_rows)


if __name__ == '__main__':
    counts = {
        'public_bodies.csv': migrate_public_bodies(),
        'public_body_foi_pages.csv': migrate_foi_pages(),
        'public_body_foi_details.csv': migrate_foi_details(),
        'public_body_foi_disclosure_files.csv': migrate_disclosure_files(),
    }
    for filename, count in counts.items():
        print(f'  {filename}: {count} rows')
    print('Migration complete.')
```

Save as `scripts/migrate_schema.py`.

---

## Task 2: Write the test suite

**Files:**
- Create: `scripts/test_migrate_schema.py`

- [ ] **Step 1: Create the test file**

```python
"""Tests for migrate_schema.py"""

import csv
import shutil
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import migrate_schema as m


@pytest.fixture
def workspace(tmp_path):
    """Copy source CSV files into a temp dir and patch ROOT."""
    root = Path(__file__).parent.parent
    for src in root.glob('*.csv'):
        shutil.copy(src, tmp_path / src.name)
    original_root = m.ROOT
    m.ROOT = tmp_path
    yield tmp_path
    m.ROOT = original_root


def read_csv(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


class TestPublicBodies:
    def test_headers(self, workspace):
        m.migrate_public_bodies()
        rows = read_csv(workspace / 'public_bodies.csv')
        assert list(rows[0].keys()) == [
            'public_body_id', 'public_body_name', 'public_body_short_name',
            'public_body_url', 'public_body_category', 'last_checked', 'last_modified',
        ]

    def test_row_count_preserved(self, workspace):
        original = read_csv(workspace / 'public_bodies_ireland.csv')
        m.migrate_public_bodies()
        migrated = read_csv(workspace / 'public_bodies.csv')
        assert len(migrated) == len(original)

    def test_known_value_preserved(self, workspace):
        m.migrate_public_bodies()
        rows = read_csv(workspace / 'public_bodies.csv')
        row = next(r for r in rows if r['public_body_id'] == '1001')
        assert row['public_body_name'] == 'Department of Agriculture, Food and the Marine'
        assert row['public_body_short_name'] == 'DAFM'
        assert row['public_body_category'] == 'government department'

    def test_tracking_columns_are_today(self, workspace):
        m.migrate_public_bodies()
        rows = read_csv(workspace / 'public_bodies.csv')
        assert rows[0]['last_checked'] == date.today().isoformat()
        assert rows[0]['last_modified'] == date.today().isoformat()


class TestFoiPages:
    def test_headers(self, workspace):
        m.migrate_foi_pages()
        rows = read_csv(workspace / 'public_body_foi_pages.csv')
        assert list(rows[0].keys()) == [
            'public_body_id', 'public_body_name', 'foi_page_url',
            'is_reachable', 'last_checked', 'last_modified',
        ]

    def test_row_count_preserved(self, workspace):
        original = read_csv(workspace / 'public_body_foi_page_urls.csv')
        m.migrate_foi_pages()
        migrated = read_csv(workspace / 'public_body_foi_pages.csv')
        assert len(migrated) == len(original)

    def test_last_checked_date_renamed_and_value_preserved(self, workspace):
        original = read_csv(workspace / 'public_body_foi_page_urls.csv')
        m.migrate_foi_pages()
        migrated = read_csv(workspace / 'public_body_foi_pages.csv')
        assert 'last_checked_date' not in migrated[0]
        assert migrated[0]['last_checked'] == original[0]['last_checked_date']

    def test_last_modified_seeded_from_last_checked_date(self, workspace):
        original = read_csv(workspace / 'public_body_foi_page_urls.csv')
        m.migrate_foi_pages()
        migrated = read_csv(workspace / 'public_body_foi_pages.csv')
        assert migrated[0]['last_modified'] == original[0]['last_checked_date']

    def test_is_reachable_preserved(self, workspace):
        m.migrate_foi_pages()
        rows = read_csv(workspace / 'public_body_foi_pages.csv')
        row = next(r for r in rows if r['public_body_id'] == '1001')
        assert row['is_reachable'] == 'true'


class TestFoiDetails:
    def test_headers(self, workspace):
        m.migrate_foi_details()
        rows = read_csv(workspace / 'public_body_foi_details.csv')
        assert list(rows[0].keys()) == [
            'public_body_id', 'public_body_name', 'foi_contact_email',
            'foi_disclosure_page_url', 'last_checked', 'last_modified',
        ]

    def test_foi_email_renamed_and_value_preserved(self, workspace):
        m.migrate_foi_details()
        rows = read_csv(workspace / 'public_body_foi_details.csv')
        assert 'foi_email' not in rows[0]
        row = next(r for r in rows if r['public_body_id'] == '1001')
        assert row['foi_contact_email'] == 'freedomofinformation@agriculture.gov.ie'

    def test_foi_disclosure_url_renamed_and_value_from_disclosure_file(self, workspace):
        m.migrate_foi_details()
        rows = read_csv(workspace / 'public_body_foi_details.csv')
        assert 'foi_disclosure_url' not in rows[0]
        row = next(r for r in rows if r['public_body_id'] == '1001')
        assert row['foi_disclosure_page_url'] == (
            'https://www.gov.ie/en/department-of-agriculture-food-and-the-marine/'
            'collections/freedom-of-information-disclosure-logs/'
        )

    def test_all_contact_ids_present(self, workspace):
        contact_ids = {r['public_body_id'] for r in read_csv(workspace / 'public_body_foi_contact.csv')}
        m.migrate_foi_details()
        migrated_ids = {r['public_body_id'] for r in read_csv(workspace / 'public_body_foi_details.csv')}
        assert contact_ids.issubset(migrated_ids)

    def test_all_disclosure_ids_present(self, workspace):
        disc_ids = {r['public_body_id'] for r in read_csv(workspace / 'public_body_foi_disclosure_page_urls.csv')}
        m.migrate_foi_details()
        migrated_ids = {r['public_body_id'] for r in read_csv(workspace / 'public_body_foi_details.csv')}
        assert disc_ids.issubset(migrated_ids)

    def test_tracking_columns_are_today(self, workspace):
        m.migrate_foi_details()
        rows = read_csv(workspace / 'public_body_foi_details.csv')
        assert rows[0]['last_checked'] == date.today().isoformat()
        assert rows[0]['last_modified'] == date.today().isoformat()


class TestDisclosureFiles:
    def test_headers(self, workspace):
        m.migrate_disclosure_files()
        rows = read_csv(workspace / 'public_body_foi_disclosure_files.csv')
        assert list(rows[0].keys()) == [
            'public_body_id', 'public_body_name', 'source_page_url',
            'document_url', 'date_added', 'last_checked', 'last_modified',
        ]

    def test_row_count_preserved(self, workspace):
        original = read_csv(workspace / 'public_body_foi_disclosure_file_urls.csv')
        m.migrate_disclosure_files()
        migrated = read_csv(workspace / 'public_body_foi_disclosure_files.csv')
        assert len(migrated) == len(original)

    def test_date_normalised_to_iso(self, workspace):
        m.migrate_disclosure_files()
        rows = read_csv(workspace / 'public_body_foi_disclosure_files.csv')
        assert rows[0]['date_added'] == '2026-04-13'

    def test_known_values_preserved(self, workspace):
        m.migrate_disclosure_files()
        rows = read_csv(workspace / 'public_body_foi_disclosure_files.csv')
        row = rows[0]
        assert row['public_body_id'] == '1001'
        assert row['public_body_name'] == 'Department of Agriculture, Food and the Marine'
        assert 'assets.gov.ie' in row['document_url']
        assert 'collections/freedom-of-information-disclosure-logs' in row['source_page_url']

    def test_old_column_names_absent(self, workspace):
        m.migrate_disclosure_files()
        rows = read_csv(workspace / 'public_body_foi_disclosure_files.csv')
        assert 'Date Added' not in rows[0]
        assert 'Public Entity Name' not in rows[0]
        assert 'Source Page' not in rows[0]
        assert 'Document Link' not in rows[0]


class TestParseDate:
    def test_converts_dd_mm_yyyy(self):
        assert m.parse_date('13/04/2026') == '2026-04-13'

    def test_leading_zeros(self):
        assert m.parse_date('01/01/2025') == '2025-01-01'
```

Save as `scripts/test_migrate_schema.py`.

---

## Task 3: Run the tests

**Files:** none modified

- [ ] **Step 1: Run tests and confirm all pass**

Run from the project root:
```bash
python3 -m pytest scripts/test_migrate_schema.py -v
```

Expected output — all tests pass, e.g.:
```
scripts/test_migrate_schema.py::TestPublicBodies::test_headers PASSED
scripts/test_migrate_schema.py::TestPublicBodies::test_row_count_preserved PASSED
...
22 passed in 0.XXs
```

If any test fails, fix `scripts/migrate_schema.py` until all pass before proceeding.

- [ ] **Step 2: Commit scripts**

```bash
git add scripts/migrate_schema.py scripts/test_migrate_schema.py
git commit -m "Add CSV schema migration script and tests"
```

---

## Task 4: Execute the migration

**Files:** Creates four new CSV files in project root.

- [ ] **Step 1: Run the migration**

```bash
python3 scripts/migrate_schema.py
```

Expected output:
```
  public_bodies.csv: 285 rows
  public_body_foi_pages.csv: 286 rows
  public_body_foi_details.csv: 286 rows
  public_body_foi_disclosure_files.csv: 488 rows
Migration complete.
```

*(Row counts may differ slightly — what matters is they match the source file row counts.)*

- [ ] **Step 2: Spot-check each output file**

```bash
head -2 public_bodies.csv
head -2 public_body_foi_pages.csv
head -2 public_body_foi_details.csv
head -2 public_body_foi_disclosure_files.csv
```

Verify:
- Headers match the schema in the spec exactly
- First data row values look correct (names, URLs, dates)
- `date_added` in disclosure files is in `YYYY-MM-DD` format (not `DD/MM/YYYY`)

---

## Task 5: Remove old files and final commit

**Files:** Deletes five source CSV files.

- [ ] **Step 1: Delete the source files**

```bash
git rm public_bodies_ireland.csv \
       public_body_foi_page_urls.csv \
       public_body_foi_contact.csv \
       public_body_foi_disclosure_page_urls.csv \
       public_body_foi_disclosure_file_urls.csv
```

- [ ] **Step 2: Stage new CSV files**

```bash
git add public_bodies.csv \
        public_body_foi_pages.csv \
        public_body_foi_details.csv \
        public_body_foi_disclosure_files.csv
```

- [ ] **Step 3: Commit**

```bash
git commit -m "Migrate CSV schema: rename files, standardise columns, add tracking dates"
```

---

## Out of scope (follow-up)

`data_structure.yml` should be updated to reflect the new file names and column schemas. This is a separate task.
