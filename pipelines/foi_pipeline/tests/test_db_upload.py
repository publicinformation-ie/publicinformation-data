import json
import pytest
from pathlib import Path
from lib.db_client import DbClient

# Find repo root (location-independent — works before and after directory move)
_HERE = Path(__file__).parent
_REPO_ROOT = _HERE
_prev = None
while not (_REPO_ROOT / ".git").exists():
    if _prev == _REPO_ROOT:
        raise RuntimeError(f"Could not find .git root starting from {_HERE}")
    _prev = _REPO_ROOT
    _REPO_ROOT = _REPO_ROOT.parent
REPO_ROOT = _REPO_ROOT

# --- helpers ---

def make_body(public_body_id=1):
    return {
        "public_body_id": public_body_id,
        "public_body_name": f"Body {public_body_id}",
        "public_body_url": f"https://body{public_body_id}.ie",
        "public_body_category": "Government Department",
        "status": {
            "website_url": {"url": f"https://body{public_body_id}.ie", "status": "success", "verified": False},
            "foi_page": {"url": f"https://body{public_body_id}.ie/foi", "status": "success", "verified": True},
            "foi_email": {"email": f"foi@body{public_body_id}.ie", "status": "success", "verified": False},
            "disclosures_page": {"url": None, "status": "failed", "verified": False},
            "disclosure_files": {"total": 2, "valid": 2, "failed": 0, "status": "success"},
            "foi_requests": {"valid": 5, "errors": 0, "status": "success"},
        },
    }


def make_export_status(bodies=None):
    bodies = bodies or [make_body(1)]
    return {
        "metadata": {"step": "export_status", "completed_at": "2026-05-27T10:00:00+00:00"},
        "public_bodies": bodies,
    }


def make_disclosure_files(public_body_id=1, count=2):
    return {
        "results": [
            {
                "public_body_id": public_body_id,
                "name": f"disclosure page {i}",
                "disclosure_page_url": f"https://body{public_body_id}.ie/disclosures",
                "file_url": f"https://body{public_body_id}.ie/doc{i}.pdf",
                "file_type": "pdf",
            }
            for i in range(count)
        ]
    }


def make_foi_disclosures(public_body_id=1, count=2):
    return {
        "results": [
            {
                "public_body_id": public_body_id,
                "name": f"FOI Request {i}",
                "file_url": f"https://body{public_body_id}.ie/foi{i}.pdf",
                "file_type": "pdf",
                "foi_reference_id": f"REF-{i}",
                "decision_date": f"2026-01-0{i+1}",
                "requester_type": "journalist",
                "decision_status": "granted",
                "review_status": None,
                "related_request": None,
                "request_description": f"Request about topic {i}",
            }
            for i in range(count)
        ]
    }


def make_topics(disclosures_data):
    disclosures = disclosures_data["results"]
    return {
        "metadata": {"step": "generate_topics", "completed_at": "2026-05-27T10:01:00+00:00"},
        "results": [
            {
                "slug": "housing",
                "label": "Housing",
                "keywords": ["housing", "accommodation"],
                "match_count": len(disclosures),
                "disclosures": disclosures,
            }
        ],
    }


@pytest.fixture
def steps_dir(tmp_path):
    """Create a minimal fake steps directory tree."""
    disclosures = make_foi_disclosures(public_body_id=1, count=2)
    step_data = {
        "export_status": make_export_status([make_body(1)]),
        "find_disclosure_files": make_disclosure_files(public_body_id=1, count=2),
        "extract_disclosures_canonicalize": disclosures,
        "extract_disclosures_deduplicate": disclosures,
        "generate_topics": make_topics(disclosures),
    }
    for step_name, data in step_data.items():
        step_dir = tmp_path / step_name
        step_dir.mkdir()
        (step_dir / "output.json").write_text(json.dumps(data), encoding="utf-8")
    return tmp_path


@pytest.fixture
def db():
    schema_sql = (REPO_ROOT / "public" / "schema.sql").read_text(encoding="utf-8")
    client = DbClient(":memory:")
    client.executescript(schema_sql)
    yield client
    client.close()


# Import upload functions after fixtures are defined
from steps.db_upload.process import (
    upload_public_bodies,
    upload_disclosure_files,
    upload_foi_disclosures,
    upload_topics,
    clear_pipeline_tables,
)


class TestClearPipelineTables:
    def test_deletes_all_pipeline_rows(self, db, steps_dir):
        upload_public_bodies(db, steps_dir)
        upload_disclosure_files(db, steps_dir)
        _, id_map = upload_foi_disclosures(db, steps_dir)
        upload_topics(db, steps_dir, id_map)

        clear_pipeline_tables(db)

        for table in ["public_bodies", "disclosure_files", "foi_disclosures", "topics", "topic_keywords", "topic_disclosures"]:
            rows = db.execute(f"SELECT count(*) as n FROM {table}")
            assert rows[0]["n"] == 0, f"{table} not cleared"

    def test_does_not_touch_corrections(self, db):
        db.execute(
            "INSERT INTO corrections (correction_id, body_id, body_name, field, suggested_value, submitter_did, submitter_ip, submitted_at) VALUES (?,?,?,?,?,?,?,?)",
            ["c1", 1, "Body", "website_url", "https://new.ie", "did:plc:abc", "1.2.3.4", "2026-05-27T00:00:00Z"],
        )
        clear_pipeline_tables(db)
        rows = db.execute("SELECT count(*) as n FROM corrections")
        assert rows[0]["n"] == 1


class TestUploadPublicBodies:
    def test_inserts_bodies(self, db, steps_dir):
        n = upload_public_bodies(db, steps_dir)
        assert n == 1
        rows = db.execute("SELECT * FROM public_bodies WHERE public_body_id = 1")
        assert len(rows) == 1
        row = rows[0]
        assert row["public_body_name"] == "Body 1"
        assert row["website_url_status"] == "success"
        assert row["foi_page_verified"] == 1
        assert row["disclosures_page_url"] is None
        assert row["disclosure_files_total"] == 2
        assert row["pipeline_step"] == "export_status"

    def test_multiple_bodies(self, db, tmp_path):
        data = make_export_status([make_body(1), make_body(2)])
        (tmp_path / "export_status").mkdir()
        (tmp_path / "export_status" / "output.json").write_text(json.dumps(data))
        n = upload_public_bodies(db, tmp_path)
        assert n == 2


class TestUploadDisclosureFiles:
    def test_inserts_files(self, db, steps_dir):
        db.execute(
            "INSERT INTO public_bodies (public_body_id, public_body_name, public_body_url, public_body_category) VALUES (?,?,?,?)",
            [1, "Body 1", "https://body1.ie", "Government Department"],
        )
        n = upload_disclosure_files(db, steps_dir)
        assert n == 2
        rows = db.execute("SELECT * FROM disclosure_files ORDER BY document_url")
        assert rows[0]["document_url"] == "https://body1.ie/doc0.pdf"
        assert rows[0]["source_page_url"] == "https://body1.ie/disclosures"
        assert rows[0]["date_added"] is None


class TestUploadFoiDisclosures:
    def test_inserts_disclosures(self, db, steps_dir):
        db.execute(
            "INSERT INTO public_bodies (public_body_id, public_body_name, public_body_url, public_body_category) VALUES (?,?,?,?)",
            [1, "Body 1", "https://body1.ie", "Government Department"],
        )
        n, id_map = upload_foi_disclosures(db, steps_dir)
        assert n == 2
        assert len(id_map) == 2
        rows = db.execute("SELECT * FROM foi_disclosures ORDER BY id")
        assert rows[0]["name"] == "FOI Request 0"
        assert rows[0]["foi_reference_id"] == "REF-0"
        assert rows[0]["review_status"] is None

    def test_id_map_keys(self, db, steps_dir):
        db.execute(
            "INSERT INTO public_bodies (public_body_id, public_body_name, public_body_url, public_body_category) VALUES (?,?,?,?)",
            [1, "Body 1", "https://body1.ie", "Government Department"],
        )
        _, id_map = upload_foi_disclosures(db, steps_dir)
        assert (1, "https://body1.ie/foi0.pdf", "REF-0") in id_map
        assert (1, "https://body1.ie/foi1.pdf", "REF-1") in id_map


class TestUploadTopics:
    def test_inserts_topics_and_keywords(self, db, steps_dir):
        db.execute(
            "INSERT INTO public_bodies (public_body_id, public_body_name, public_body_url, public_body_category) VALUES (?,?,?,?)",
            [1, "Body 1", "https://body1.ie", "Government Department"],
        )
        _, id_map = upload_foi_disclosures(db, steps_dir)
        n = upload_topics(db, steps_dir, id_map)
        assert n == 1

        topics = db.execute("SELECT * FROM topics")
        assert topics[0]["slug"] == "housing"
        assert topics[0]["match_count"] == 2

        kws = db.execute("SELECT keyword FROM topic_keywords ORDER BY keyword")
        assert [r["keyword"] for r in kws] == ["accommodation", "housing"]

        tds = db.execute("SELECT * FROM topic_disclosures")
        assert len(tds) == 2

    def test_skips_missing_disclosures(self, db, steps_dir):
        db.execute(
            "INSERT INTO public_bodies (public_body_id, public_body_name, public_body_url, public_body_category) VALUES (?,?,?,?)",
            [1, "Body 1", "https://body1.ie", "Government Department"],
        )
        upload_topics(db, steps_dir, {})  # empty id_map — no topic_disclosures
        tds = db.execute("SELECT * FROM topic_disclosures")
        assert len(tds) == 0


class TestApplySchemaMigrations:
    def test_cso_columns_added_by_migration(self):
        """Verify migrations add the 9 CSO columns to a database with the old schema."""
        from lib.db_client import DbClient
        from steps.db_upload.process import apply_schema_migrations

        old_schema = """
        CREATE TABLE IF NOT EXISTS public_bodies (
          public_body_id INTEGER PRIMARY KEY,
          public_body_name TEXT NOT NULL,
          public_body_url TEXT NOT NULL,
          public_body_category TEXT NOT NULL,
          pipeline_step TEXT,
          pipeline_completed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS foi_disclosures (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          public_body_id INTEGER NOT NULL,
          name TEXT NOT NULL,
          file_url TEXT NOT NULL,
          file_type TEXT NOT NULL
        );
        """
        db = DbClient(":memory:")
        db.executescript(old_schema)
        apply_schema_migrations(db)

        rows = db.execute("PRAGMA table_info(public_bodies)")
        cols = {r["name"] for r in rows}
        for col in ["parent_id", "parent_name", "sector", "legal_status",
                    "government_department", "government_department_id",
                    "nace_code", "cro", "data_vintage"]:
            assert col in cols, f"Missing column: {col}"
        db.close()

    def test_migrations_idempotent(self, db):
        """Running migrations twice must not raise."""
        from steps.db_upload.process import apply_schema_migrations
        apply_schema_migrations(db)  # first call (columns already in schema.sql)
        apply_schema_migrations(db)  # second call — must silently no-op


import sys as _sys
import steps.db_upload.process as _proc


def test_public_body_scoped_skips_and_exits_clean(tmp_path, monkeypatch):
    # db_upload inserts are not idempotent -- scoped run must skip
    out = tmp_path / "output.json"
    monkeypatch.setattr(_proc, "__file__", str(tmp_path / "process.py"))
    _sys.argv = ["process.py", "--input", "unused", "--output", str(out),
                 "--public-body", "1002"]
    with pytest.raises(SystemExit) as exc:
        _proc.main()
    assert exc.value.code == 0  # clean exit (not an error)
    assert not out.exists()  # no output written
