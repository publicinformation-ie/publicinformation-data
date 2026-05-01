import csv
import io
import json
import sys
import requests

CSV_URL = "https://codeberg.org/gingertechie/publicinformation-data/raw/branch/main/public_bodies.csv"
OUTPUT_PATH = "src/data/public_bodies.json"

REQUIRED_COLUMNS = {
    "public_body_id",
    "public_body_name",
    "public_body_short_name",
    "public_body_url",
    "public_body_category",
}


def convert_csv_to_json():
    try:
        response = requests.get(CSV_URL, timeout=30)
        response.raise_for_status()
        reader = csv.DictReader(io.StringIO(response.text))
        rows = list(reader)

        if not rows or not REQUIRED_COLUMNS.issubset(set(rows[0].keys())):
            print(
                f"Warning: CSV missing required columns. Found: {list(rows[0].keys()) if rows else 'none'}",
                file=sys.stderr,
            )
            _write([], OUTPUT_PATH)
            return

        records = [
            {
                "public_body_id": int(row["public_body_id"]) if row["public_body_id"].isdigit() else row["public_body_id"],
                "public_body_name": row["public_body_name"],
                "public_body_short_name": row["public_body_short_name"],
                "public_body_url": row["public_body_url"],
                "public_body_category": row["public_body_category"],
            }
            for row in rows
        ]
        _write(records, OUTPUT_PATH)
        print(f"Wrote {len(records)} records to {OUTPUT_PATH}")

    except Exception as exc:
        print(f"Error fetching/parsing CSV: {exc}", file=sys.stderr)
        _write([], OUTPUT_PATH)


def _write(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    convert_csv_to_json()
