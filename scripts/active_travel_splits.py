"""Derived, spreadsheet-friendly splits of the Active Travel allocations dataset.

The combined CSV is 2 MB and 13 columns, which is awkward for a casual user. These
splits publish the same published records as small, plain CSVs that Google Sheets
can pull in with one formula, e.g.

    =IMPORTDATA("https://data.publicinformation.ie/latest/active-travel-allocations/by-recipient/carlow-county-council.csv")

(IMPORTRANGE only reads other Google Sheets; IMPORTDATA is the CSV-from-a-URL
equivalent.) Two splits, each with an index.csv listing every file and its URL:

  by-recipient/<recipient-slug>.csv   all years for one recipient
  by-year/<year>.csv                  one NTA edition, in the NTA's recipient order

They are derived views, published under latest/ only: they carry no version of
their own and are rebuilt from the same records as the combined files, so they
cannot drift from them.
"""
from pathlib import Path

from src.lib.dataset_publish import render_csv

PUBLIC_BASE_URL = "https://data.publicinformation.ie/latest/active-travel-allocations"

# Friendly subset of the published columns: no URIs, hashes or join keys.
SPLIT_FIELDNAMES = [
    "year", "recipient_name", "funding_stream", "project_code", "project_name",
    "allocation_eur", "source_document_url", "source_page",
]
RECIPIENT_INDEX_FIELDNAMES = [
    "recipient_name", "public_body_id", "years", "projects", "total_allocation_eur",
    "file", "url",
]
YEAR_INDEX_FIELDNAMES = [
    "year", "recipients", "projects", "total_allocation_eur", "source_document_url",
    "file", "url",
]


def recipient_slug(record: dict) -> str:
    """The recipient segment of the record's permanent @id
    (.../allocation/<slug>/<year>/<stream>/<key>)."""
    return record["@id"].split("/allocation/", 1)[1].split("/", 1)[0]


def _row(record: dict) -> dict:
    return {field: record[field] for field in SPLIT_FIELDNAMES}


def build_splits(records: list[dict]) -> dict[str, bytes]:
    """Return {path relative to the dataset directory: CSV bytes}.

    `records` must be in the export order, which follows the order the NTA prints
    each document; that order is preserved within each file.
    """
    by_recipient: dict[str, list[dict]] = {}
    by_year: dict[int, list[dict]] = {}
    for record in records:
        by_recipient.setdefault(recipient_slug(record), []).append(record)
        by_year.setdefault(record["year"], []).append(record)

    files: dict[str, bytes] = {}

    recipient_index = []
    for slug in sorted(by_recipient):
        group = sorted(by_recipient[slug], key=lambda r: r["year"])  # stable
        path = f"by-recipient/{slug}.csv"
        files[path] = render_csv(SPLIT_FIELDNAMES, [_row(r) for r in group])
        years = sorted({r["year"] for r in group})
        recipient_index.append({
            "recipient_name": group[0]["recipient_name"],
            "public_body_id": group[0].get("public_body_id", ""),
            "years": f"{years[0]}-{years[-1]}" if len(years) > 1 else str(years[0]),
            "projects": len(group),
            "total_allocation_eur": sum(r["allocation_eur"] for r in group),
            "file": f"{slug}.csv",
            "url": f"{PUBLIC_BASE_URL}/{path}",
        })
    recipient_index.sort(key=lambda r: r["recipient_name"].casefold())
    files["by-recipient/index.csv"] = render_csv(RECIPIENT_INDEX_FIELDNAMES, recipient_index)

    year_index = []
    for year in sorted(by_year):
        group = by_year[year]
        path = f"by-year/{year}.csv"
        files[path] = render_csv(SPLIT_FIELDNAMES, [_row(r) for r in group])
        year_index.append({
            "year": year,
            "recipients": len({recipient_slug(r) for r in group}),
            "projects": len(group),
            "total_allocation_eur": sum(r["allocation_eur"] for r in group),
            "source_document_url": group[0]["source_document_url"],
            "file": f"{year}.csv",
            "url": f"{PUBLIC_BASE_URL}/{path}",
        })
    files["by-year/index.csv"] = render_csv(YEAR_INDEX_FIELDNAMES, year_index)
    return files


def write_splits(files: dict[str, bytes], latest_dir: Path) -> bool:
    """Write the splits under latest_dir, touching only files whose bytes differ and
    removing split files that are no longer produced. Returns True if anything
    changed."""
    changed = False
    for relative, data in files.items():
        target = latest_dir / relative
        if target.exists() and target.read_bytes() == data:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        changed = True
    for folder in ("by-recipient", "by-year"):
        for existing in sorted((latest_dir / folder).glob("*.csv")):
            if f"{folder}/{existing.name}" not in files:
                existing.unlink()
                changed = True
    return changed
