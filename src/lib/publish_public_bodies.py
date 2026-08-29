"""Build and publish the Public Bodies catalog dataset (JSON-LD + CSV).

Moved out of scripts/transform_public_bodies.py so the FOI pipeline's
export_status step can regenerate the catalog on every run, instead of relying
on a manually-invoked standalone script that goes stale. The module owns the
same output contract as the former script: writes public/v2.0.0/public-bodies/
(CSV + JSON-LD), copies it to public/latest/public-bodies/, and stamps
dct:modified in public/catalog/dataset-public-bodies.ttl via
stamp_if_changed() (only when content actually changes).

publish_public_bodies() is the entry point called by export_status. It takes
the freshly-merged bodies (the same records export_status writes to
public/pipeline-data.json) so it never re-reads a possibly-stale file.
"""
import json
import os
import shutil
from pathlib import Path

from .body_refs import BASE_URI, build_body_slug_lookup, body_uri
from .dataset_publish import render_csv, render_jsonld, stamp_if_changed

FIND_PUBLIC_BODIES_PATH = "pipelines/foi_pipeline/steps/find_public_bodies/output.json"
INCLUSIONS_PATH = "pipelines/foi_pipeline/steps/find_public_bodies_subject_to_foi/inclusions.json"
SLUG_SEED_PATH = "pipelines/foi_pipeline/steps/db_upload/slug_seed.json"
CSO_PATH = "pipelines/cso_pipeline/steps/resolve_website_urls/output.json"
OUTPUT_DIR = "public/v2.0.0/public-bodies"
LATEST_DIR = "public/latest/public-bodies"
JSONLD_OUTPUT_PATH = f"{OUTPUT_DIR}/public-bodies.jsonld"
CSV_OUTPUT_PATH = f"{OUTPUT_DIR}/public-bodies.csv"
TTL_PATH = "public/catalog/dataset-public-bodies.ttl"

BODY_TYPE_MAP = {
    "government department": "department",
    "local authority": "local_authority",
    "public body": "public_body",
}


def map_body_type(category):
    """Map a raw pipeline category to a body-type vocabulary notation.

    Raises ValueError for unrecognized categories rather than guessing —
    an unbacked type would be a fabricated value.
    """
    try:
        return BODY_TYPE_MAP[category]
    except KeyError:
        raise ValueError(f"Unrecognized public body category: {category!r}")


def build_contact_email_lookup(pipeline_data_bodies):
    """Map public_body_id -> email for bodies with a successfully crawled FOI email.

    find_public_bodies/output.json never has real crawl results (always
    "not_attempted"); only pipeline-data.json's crawled records do.
    """
    lookup = {}
    for body in pipeline_data_bodies:
        foi_email = body.get("status", {}).get("foi_email", {})
        if foi_email.get("status") == "success" and foi_email.get("email"):
            lookup[body["public_body_id"]] = foi_email["email"]
    return lookup


CSO_FIELDS = [
    "parent_id", "parent_name", "sector", "legal_status",
    "government_department_id", "government_department",
    "nace_code", "nace_section", "nace_section_name", "nace_division",
    "nace_group", "nace_class", "nace_class_name",
    "cro", "data_vintage", "is_commercial", "is_financial",
    "aegis", "legal_entity_type",
]


def build_cso_lookup(cso_records):
    """public_body_id -> dict of whitelisted CSO fields only. Deliberately
    excludes internal CSO-pipeline fields (llm_*, apify_*,
    description_for_sub_sector, official_website_url) that are not part of
    the published catalog schema."""
    lookup = {}
    for r in cso_records:
        lookup[r["public_body_id"]] = {field: r.get(field) for field in CSO_FIELDS}
    return lookup


def build_crawl_status_lookup(pipeline_bodies):
    """public_body_id -> raw status dict, for the bodies present in
    pipeline_bodies. Bodies absent from pipeline_bodies simply have no
    key here -- callers must treat a missing key as "no crawl data at all",
    not as empty/default crawl-status objects."""
    lookup = {}
    for body in pipeline_bodies:
        lookup[body["public_body_id"]] = body.get("status", {})
    return lookup


def build_status_object(raw, value_field):
    """Build a {value_field, status[, verified]} object from a raw crawl
    status dict, e.g. {"url": ..., "status": ..., "verified": ...} for
    website_url/foi_page/disclosures_page, or {"email": ..., "status": ...}
    for foi_email. Returns None if raw itself is missing (body was never
    crawled at all). Omits value_field if its value is null (crawl attempted
    but found nothing); omits "verified" unless the source actually has it
    (never fabricates verified: false)."""
    if raw is None:
        return None
    obj = {}
    value = raw.get(value_field)
    if value is not None:
        obj[value_field] = value
    obj["status"] = raw.get("status")
    if "verified" in raw:
        obj["verified"] = raw["verified"]
    return obj


def build_disclosure_files_object(raw):
    """total/valid/failed are always present ints when raw is present (no
    per-leaf null-omission needed), only the whole object is omitted when
    raw itself is missing."""
    if raw is None:
        return None
    return {
        "total": raw.get("total"),
        "valid": raw.get("valid"),
        "failed": raw.get("failed"),
        "status": raw.get("status"),
    }


def build_foi_requests_object(raw):
    if raw is None:
        return None
    return {
        "valid": raw.get("valid"),
        "errors": raw.get("errors"),
        "status": raw.get("status"),
    }


CSO_SCALAR_FIELDS = [
    "parent_name", "sector", "legal_status", "government_department",
    "nace_code", "nace_section", "nace_section_name", "nace_division",
    "nace_group", "nace_class", "nace_class_name", "cro", "data_vintage",
    "is_commercial", "is_financial", "aegis", "legal_entity_type",
]


def build_record(body, foi_subject_ids, contact_email_lookup, slug_lookup, cso_lookup, crawl_status_lookup, warnings=None):
    """Build one public body record in the corrected Slice 1 data model."""
    if warnings is None:
        warnings = []
    body_id = body["public_body_id"]
    slug = slug_lookup[body_id]
    foi_subject = body_id in foi_subject_ids
    record = {
        "@id": body_uri(slug),
        "@type": "foi:PublicBody",
        "name": body["name"],
        "type": map_body_type(body["category"]),
        "foi_subject": foi_subject,
        "foi_scope": f"{BASE_URI}/ns/foi#FullScope" if foi_subject else f"{BASE_URI}/ns/foi#NoScope",
        "slug": slug,
    }
    if body.get("official_website_url"):
        record["website"] = body["official_website_url"]
    email = contact_email_lookup.get(body_id)
    if email:
        record["contact_email"] = email

    cso = cso_lookup.get(body_id, {})
    for field in CSO_SCALAR_FIELDS:
        value = cso.get(field)
        if value is not None:
            record[field] = value

    for ref_field in ("parent_id", "government_department_id"):
        ref_id = cso.get(ref_field)
        if ref_id is not None:
            ref_slug = slug_lookup.get(ref_id)
            if ref_slug is not None:
                record[ref_field] = body_uri(ref_slug)
            else:
                warnings.append((body_id, ref_field, ref_id))

    crawl_status = crawl_status_lookup.get(body_id, {})
    website_url_obj = build_status_object(crawl_status.get("website_url"), "url")
    if website_url_obj is not None:
        record["website_url"] = website_url_obj
    foi_page_obj = build_status_object(crawl_status.get("foi_page"), "url")
    if foi_page_obj is not None:
        record["foi_page"] = foi_page_obj
    foi_email_obj = build_status_object(crawl_status.get("foi_email"), "email")
    if foi_email_obj is not None:
        record["foi_email"] = foi_email_obj
    disclosures_page_obj = build_status_object(crawl_status.get("disclosures_page"), "url")
    if disclosures_page_obj is not None:
        record["disclosures_page"] = disclosures_page_obj
    disclosure_files_obj = build_disclosure_files_object(crawl_status.get("disclosure_files"))
    if disclosure_files_obj is not None:
        record["disclosure_files"] = disclosure_files_obj
    foi_requests_obj = build_foi_requests_object(crawl_status.get("foi_requests"))
    if foi_requests_obj is not None:
        record["foi_requests"] = foi_requests_obj

    return record


def transform_to_jsonld(records):
    """Wrap records in a single top-level @context + @graph document."""
    return {
        "@context": {
            "@vocab": "https://schema.org/",
            "foi": f"{BASE_URI}/ns/foi#",
            "dct": "http://purl.org/dc/terms/",
        },
        "@graph": records,
    }


CSV_FIELDNAMES = [
    "id", "name", "type", "website", "foi_subject", "foi_scope", "contact_email",
    "slug", "parent_id", "parent_name", "government_department_id", "government_department",
    "sector", "legal_status",
    "nace_code", "nace_section", "nace_section_name", "nace_division", "nace_group",
    "nace_class", "nace_class_name", "cro", "data_vintage", "is_commercial",
    "is_financial", "aegis", "legal_entity_type",
    "website_url_url", "website_url_status", "website_url_verified",
    "foi_page_url", "foi_page_status", "foi_page_verified",
    "foi_email_email", "foi_email_status", "foi_email_verified",
    "disclosures_page_url", "disclosures_page_status", "disclosures_page_verified",
    "disclosure_files_total", "disclosure_files_valid", "disclosure_files_failed", "disclosure_files_status",
    "foi_requests_valid", "foi_requests_errors", "foi_requests_status",
]


def _csv_bool(value):
    if value is None:
        return ""
    return "true" if value else "false"


def _csv_scalar(value):
    if value is None:
        return ""
    return str(value)


def _csv_status_field(record, obj_key, value_field):
    obj = record.get(obj_key, {})
    return {
        f"{obj_key}_{value_field}": _csv_scalar(obj.get(value_field)),
        f"{obj_key}_status": _csv_scalar(obj.get("status")),
        f"{obj_key}_verified": _csv_bool(obj.get("verified")) if "verified" in obj else "",
    }


def transform_to_csv_rows(records):
    """Flatten records into CSV rows. Booleans use lowercase xsd:boolean lexical form."""
    fieldnames = CSV_FIELDNAMES
    rows = []
    for r in records:
        row = {
            "id": r["@id"],
            "name": r["name"],
            "type": r["type"],
            "website": r.get("website", ""),
            "foi_subject": "true" if r["foi_subject"] else "false",
            "foi_scope": r["foi_scope"],
            "contact_email": r.get("contact_email", ""),
            "slug": r["slug"],
            "parent_id": r.get("parent_id", ""),
            "parent_name": _csv_scalar(r.get("parent_name")),
            "government_department_id": r.get("government_department_id", ""),
            "government_department": _csv_scalar(r.get("government_department")),
            "sector": _csv_scalar(r.get("sector")),
            "legal_status": _csv_scalar(r.get("legal_status")),
            "nace_code": _csv_scalar(r.get("nace_code")),
            "nace_section": _csv_scalar(r.get("nace_section")),
            "nace_section_name": _csv_scalar(r.get("nace_section_name")),
            "nace_division": _csv_scalar(r.get("nace_division")),
            "nace_group": _csv_scalar(r.get("nace_group")),
            "nace_class": _csv_scalar(r.get("nace_class")),
            "nace_class_name": _csv_scalar(r.get("nace_class_name")),
            "cro": _csv_scalar(r.get("cro")),
            "data_vintage": _csv_scalar(r.get("data_vintage")),
            "is_commercial": _csv_bool(r.get("is_commercial")) if "is_commercial" in r else "",
            "is_financial": _csv_bool(r.get("is_financial")) if "is_financial" in r else "",
            "aegis": _csv_scalar(r.get("aegis")),
            "legal_entity_type": _csv_scalar(r.get("legal_entity_type")),
        }
        row.update(_csv_status_field(r, "website_url", "url"))
        row.update(_csv_status_field(r, "foi_page", "url"))
        row.update(_csv_status_field(r, "foi_email", "email"))
        row.update(_csv_status_field(r, "disclosures_page", "url"))
        disclosure_files = r.get("disclosure_files", {})
        row["disclosure_files_total"] = _csv_scalar(disclosure_files.get("total"))
        row["disclosure_files_valid"] = _csv_scalar(disclosure_files.get("valid"))
        row["disclosure_files_failed"] = _csv_scalar(disclosure_files.get("failed"))
        row["disclosure_files_status"] = _csv_scalar(disclosure_files.get("status"))
        foi_requests = r.get("foi_requests", {})
        row["foi_requests_valid"] = _csv_scalar(foi_requests.get("valid"))
        row["foi_requests_errors"] = _csv_scalar(foi_requests.get("errors"))
        row["foi_requests_status"] = _csv_scalar(foi_requests.get("status"))
        rows.append(row)
    return fieldnames, rows


def copy_to_latest(versioned_dir, latest_dir):
    """Copy the versioned output directory to latest/ as a build-time snapshot.

    Not a symlink: Codeberg Pages and various git checkout paths don't
    reliably serve/preserve symlinks.
    """
    shutil.copytree(versioned_dir, latest_dir, dirs_exist_ok=True)


def publish(
    jsonld_data, fieldnames, rows,
    jsonld_path=Path(JSONLD_OUTPUT_PATH), csv_path=Path(CSV_OUTPUT_PATH), ttl_path=Path(TTL_PATH),
):
    """Write jsonld/csv and stamp dct:modified only if content changed. Returns True if written.

    Callers should pass repo-root-relative Paths (publish_public_bodies does);
    the cwd-relative defaults exist only to preserve the unit-test contract.
    """
    generated = {
        jsonld_path: render_jsonld(jsonld_data),
        csv_path: render_csv(fieldnames, rows),
    }
    return stamp_if_changed(ttl_path, [jsonld_path, csv_path], generated)


def publish_public_bodies(repo_root, merged_bodies):
    """Regenerate the Public Bodies catalog from the freshly-merged pipeline
    bodies. Call this from export_status after writing public/pipeline-data.json.

    repo_root: repository root Path (all inputs/outputs resolve from here, so
    the step's result doesn't depend on the process cwd).

    merged_bodies: the same per-body records export_status just merged (with
    "public_body_id", "status", and "public_body_name"/"public_body_url"/
    "public_body_category"), i.e. what export_status writes to
    public/pipeline-data.json. Passing them in-memory guarantees the catalog
    is built from the same data being published, never a stale on-disk copy.

    Returns True if the catalog content changed and dct:modified was stamped.
    """
    repo_root = Path(repo_root)
    output_dir = repo_root / OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(repo_root / FIND_PUBLIC_BODIES_PATH) as f:
        bodies = json.load(f)["public_bodies"]
    with open(repo_root / INCLUSIONS_PATH) as f:
        foi_subject_ids = set(json.load(f))
    with open(repo_root / SLUG_SEED_PATH) as f:
        raw_slug_seed = json.load(f)
    slug_seed = {int(k): v for k, v in raw_slug_seed.items()}
    slug_lookup = build_body_slug_lookup(bodies, slug_seed)
    contact_email_lookup = build_contact_email_lookup(merged_bodies)
    with open(repo_root / CSO_PATH) as f:
        cso_records = json.load(f)["results"]
    cso_lookup = build_cso_lookup(cso_records)
    crawl_status_lookup = build_crawl_status_lookup(merged_bodies)

    warnings = []
    records = [
        build_record(b, foi_subject_ids, contact_email_lookup, slug_lookup, cso_lookup, crawl_status_lookup, warnings)
        for b in bodies
    ]
    jsonld_data = transform_to_jsonld(records)
    fieldnames, rows = transform_to_csv_rows(records)

    changed = publish(
        jsonld_data, fieldnames, rows,
        jsonld_path=repo_root / JSONLD_OUTPUT_PATH,
        csv_path=repo_root / CSV_OUTPUT_PATH,
        ttl_path=repo_root / TTL_PATH,
    )
    if changed:
        copy_to_latest(output_dir, repo_root / LATEST_DIR)
        print(f"Transformed {len(records)} public bodies to JSON-LD and CSV (content changed, dct:modified updated)")
    else:
        print(f"Transformed {len(records)} public bodies to JSON-LD and CSV (no content change, dct:modified untouched)")
    if warnings:
        print(f"WARNING: {len(warnings)} unmatched URI-reference field(s) omitted:")
        for body_id, ref_field, ref_id in warnings:
            print(f"  public_body_id {body_id}: {ref_field}={ref_id} has no matching body")
    else:
        print("No unmatched parent_id/government_department_id references.")
    return changed