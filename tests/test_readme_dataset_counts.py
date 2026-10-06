"""Pin root README dataset record counts to csv-module row counts.

`wc -l` is not a record count: quoted fields contain embedded newlines
(foi-disclosures is off by 2,112 lines). This test parses properly so the
published numbers cannot regress to line counts again.
"""

import csv
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"

# dataset label in the README table -> (slug, primary CSV). The primary CSV
# is the table a reader means by "records" for multi-table datasets.
PRIMARY = {
    "Public Bodies": ("public-bodies", "public-bodies.csv"),
    "FOI Disclosures": ("foi-disclosures", "foi-disclosures.csv"),
    "FOI Request Files": ("foi-request-files", "foi-request-files.csv"),
    "Who Does What": ("who-does-what", "who-does-what.csv"),
    "data.gov.ie Links": ("data-gov-ie-links", "data-gov-ie-links.csv"),
    "lobbying.ie Links": ("lobbying-ie-links", "lobbying-ie-links.csv"),
    "Public Body Actions": ("public-body-actions", "actions.csv"),
    "Motions": ("motions", "motions.csv"),
}


def _csv_records(slug: str, basename: str) -> int:
    path = REPO_ROOT / "public" / "latest" / slug / basename
    with path.open(newline="", encoding="utf-8") as fh:
        return sum(1 for _ in csv.DictReader(fh))


def test_readme_record_counts_match_primary_csvs():
    text = README.read_text(encoding="utf-8")
    for label, (slug, basename) in PRIMARY.items():
        match = re.search(rf"\| {re.escape(label)} \| \S+ \| ([\d,]+) \|",
                          text)
        assert match, f"README table row missing for {label}"
        claimed = int(match.group(1).replace(",", ""))
        assert claimed == _csv_records(slug, basename), (
            f"{label}: README claims {claimed}, "
            f"{slug}/{basename} has {_csv_records(slug, basename)} records")
