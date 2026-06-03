import argparse
from pathlib import Path

from lib.file_utils import read_json

_ARRAY_KEYS = ("results", "public_bodies")


def filter_by_public_body(data: dict, public_body_id):
    """Return a shallow copy of `data` with its record array filtered to
    public_body_id. Handles both 'results' and 'public_bodies' keys. If
    public_body_id is None, returns `data` unchanged (same object). Other
    top-level keys (e.g. metadata) are preserved. Does not mutate `data`."""
    if public_body_id is None:
        return data
    out = dict(data)
    for key in _ARRAY_KEYS:
        if key in out:
            out[key] = [r for r in out[key] if r.get("public_body_id") == public_body_id]
    return out


def add_common_args(parser: argparse.ArgumentParser) -> None:
    """Add --input, --output, --force, --verbose, --public-body to a step parser.
    Steps with extra args add them after calling this."""
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--public-body", type=int, default=None, dest="public_body",
                        help="Scope processing to this public body ID only")


def validate_public_body(pipeline_dir: Path, public_body_id: int) -> bool:
    """True if public_body_id is present in find_public_bodies/output.json
    (under the 'public_bodies' key). False if the file is missing or the
    body is absent."""
    bodies_path = Path(pipeline_dir) / "steps" / "find_public_bodies" / "output.json"
    if not bodies_path.exists():
        return False
    bodies = read_json(bodies_path).get("public_bodies", [])
    return any(b.get("public_body_id") == public_body_id for b in bodies)


def merge_replacing_body(existing: list, new: list, public_body_id: int) -> list:
    """Return `existing` with all records for public_body_id removed, then
    `new` appended. Preserves every other body exactly. Used by §(b)
    stateless transforms to honour the no-effect guarantee."""
    kept = [r for r in existing if r.get("public_body_id") != public_body_id]
    return kept + new
