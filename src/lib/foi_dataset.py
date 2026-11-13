"""Per-body NDJSON storage for the FOI disclosures dataset.

The committed dataset is one canonical NDJSON file per public body
(`<public_body_id>.ndjson`, one compact JSON row per line). Every other form
(combined JSON, CSV, JSON-LD, XLSX, manifest) is built from these files and is
never committed. The serialisation rules live here so the export step, the
build script, the tests and the size guard all agree on them.
"""
import hashlib
import json
from pathlib import Path

FIELD_ORDER = [
    "public_body_id", "name", "file_url", "file_type", "foi_reference_id",
    "date_received", "decision_date", "requester_type", "decision_status",
    "review_status", "related_request", "request_description", "row_id",
    "known_issues", "missing_columns",
]
BODIES_RELPATH = "latest/foi-disclosures/bodies"
SITE_URL = "https://data.publicinformation.ie"
SUFFIX = ".ndjson"


def serialise_row(row):
    """One canonical JSON line (no newline). Fixed key order, compact,
    UTF-8 text, with U+2028/U+2029 escaped so no reader splits the row."""
    ordered = {k: row[k] for k in FIELD_ORDER if k in row}
    for k in sorted(set(row) - set(ordered)):
        ordered[k] = row[k]
    text = json.dumps(ordered, separators=(",", ":"), ensure_ascii=False)
    return text.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def _serialise_body(rows):
    return "".join(serialise_row(r) + "\n" for r in sorted(rows, key=lambda r: r["row_id"])).encode("utf-8")


def _group(rows):
    groups = {}
    for i, row in enumerate(rows):
        if row.get("public_body_id") is None:
            raise ValueError(f"row {i} has no public_body_id: {row!r}")
        if not row.get("row_id"):
            raise ValueError(f"row {i} has no row_id: {row!r}")
        groups.setdefault(row["public_body_id"], []).append(row)
    return groups


def part_path(out_dir, public_body_id):
    return Path(out_dir) / f"{public_body_id}{SUFFIX}"


def write_parts(rows, out_dir):
    """Write one canonical file per body and remove files for bodies with no
    rows. Raises before writing anything if any row lacks `public_body_id`.

    Returns {"added": [...], "changed": [...], "removed": [...]} (body ids),
    so callers can tell whether the stored dataset actually changed.
    """
    groups = _group(rows)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {"added": [], "changed": [], "removed": []}
    for body_id, body_rows in sorted(groups.items()):
        data = _serialise_body(body_rows)
        path = part_path(out_dir, body_id)
        if not path.exists():
            report["added"].append(body_id)
        elif path.read_bytes() != data:
            report["changed"].append(body_id)
        else:
            continue
        path.write_bytes(data)
    keep = {part_path(out_dir, b).name for b in groups}
    for path in sorted(out_dir.glob(f"*{SUFFIX}")):
        if path.name not in keep:
            path.unlink()
            report["removed"].append(path.stem)
    return report


def _body_files(out_dir):
    return sorted(Path(out_dir).glob(f"*{SUFFIX}"), key=lambda p: (len(p.stem), p.stem))


def _read_body(path):
    text = path.read_bytes().decode("utf-8")
    return [json.loads(line) for line in text.splitlines()] if text else []


def load_parts(out_dir):
    """All rows, ordered by (public_body_id, row_id)."""
    rows = []
    for path in _body_files(out_dir):
        rows.extend(_read_body(path))
    rows.sort(key=lambda r: (r["public_body_id"], r["row_id"]))
    return rows


def verify_parts(out_dir):
    """Return a list of problems (empty when the folder is canonical)."""
    problems = []
    seen = {}
    for path in _body_files(out_dir):
        raw = path.read_bytes()
        try:
            rows = _read_body(path)
        except ValueError as exc:
            problems.append(f"{path.name}: does not parse: {exc}")
            continue
        for row in rows:
            if str(row.get("public_body_id")) != path.stem:
                problems.append(f"{path.name}: row_id {row.get('row_id')} has public_body_id {row.get('public_body_id')!r}")
            rid = row.get("row_id")
            if rid in seen:
                problems.append(f"{path.name}: duplicate row_id {rid} (also in {seen[rid]})")
            seen[rid] = path.name
        ids = [r.get("row_id") for r in rows]
        if ids != sorted(ids):
            problems.append(f"{path.name}: rows are not in row_id order")
        elif raw != _serialise_body(rows):
            problems.append(f"{path.name}: not canonical (differs from re-serialisation)")
    return problems


def build_manifest(out_dir, *, schema_version, build=None, commit=None):
    """Index of the per-body files; deterministic for the same files."""
    bodies = []
    total_rows = 0
    for path in _body_files(out_dir):
        rows = _read_body(path)
        dates = [r["date_received"] for r in rows if r.get("date_received")]
        rel = f"{BODIES_RELPATH}/{path.name}"
        bodies.append({
            "public_body_id": rows[0]["public_body_id"],
            "name": rows[0]["name"],
            "path": rel,
            "url": f"{SITE_URL}/{rel}",
            "row_count": len(rows),
            "date_received_min": min(dates) if dates else None,
            "date_received_max": max(dates) if dates else None,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
        total_rows += len(rows)
    bodies.sort(key=lambda b: b["public_body_id"])
    return {
        "schema_version": schema_version,
        "build": build,
        "commit": commit,
        "total_rows": total_rows,
        "total_bodies": len(bodies),
        "bodies": bodies,
    }
