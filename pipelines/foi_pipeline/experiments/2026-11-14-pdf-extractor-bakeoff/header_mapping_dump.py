"""Dump {file_url: {header_text: canonical}} for every transform record.

Used to list the blast radius of a column_map change: run before and after, then diff.
"""
import argparse
import json
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[4] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from lib.column_map import canonicalize_headers  # noqa: E402
from lib.table_utils import detect_header_row  # noqa: E402


def dump(records: list[dict]) -> dict[str, dict[str, str | None]]:
    out: dict[str, dict[str, str | None]] = {}
    for rec in records:
        rows = rec.get("rows")
        if not rows:
            continue
        header = [str(c) for c in rows[detect_header_row(rows)] if c not in (None, "")]
        mapping = canonicalize_headers(header)
        out.setdefault(rec["file_url"], {}).update(mapping)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--transform", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    records = json.load(open(args.transform))["results"]
    Path(args.out).write_text(json.dumps(dump(records), indent=1, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
