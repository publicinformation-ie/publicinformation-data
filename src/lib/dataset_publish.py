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

    ttl_text = ttl_path.read_text()
    new_ttl_text, count = DCT_MODIFIED_RE.subn(
        rf'\g<1>{date.today().isoformat()}\g<2>', ttl_text, count=1
    )
    if count != 1:
        raise ValueError(f"dct:modified field not found in {ttl_path}")
    ttl_path.write_text(new_ttl_text)

    return True
