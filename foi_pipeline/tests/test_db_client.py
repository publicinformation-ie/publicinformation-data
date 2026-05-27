import pytest
from pathlib import Path
from scripts.db_client import DbClient

REPO_ROOT = Path(__file__).parent.parent.parent


@pytest.fixture
def schema_sql():
    return (REPO_ROOT / "schema.sql").read_text(encoding="utf-8")


@pytest.fixture
def db():
    client = DbClient(":memory:")
    yield client
    client.close()


@pytest.fixture
def seeded_db(db, schema_sql):
    db.executescript(schema_sql)
    return db


class TestExecute:
    def test_insert_and_select(self, seeded_db):
        seeded_db.execute(
            "INSERT INTO topics (slug, label, match_count) VALUES (?,?,?)",
            ["housing", "Housing", 5],
        )
        rows = seeded_db.execute("SELECT slug, label, match_count FROM topics")
        assert len(rows) == 1
        assert rows[0]["slug"] == "housing"
        assert rows[0]["label"] == "Housing"
        assert rows[0]["match_count"] == 5

    def test_select_returns_empty_list(self, seeded_db):
        rows = seeded_db.execute("SELECT * FROM topics")
        assert rows == []

    def test_none_param(self, seeded_db):
        seeded_db.execute(
            "INSERT INTO public_bodies (public_body_id, public_body_name, public_body_url, public_body_category) VALUES (?,?,?,?)",
            [1, "Test Body", "https://example.ie", "Government Department"],
        )
        seeded_db.execute(
            "INSERT INTO disclosure_files (public_body_id, document_url, source_page_url, file_type, date_added) VALUES (?,?,?,?,?)",
            [1, "https://example.ie/doc.pdf", "https://example.ie/disclosures", "pdf", None],
        )
        rows = seeded_db.execute("SELECT date_added FROM disclosure_files")
        assert rows[0]["date_added"] is None


class TestExecuteMany:
    def test_bulk_insert(self, seeded_db):
        rows = [
            ["housing", "Housing", 3],
            ["transport", "Transport", 7],
        ]
        seeded_db.executemany(
            "INSERT INTO topics (slug, label, match_count) VALUES (?,?,?)",
            rows,
        )
        result = seeded_db.execute("SELECT count(*) as n FROM topics")
        assert result[0]["n"] == 2

    def test_empty_list_is_noop(self, seeded_db):
        seeded_db.executemany(
            "INSERT INTO topics (slug, label, match_count) VALUES (?,?,?)",
            [],
        )
        result = seeded_db.execute("SELECT count(*) as n FROM topics")
        assert result[0]["n"] == 0


class TestExecuteScript:
    def test_creates_tables(self, db, schema_sql):
        db.executescript(schema_sql)
        rows = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        names = [r["name"] for r in rows]
        assert "public_bodies" in names
        assert "foi_disclosures" in names
        assert "topics" in names
        assert "corrections" in names

    def test_idempotent(self, db, schema_sql):
        db.executescript(schema_sql)
        db.executescript(schema_sql)  # should not raise
        rows = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        names = [r["name"] for r in rows]
        assert "public_bodies" in names
        assert "topics" in names


class TestLocalUrl:
    def test_memory_url(self):
        db = DbClient(":memory:")
        db.close()

    def test_file_prefix_stripped(self, tmp_path):
        url = f"file:{tmp_path / 'test.db'}"
        db = DbClient(url)
        db.close()
