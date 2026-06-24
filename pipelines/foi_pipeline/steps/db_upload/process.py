#!/usr/bin/env python3
import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib.body_utils import derive_category
from lib.cli_utils import add_common_args
from lib.db_client import DbClient
from lib.file_utils import read_json, write_json, write_status

STEP_NAME = "db_upload"

_INSERT_PUBLIC_BODY = """
INSERT OR REPLACE INTO public_bodies (
  public_body_id, public_body_name, public_body_url, public_body_category,
  website_url, website_url_status, website_url_verified,
  foi_page_url, foi_page_status, foi_page_verified,
  foi_email, foi_email_status, foi_email_verified,
  disclosures_page_url, disclosures_page_status, disclosures_page_verified,
  disclosure_files_total, disclosure_files_valid, disclosure_files_failed, disclosure_files_status,
  foi_requests_valid, foi_requests_errors, foi_requests_status,
  pipeline_step, pipeline_completed_at,
  parent_id, parent_name, sector, legal_status,
  government_department, government_department_id,
  nace_code, cro, data_vintage,
  is_commercial, is_financial, aegis, legal_entity_type,
  nace_section, nace_division, nace_group, nace_class,
  nace_section_name, nace_class_name,
  subject_to_foi
) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
"""

_INSERT_CSO_BODY = """
INSERT INTO public_bodies (
  public_body_id, public_body_name, public_body_url, public_body_category,
  website_url, website_url_status, website_url_verified,
  foi_page_url, foi_page_status, foi_page_verified,
  foi_email, foi_email_status, foi_email_verified,
  disclosures_page_url, disclosures_page_status, disclosures_page_verified,
  disclosure_files_total, disclosure_files_valid, disclosure_files_failed, disclosure_files_status,
  foi_requests_valid, foi_requests_errors, foi_requests_status,
  pipeline_step, pipeline_completed_at,
  parent_id, parent_name, sector, legal_status,
  government_department, government_department_id,
  nace_code, cro, data_vintage,
  is_commercial, is_financial, aegis, legal_entity_type,
  nace_section, nace_division, nace_group, nace_class,
  nace_section_name, nace_class_name,
  subject_to_foi
) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
"""

_INSERT_DISCLOSURE_FILE = """
INSERT INTO disclosure_files (public_body_id, document_url, source_page_url, file_type, date_added)
VALUES (?,?,?,?,?)
"""

_INSERT_FOI_DISCLOSURE = """
INSERT INTO foi_disclosures (
  public_body_id, name, file_url, file_type,
  foi_reference_id, decision_date, date_received, requester_type,
  decision_status, review_status, related_request, request_description
) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
"""

_INSERT_TOPIC = "INSERT INTO topics (slug, label, match_count) VALUES (?,?,?)"
_INSERT_KEYWORD = "INSERT INTO topic_keywords (topic_slug, keyword) VALUES (?,?)"
_INSERT_TOPIC_DISCLOSURE = "INSERT INTO topic_disclosures (topic_slug, foi_disclosure_id) VALUES (?,?)"


def apply_schema_migrations(db):
    """Apply incremental schema changes that CREATE TABLE IF NOT EXISTS cannot handle."""
    migrations = [
        "ALTER TABLE foi_disclosures ADD COLUMN date_received TEXT",
        "ALTER TABLE public_bodies ADD COLUMN parent_id INTEGER",
        "ALTER TABLE public_bodies ADD COLUMN parent_name TEXT",
        "ALTER TABLE public_bodies ADD COLUMN sector TEXT",
        "ALTER TABLE public_bodies ADD COLUMN legal_status TEXT",
        "ALTER TABLE public_bodies ADD COLUMN government_department TEXT",
        "ALTER TABLE public_bodies ADD COLUMN government_department_id INTEGER",
        "ALTER TABLE public_bodies ADD COLUMN nace_code TEXT",
        "ALTER TABLE public_bodies ADD COLUMN cro TEXT",
        "ALTER TABLE public_bodies ADD COLUMN data_vintage INTEGER",
        "ALTER TABLE public_bodies ADD COLUMN is_commercial     INTEGER",
        "ALTER TABLE public_bodies ADD COLUMN is_financial      INTEGER",
        "ALTER TABLE public_bodies ADD COLUMN aegis             TEXT",
        "ALTER TABLE public_bodies ADD COLUMN legal_entity_type TEXT",
        "ALTER TABLE public_bodies ADD COLUMN nace_section      TEXT",
        "ALTER TABLE public_bodies ADD COLUMN nace_division     TEXT",
        "ALTER TABLE public_bodies ADD COLUMN nace_group        TEXT",
        "ALTER TABLE public_bodies ADD COLUMN nace_class        TEXT",
        "ALTER TABLE public_bodies ADD COLUMN nace_section_name TEXT",
        "ALTER TABLE public_bodies ADD COLUMN nace_class_name   TEXT",
        "ALTER TABLE public_bodies ADD COLUMN subject_to_foi    INTEGER DEFAULT 0",
    ]
    for sql in migrations:
        try:
            db.execute(sql)
        except Exception as e:
            msg = str(e).lower()
            if "duplicate column" not in msg and "already exists" not in msg:
                raise


def clear_pipeline_tables(db):
    """Delete pipeline data in dependency order; leaves corrections/outreach tables untouched."""
    tables = ["topic_disclosures", "topic_keywords", "topics",
              "foi_disclosures", "disclosure_files", "public_bodies"]
    db.execute_batch([(f"DELETE FROM {table}", []) for table in tables])


def upload_public_bodies(db, steps_dir, cso_lookup):
    data = read_json(steps_dir / "export_status" / "output.json")
    meta = data["metadata"]
    rows = []
    for body in data["public_bodies"]:
        s = body["status"]
        cso = cso_lookup.get(body["public_body_id"], {})
        rows.append([
            body["public_body_id"],
            body["public_body_name"],
            body.get("public_body_url") or "",
            body["public_body_category"],
            s["website_url"].get("url"),
            s["website_url"].get("status"),
            1 if s["website_url"].get("verified") else 0,
            s["foi_page"].get("url"),
            s["foi_page"].get("status"),
            1 if s["foi_page"].get("verified") else 0,
            s["foi_email"].get("email"),
            s["foi_email"].get("status"),
            1 if s["foi_email"].get("verified") else 0,
            s["disclosures_page"].get("url"),
            s["disclosures_page"].get("status"),
            1 if s["disclosures_page"].get("verified") else 0,
            s["disclosure_files"].get("total", 0),
            s["disclosure_files"].get("valid", 0),
            s["disclosure_files"].get("failed", 0),
            s["disclosure_files"].get("status"),
            s["foi_requests"].get("valid", 0),
            s["foi_requests"].get("errors", 0),
            s["foi_requests"].get("status"),
            meta.get("step"),
            meta.get("completed_at"),
            cso.get("parent_id"),
            cso.get("parent_name"),
            cso.get("sector"),
            cso.get("legal_status"),
            cso.get("government_department"),
            cso.get("government_department_id"),
            cso.get("nace_code"),
            cso.get("cro"),
            cso.get("data_vintage"),
            1 if cso.get("is_commercial") is True else (0 if cso.get("is_commercial") is False else None),
            1 if cso.get("is_financial") is True else (0 if cso.get("is_financial") is False else None),
            cso.get("aegis"),
            cso.get("legal_entity_type"),
            cso.get("nace_section"),
            cso.get("nace_division"),
            cso.get("nace_group"),
            cso.get("nace_class"),
            cso.get("nace_section_name"),
            cso.get("nace_class_name"),
            1,
        ])
    db.executemany(_INSERT_PUBLIC_BODY, rows)
    return len(rows)


def upload_cso_bodies(db, cso_path):
    data = read_json(cso_path)
    bodies = data.get("results") or data.get("public_bodies", [])
    rows = []
    for body in bodies:
        rows.append([
            body["public_body_id"],
            body["name"],
            "",
            derive_category(body),
            body.get("official_website_url"),
            "not_attempted", 0,
            None, "not_attempted", 0,
            None, "not_attempted", 0,
            None, "not_attempted", 0,
            0, 0, 0, "not_attempted",
            0, 0, "not_attempted",
            None, None,
            body.get("parent_id"),
            body.get("parent_name"),
            body.get("sector"),
            body.get("legal_status"),
            body.get("government_department"),
            body.get("government_department_id"),
            body.get("nace_code"),
            body.get("cro"),
            body.get("data_vintage"),
            1 if body.get("is_commercial") is True else (0 if body.get("is_commercial") is False else None),
            1 if body.get("is_financial") is True else (0 if body.get("is_financial") is False else None),
            body.get("aegis"),
            body.get("legal_entity_type"),
            body.get("nace_section"),
            body.get("nace_division"),
            body.get("nace_group"),
            body.get("nace_class"),
            body.get("nace_section_name"),
            body.get("nace_class_name"),
            0,
        ])
    db.executemany(_INSERT_CSO_BODY, rows)
    return len(rows)


def upload_disclosure_files(db, steps_dir):
    data = read_json(steps_dir / "find_disclosure_files" / "output.json")
    rows = [
        [r["public_body_id"], r["file_url"], r["disclosure_page_url"], r["file_type"], r.get("date_added")]
        for r in data["results"]
    ]
    db.executemany(_INSERT_DISCLOSURE_FILE, rows)
    return len(rows)


def upload_foi_disclosures(db, steps_dir):
    """Returns (count, {(public_body_id, file_url, foi_reference_id): db_id}) for topic linking."""
    data = read_json(steps_dir / "extract_disclosures_deduplicate" / "output.json")
    rows = [
        [
            r["public_body_id"], r["name"], r["file_url"], r["file_type"],
            r.get("foi_reference_id"), r.get("decision_date"), r.get("date_received"),
            r.get("requester_type"), r.get("decision_status"), r.get("review_status"),
            r.get("related_request"), r.get("request_description"),
        ]
        for r in data["results"]
    ]
    max_before = db.execute("SELECT COALESCE(MAX(id), 0) AS m FROM foi_disclosures")[0]["m"]
    db.executemany(_INSERT_FOI_DISCLOSURE, rows)
    id_rows = db.execute(
        "SELECT id, public_body_id, file_url, foi_reference_id FROM foi_disclosures WHERE id > ?",
        [max_before],
    )
    id_map = {(r["public_body_id"], r["file_url"], r["foi_reference_id"]): r["id"] for r in id_rows}
    return len(rows), id_map


def upload_topics(db, steps_dir, disclosure_id_map):
    data = read_json(steps_dir / "generate_topics" / "output.json")
    topics = data["results"]

    db.executemany(_INSERT_TOPIC, [[t["slug"], t["label"], t["match_count"]] for t in topics])

    kw_rows = [[t["slug"], kw] for t in topics for kw in t["keywords"]]
    db.executemany(_INSERT_KEYWORD, kw_rows)

    td_seen = set()
    td_rows = []
    for t in topics:
        for d in t["disclosures"]:
            disc_id = disclosure_id_map.get((d["public_body_id"], d["file_url"], d.get("foi_reference_id")))
            if disc_id is not None:
                pair = (t["slug"], disc_id)
                if pair not in td_seen:
                    td_seen.add(pair)
                    td_rows.append(list(pair))
    db.executemany(_INSERT_TOPIC_DISCLOSURE, td_rows)

    return len(topics)


def main():
    parser = argparse.ArgumentParser(description="Upload pipeline data to libSQL database")
    add_common_args(parser)
    parser.add_argument(
        "--cso-input", dest="cso_input", default=None,
        help="Path to CSO resolve_website_urls/output.json (defaults to repo-relative path)",
    )
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)

    if args.public_body is not None:
        print("--public-body scoped db_upload skipped: upsert is not idempotent; run a full upload.",
              file=sys.stderr)
        sys.exit(0)

    if not args.force and output_path.exists():
        print(f"Output exists at {output_path}, skipping (use --force to re-run)")
        sys.exit(0)

    steps_dir = step_dir.parent
    pipeline_dir = steps_dir.parent
    pipelines_dir = pipeline_dir.parent
    repo_root = pipelines_dir.parent

    if args.cso_input:
        cso_path = Path(args.cso_input)
    else:
        cso_path = pipelines_dir / "cso_pipeline" / "steps" / "resolve_website_urls" / "output.json"

    db_url = os.getenv("DATABASE_URL", str(repo_root / "local.db"))
    db_token = os.getenv("DATABASE_AUTH_TOKEN", "")

    db = DbClient(db_url, db_token)
    try:
        schema_sql = (repo_root / "public" / "schema.sql").read_text(encoding="utf-8")
        db.executescript(schema_sql)
        apply_schema_migrations(db)
        clear_pipeline_tables(db)

        n_cso = upload_cso_bodies(db, cso_path)
        cso_data = read_json(cso_path)
        cso_lookup = {b["public_body_id"]: b for b in (cso_data.get("results") or cso_data.get("public_bodies", []))}
        n_bodies = upload_public_bodies(db, steps_dir, cso_lookup)
        n_files = upload_disclosure_files(db, steps_dir)
        n_disclosures, disclosure_id_map = upload_foi_disclosures(db, steps_dir)
        n_topics = upload_topics(db, steps_dir, disclosure_id_map)
    finally:
        db.close()

    counts = {
        "cso_bodies": n_cso,
        "foi_bodies": n_bodies,
        "disclosure_files": n_files,
        "foi_disclosures": n_disclosures,
        "topics": n_topics,
    }
    write_json(output_path, {
        "metadata": {
            "step": STEP_NAME,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
        "counts": counts,
    })
    write_status(step_dir, n_cso)

    print(f"Uploaded to {db_url}:")
    for k, v in counts.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
