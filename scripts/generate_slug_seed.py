#!/usr/bin/env python3
"""One-off: freeze publicinformation-web's published slug registry as this
repo's permanence seed fixture.

publicinformation-web has already computed and published the current,
correct, production slug for every existing public body
(https://publicinformation.ie/api/bodies.json). This repo must not
recompute those slugs — it seeds them once, here, and from then on
db_upload/process.py writes the seeded value verbatim for every id present
in the fixture (see
docs/superpowers/plans/2026-07-07-public-bodies-slug-column.md).

Run ONCE, now, to produce the initial slug_seed.json (already done and
committed if this file exists with content). Re-run only to add newly
onboarded bodies that are missing from the fixture -- never to "refresh"
a slug that is already seeded; that would violate slug permanence.

Usage:
    PYTHONPATH=src python3 scripts/generate_slug_seed.py
    PYTHONPATH=src python3 scripts/generate_slug_seed.py --url https://publicinformation.ie/api/bodies.json
    PYTHONPATH=src python3 scripts/generate_slug_seed.py --input path/to/bodies.json
"""
import argparse
import json
from pathlib import Path

import requests

from lib.file_utils import write_json

DEFAULT_URL = "https://publicinformation.ie/api/bodies.json"
REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = (
    REPO_ROOT / "pipelines" / "foi_pipeline" / "steps" / "db_upload" / "slug_seed.json"
)


def fetch_bodies(url=None, input_path=None):
    if input_path:
        data = json.loads(Path(input_path).read_text(encoding="utf-8"))
    else:
        resp = requests.get(url or DEFAULT_URL, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    return data["bodies"]


def build_seed(bodies):
    seed = {}
    for body in bodies:
        body_id = body["id"]
        slug = body.get("slug")
        if not slug:
            raise ValueError(f"Body {body_id} ({body.get('name')}) has an empty slug in source data")
        seed[str(body_id)] = slug
    return dict(sorted(seed.items(), key=lambda kv: int(kv[0])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=None, help=f"Slug registry URL (default: {DEFAULT_URL})")
    parser.add_argument("--input", default=None, help="Local bodies.json file instead of fetching a URL")
    parser.add_argument("--output", default=None, help=f"Output path (default: {OUTPUT_PATH})")
    args = parser.parse_args()

    bodies = fetch_bodies(url=args.url, input_path=args.input)
    seed = build_seed(bodies)

    output_path = Path(args.output) if args.output else OUTPUT_PATH
    write_json(output_path, seed)
    print(f"Wrote {len(seed)} id->slug entries to {output_path}")


if __name__ == "__main__":
    main()
