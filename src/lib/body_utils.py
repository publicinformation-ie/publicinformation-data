import re
import unicodedata


def derive_category(body):
    if body.get("description_for_sub_sector") == "Local Authorities":
        return "local authority"
    if (body.get("legal_status") == "Vote"
            and body.get("government_department_id") == body.get("public_body_id")):
        return "government department"
    return "public body"


def generate_slug(name):
    """Best-effort slug for a body absent from slug_seed.json. Does not need
    to match publicinformation-web's slugify() -- new bodies without a seed
    are override-correctable there; see
    docs/superpowers/plans/2026-07-07-public-bodies-slug-column.md.
    """
    normalized = unicodedata.normalize("NFKD", name)
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    normalized = normalized.replace("&", " and ").lower()
    return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")


def resolve_slug(public_body_id, name, seed):
    """Look up the permanent seeded slug for a body; only fall back to a
    freshly generated one for ids absent from the seed (bodies onboarded
    after slug_seed.json was frozen). Never recompute a slug for a seeded
    id -- that is the slug-permanence guarantee this repo owes
    publicinformation-web.
    """
    seeded = seed.get(public_body_id)
    if seeded:
        return seeded
    slug = generate_slug(name)
    return slug or f"body-{public_body_id}"
