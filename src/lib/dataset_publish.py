"""Shared publish helpers for the 5 catalogued datasets' transform_*.py scripts.

Splits versioning into two independent signals (see
docs/superpowers/specs/2026-07-13-catalog-versioning-policy-design.md):
owl:versionInfo is bumped by hand for schema/shape changes; dct:modified is
stamped here, automatically, only when a script's output content actually
changed.
"""
import csv
import io
import json
import re
from datetime import date
from pathlib import Path

DCT_MODIFIED_RE = re.compile(r'(dct:modified\s+")[^"]*("\^\^xsd:date\s*;)')


def render_jsonld(data: dict) -> bytes:
    return json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")


def render_csv(fieldnames: list[str], rows: list[dict]) -> bytes:
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def stamp_modified(ttl_path: Path, today: date | None = None) -> None:
    """Rewrite `dct:modified` in ttl_path to `today` (default: the current date)."""
    ttl_text = ttl_path.read_text()
    new_ttl_text, count = DCT_MODIFIED_RE.subn(
        rf'\g<1>{(today or date.today()).isoformat()}\g<2>', ttl_text, count=1
    )
    if count != 1:
        raise ValueError(f"dct:modified field not found in {ttl_path}")
    ttl_path.write_text(new_ttl_text)


def write_xlsx(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    """Write rows to an XLSX (openpyxl write-only mode) with fieldnames as the header.
    Cell values are the same values the CSV carries; None becomes an empty cell."""
    from openpyxl import Workbook
    from openpyxl.cell import WriteOnlyCell

    wb = Workbook(write_only=True)
    ws = wb.create_sheet("foi-disclosures")

    def cell(value):
        # openpyxl turns any string starting with "=" into a formula. Force
        # literal text so source-controlled strings can never execute.
        c = WriteOnlyCell(ws, value=_xlsx_cell(value))
        if isinstance(c.value, str):
            c.data_type = "s"
        return c

    ws.append([cell(f) for f in fieldnames])
    for row in rows:
        ws.append([cell(row.get(f, "")) for f in fieldnames])
    wb.save(path)


def _xlsx_cell(value):
    """XLSX is XML 1.0, which cannot hold control characters such as \x00-\x08 or
    \x0b-\x1f; they are dropped here (the CSV keeps them verbatim)."""
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

    if isinstance(value, list):
        value = "|".join(str(v) for v in value)
    if isinstance(value, str):
        return ILLEGAL_CHARACTERS_RE.sub("", value)
    return value


def stamp_if_changed(ttl_path: Path, payload_paths: list[Path], generated: dict[Path, bytes]) -> bool:
    """
    Compare `generated` (path -> new file bytes, for each path in payload_paths) against what's
    currently on disk at those paths. If any differ, write the new bytes to disk and rewrite
    `dct:modified` in ttl_path to today's date. Returns True if anything was written.
    If nothing differs, leaves everything untouched (no-op) and returns False.
    """
    changed = any(
        not path.exists() or path.read_bytes() != generated[path]
        for path in payload_paths
    )
    if not changed:
        return False

    for path in payload_paths:
        path.write_bytes(generated[path])

    stamp_modified(ttl_path)

    return True
