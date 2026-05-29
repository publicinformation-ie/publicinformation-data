#!/usr/bin/env python3
import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from scripts.db_client import DbClient
from scripts.file_utils import read_json, write_json, write_status

STEP_NAME = "db_upload"

_INSERT_PUBLIC_BODY = """
INSERT INTO public_bodies (
  public_body_id, public_body_name, public_body_url, public_body_category,
  website_url, website_url_status, website_url_verified,
  foi_page_url, foi_page_status, foi_page_verified,
  foi_email, foi_email_status, foi_email_verified,
  disclosures_page_url, disclosures_page_status, disclosures_page_verified,
  disclosure_files_total, disclosure_files_valid, disclosure_files_failed, disclosure_files_status,
  foi_requests_valid, foi_requests_errors, foi_requests_status,
  pipeline_step, pipeline_completed_at
) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
"""

_INSERT_DISCLOSURE_FILE = """
INSERT INTO disclosure_files (public_body_id, document_url, source_page_url, file_type, date_added)
VALUES (?,?,?,?,?)
"""

_INSERT_FOI_DISCLOSURE = """
INSERT INTO foi_disclosures (
  public_body_id, name, file_url, file_type,
  foi_reference_id, decision_date, requester_type,
  decision_status, review_status, related_request, request_description
) VALUES (?,?,?,?,?,?,?,?,?,?,?)
"""

_INSERT_TOPIC = "INSERT INTO topics (slug, label, match_count) VALUES (?,?,?)"
_INSERT_KEYWORD = "INSERT INTO topic_keywords (topic_slug, keyword) VALUES (?,?)"
_INSERT_TOPIC_DISCLOSURE = "INSERT INTO topic_disclosures (topic_slug, foi_disclosure_id) VALUES (?,?)"


def clear_pipeline_tables(db):
    """Delete pipeline data in dependency order; leaves corrections/outreach tables untouched."""
    tables = ["topic_disclosures", "topic_keywords", "topics",
              "foi_disclosures", "disclosure_files", "public_bodies"]
    db.execute_batch([(f"DELETE FROM {table}", []) for table in tables])


def upload_public_bodies(db, steps_dir):
    data = read_json(steps_dir / "export_status" / "output.json")
    meta = data["metadata"]
    rows = []
    for body in data["public_bodies"]:
        s = body["status"]
        rows.append([
            body["public_body_id"],
            body["public_body_name"],
            body["public_body_url"],
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
        ])
    db.executemany(_INSERT_PUBLIC_BODY, rows)
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
            r.get("foi_reference_id"), r.get("decision_date"), r.get("requester_type"),
            r.get("decision_status"), r.get("review_status"), r.get("related_request"),
            r.get("request_description"),
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
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output)

    if not args.force and output_path.exists():
        print(f"Output exists at {output_path}, skipping (use --force to re-run)")
        sys.exit(0)

    steps_dir = step_dir.parent
    pipeline_dir = steps_dir.parent
    repo_root = pipeline_dir.parent

    db_url = os.getenv("DATABASE_URL", str(repo_root / "local.db"))
    db_token = os.getenv("DATABASE_AUTH_TOKEN", "")

    db = DbClient(db_url, db_token)
    try:
        schema_sql = (repo_root / "schema.sql").read_text(encoding="utf-8")
        db.executescript(schema_sql)
        clear_pipeline_tables(db)

        n_bodies = upload_public_bodies(db, steps_dir)
        n_files = upload_disclosure_files(db, steps_dir)
        n_disclosures, disclosure_id_map = upload_foi_disclosures(db, steps_dir)
        n_topics = upload_topics(db, steps_dir, disclosure_id_map)
    finally:
        db.close()

    counts = {
        "public_bodies": n_bodies,
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
    write_status(step_dir, n_bodies)

    print(f"Uploaded to {db_url}:")
    for k, v in counts.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
