import pytest
from pathlib import Path
from unittest.mock import patch, Mock
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


def _ok_result():
    return {"type": "ok", "response": {"type": "execute", "result": {"cols": [], "rows": []}}}


def _pipeline_response(results):
    mock_resp = Mock()
    mock_resp.raise_for_status = Mock()
    mock_resp.json.return_value = {"results": results}
    return mock_resp


@pytest.fixture
def remote_db():
    return DbClient("https://test.example.com", "test-token")


class TestHttpPipeline:
    def test_wraps_statements_in_begin_commit(self, remote_db):
        ok = _ok_result()
        with patch("scripts.db_client.requests.post", return_value=_pipeline_response([ok, ok, ok])) as mock_post:
            remote_db._http_pipeline([("INSERT INTO t VALUES (?)", [42])])

        payload = mock_post.call_args[1]["json"]
        sqls = [r["stmt"]["sql"] for r in payload["requests"]]
        assert sqls == ["BEGIN", "INSERT INTO t VALUES (?)", "COMMIT"]

    def test_passes_args_correctly(self, remote_db):
        ok = _ok_result()
        with patch("scripts.db_client.requests.post", return_value=_pipeline_response([ok, ok, ok])) as mock_post:
            remote_db._http_pipeline([("INSERT INTO t VALUES (?,?)", [1, "hello"])])

        payload = mock_post.call_args[1]["json"]
        stmt_args = payload["requests"][1]["stmt"]["args"]
        assert stmt_args == [
            {"type": "integer", "value": "1"},
            {"type": "text", "value": "hello"},
        ]

    def test_raises_on_error_result(self, remote_db):
        ok = _ok_result()
        err = {"type": "error", "error": {"message": "UNIQUE constraint failed"}}
        with patch("scripts.db_client.requests.post", return_value=_pipeline_response([ok, err, ok])):
            with pytest.raises(RuntimeError, match="UNIQUE constraint failed"):
                remote_db._http_pipeline([("INSERT INTO t VALUES (?)", [1])])

    def test_sends_multiple_statements(self, remote_db):
        ok = _ok_result()
        # BEGIN + 3 stmts + COMMIT = 5 results
        with patch("scripts.db_client.requests.post", return_value=_pipeline_response([ok] * 5)) as mock_post:
            remote_db._http_pipeline([
                ("INSERT INTO a VALUES (?)", [1]),
                ("INSERT INTO b VALUES (?)", [2]),
                ("DELETE FROM c", []),
            ])

        payload = mock_post.call_args[1]["json"]
        assert len(payload["requests"]) == 5
        assert payload["requests"][0]["stmt"]["sql"] == "BEGIN"
        assert payload["requests"][4]["stmt"]["sql"] == "COMMIT"


class TestExecuteBatch:
    def test_local_executes_all_statements(self, seeded_db):
        seeded_db.execute_batch([
            ("INSERT INTO topics (slug, label, match_count) VALUES (?,?,?)", ["a", "A", 1]),
            ("INSERT INTO topics (slug, label, match_count) VALUES (?,?,?)", ["b", "B", 2]),
        ])
        rows = seeded_db.execute("SELECT count(*) as n FROM topics")
        assert rows[0]["n"] == 2

    def test_local_empty_is_noop(self, seeded_db):
        seeded_db.execute_batch([])
        rows = seeded_db.execute("SELECT count(*) as n FROM topics")
        assert rows[0]["n"] == 0

    def test_remote_sends_single_pipeline_call(self, remote_db):
        ok = _ok_result()
        # BEGIN + 2 stmts + COMMIT = 4 results
        with patch("scripts.db_client.requests.post", return_value=_pipeline_response([ok] * 4)) as mock_post:
            remote_db.execute_batch([
                ("DELETE FROM t", []),
                ("INSERT INTO t VALUES (?)", [1]),
            ])

        assert mock_post.call_count == 1
        payload = mock_post.call_args[1]["json"]
        sqls = [r["stmt"]["sql"] for r in payload["requests"]]
        assert sqls == ["BEGIN", "DELETE FROM t", "INSERT INTO t VALUES (?)", "COMMIT"]

    def test_remote_empty_is_noop(self, remote_db):
        with patch("scripts.db_client.requests.post") as mock_post:
            remote_db.execute_batch([])

        mock_post.assert_not_called()


class TestExecuteScriptRemote:
    def test_sends_all_ddl_in_one_pipeline_call(self, remote_db):
        sql = "CREATE TABLE a (id INTEGER);\nCREATE TABLE b (id INTEGER);\n"
        ok = _ok_result()
        # BEGIN + 2 stmts + COMMIT = 4 results
        with patch("scripts.db_client.requests.post", return_value=_pipeline_response([ok] * 4)) as mock_post:
            remote_db.executescript(sql)

        assert mock_post.call_count == 1
        payload = mock_post.call_args[1]["json"]
        sqls = [r["stmt"]["sql"] for r in payload["requests"]]
        assert sqls[0] == "BEGIN"
        assert sqls[1] == "CREATE TABLE a (id INTEGER)"
        assert sqls[2] == "CREATE TABLE b (id INTEGER)"
        assert sqls[3] == "COMMIT"

    def test_skips_blank_lines_and_comments(self, remote_db):
        sql = "-- setup\nCREATE TABLE a (id INTEGER);\n\n-- end\n"
        ok = _ok_result()
        # BEGIN + 1 stmt + COMMIT = 3 results
        with patch("scripts.db_client.requests.post", return_value=_pipeline_response([ok] * 3)) as mock_post:
            remote_db.executescript(sql)

        payload = mock_post.call_args[1]["json"]
        assert len(payload["requests"]) == 3
        assert payload["requests"][1]["stmt"]["sql"] == "CREATE TABLE a (id INTEGER)"


class TestExecuteManyRemote:
    def test_single_batch_for_few_rows(self, remote_db):
        params_list = [[1], [2], [3]]
        ok = _ok_result()
        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        mock_resp.json.return_value = {"results": [ok] * 5}  # BEGIN + 3 + COMMIT

        with patch("scripts.db_client.requests.post", return_value=mock_resp) as mock_post:
            remote_db.executemany("INSERT INTO t VALUES (?)", params_list)

        assert mock_post.call_count == 1
        payload = mock_post.call_args[1]["json"]
        assert len(payload["requests"]) == 5

    def test_chunks_into_batches_of_500(self, remote_db):
        params_list = [[i] for i in range(1001)]
        ok = _ok_result()

        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        mock_resp.json.side_effect = [
            {"results": [ok] * 502},  # BEGIN + 500 + COMMIT
            {"results": [ok] * 502},  # BEGIN + 500 + COMMIT
            {"results": [ok] * 3},    # BEGIN + 1 + COMMIT
        ]

        with patch("scripts.db_client.requests.post", return_value=mock_resp) as mock_post:
            remote_db.executemany("INSERT INTO t VALUES (?)", params_list)

        assert mock_post.call_count == 3

    def test_empty_list_makes_no_http_call(self, remote_db):
        with patch("scripts.db_client.requests.post") as mock_post:
            remote_db.executemany("INSERT INTO t VALUES (?)", [])

        mock_post.assert_not_called()


class TestLocalUrl:
    def test_memory_url(self):
        db = DbClient(":memory:")
        db.close()

    def test_file_prefix_stripped(self, tmp_path):
        url = f"file:{tmp_path / 'test.db'}"
        db = DbClient(url)
        db.close()
