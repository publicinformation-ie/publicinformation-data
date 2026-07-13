"""Shared helpers for resolving public_body_id -> permanent slug -> @id URI.

Every catalog transform script (transform_public_bodies.py,
transform_foi_request_files.py, transform_who_does_what.py, and future
transform_foi_disclosures.py) should import build_body_slug_lookup() and
body_uri() from here instead of independently re-slugifying names. The
permanent slug source of truth is resolve_slug() in src/lib/body_utils.py
(already used by db_upload) plus slug_seed.json
(pipelines/foi_pipeline/steps/db_upload/slug_seed.json, frozen once
assigned) -- this module never recomputes a slug for an id present in that
seed file.
"""
from src.lib.body_utils import resolve_slug

BASE_URI = "https://data.publicinformation.ie"


def build_body_slug_lookup(pipeline_bodies, slug_seed):
    """Map public_body_id -> permanent slug for a list of body records.

    pipeline_bodies: list of dicts, each with an integer "public_body_id"
    and a display name under either "name" (find_public_bodies/output.json,
    apply_overrides output) or "public_body_name" (public/pipeline-data.json
    and similar). Falls back between the two keys so callers can pass their
    existing records unmodified.

    slug_seed: dict of {public_body_id (int): permanent_slug (str)}, i.e.
    slug_seed.json already loaded and int-keyed the same way db_upload's
    process.py does before calling resolve_slug() -- this function does not
    load or key-convert the file itself.

    Delegates every lookup to resolve_slug(), which guarantees a seeded id
    is never recomputed.
    """
    lookup = {}
    for body in pipeline_bodies:
        body_id = body["public_body_id"]
        name = body.get("name") or body.get("public_body_name")
        lookup[body_id] = resolve_slug(body_id, name, slug_seed)
    return lookup


def body_uri(slug):
    """Build a public body's canonical @id URI from its permanent slug."""
    return f"{BASE_URI}/body/{slug}"
