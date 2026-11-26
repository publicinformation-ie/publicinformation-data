#!/usr/bin/env python3
"""Build reference/cofog_1999.json from the UNSD COFOG 1999 structure file.

Usage:
    uv run python pipelines/spc_pipeline/scripts/build_cofog.py
    uv run python pipelines/spc_pipeline/scripts/build_cofog.py --input /path/to/COFOG_english_structure.txt

The committed JSON records the source URL, the retrieval date and the source
file's sha256 so the list can be re-derived and checked later. It is
regenerated only when the source changes; a different sha256 is a reviewed
content change.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

import requests

SOURCE_URL = (
    "https://unstats.un.org/unsd/classifications/Econ/Download/In%20Text/"
    "COFOG_english_structure.txt"
)
OUTPUT = Path(__file__).resolve().parents[1] / "reference" / "cofog_1999.json"

_LINE_RE = re.compile(r"^(?P<code>\d{2}(?:\.\d+)*)\s{2,}(?P<description>.+?)\s*$")
_MARKER_RE = re.compile(r"\s*\((CS|IS)\)\s*$")


def level_of(code: str) -> str:
    parts = code.count(".") + 1
    return {1: "division", 2: "group", 3: "class"}[parts]


def parent_of(code: str) -> str | None:
    return code.rsplit(".", 1)[0] if "." in code else None


def parse_structure(text: str) -> list[dict]:
    codes: list[dict] = []
    for line in text.splitlines():
        match = _LINE_RE.match(line)
        if not match:
            continue
        code = match.group("code")
        description = match.group("description")
        marker_match = _MARKER_RE.search(description)
        marker = marker_match.group(1) if marker_match else None
        if marker_match:
            description = description[:marker_match.start()].rstrip()
        codes.append({
            "code": code,
            "level": level_of(code),
            "description": description,
            "marker": marker,
            "parent": parent_of(code),
        })
    return codes


def build(source_bytes: bytes, retrieved: str) -> dict:
    codes = parse_structure(source_bytes.decode("utf-8"))
    if not codes:
        raise ValueError("no COFOG codes parsed from the source file")
    known = {code["code"] for code in codes}
    for code in codes:
        parent = code["parent"]
        if parent is not None and parent not in known:
            raise ValueError(f"COFOG code {code['code']} has missing parent {parent}")
    return {
        "metadata": {
            "source_url": SOURCE_URL,
            "retrieved_date": retrieved,
            "sha256": hashlib.sha256(source_bytes).hexdigest(),
            "byte_size": len(source_bytes),
        },
        "codes": codes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="local copy of the structure file")
    parser.add_argument("--retrieved", default=date.today().isoformat(),
                        help="retrieval date recorded in the output (YYYY-MM-DD)")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    if args.input is not None:
        source_bytes = args.input.read_bytes()
    else:
        response = requests.get(SOURCE_URL, timeout=60)
        response.raise_for_status()
        source_bytes = response.content

    data = build(source_bytes, args.retrieved)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(f"Wrote {len(data['codes'])} COFOG codes to {args.output}")


if __name__ == "__main__":
    sys.exit(main())
