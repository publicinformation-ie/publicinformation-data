import os
import sqlite3
import requests


class DbClient:
    """Database client: sqlite3 for local files/memory, libSQL HTTP v2 API for remote URLs."""

    def __init__(self, url=None, auth_token=None):
        url = url or os.getenv("DATABASE_URL", "local.db")
        auth_token = auth_token or os.getenv("DATABASE_AUTH_TOKEN", "")
        if url.startswith("libsql://"):
            url = "https://" + url[len("libsql://"):]
        self._local = not url.startswith("http")
        if self._local:
            path = url.removeprefix("file:") if url.startswith("file:") else url
            self._conn = sqlite3.connect(path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
        else:
            self._remote_url = url.rstrip("/") + "/v2/pipeline"
            self._headers = {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json",
            }

    def execute(self, sql, params=None):
        if self._local:
            cur = self._conn.cursor()
            cur.execute(sql, params or [])
            self._conn.commit()
            return [dict(row) for row in cur.fetchall()]
        return self._http_execute(sql, params)

    def executemany(self, sql, params_list):
        if not params_list:
            return
        if self._local:
            cur = self._conn.cursor()
            cur.executemany(sql, params_list)
            self._conn.commit()
        else:
            chunk_size = 500
            for i in range(0, len(params_list), chunk_size):
                chunk = params_list[i : i + chunk_size]
                self._http_pipeline([(sql, params) for params in chunk])

    def executescript(self, sql):
        """Execute multiple semicolon-separated DDL statements (schema init)."""
        if self._local:
            self._conn.executescript(sql)
        else:
            stmts = [
                s.strip()
                for s in sql.split(";")
                if s.strip() and not s.strip().startswith("--")
            ]
            for stmt in stmts:
                self._http_execute(stmt)

    def close(self):
        if self._local:
            self._conn.close()

    def _build_args(self, params):
        args = []
        for p in (params or []):
            if p is None:
                args.append({"type": "null", "value": None})
            elif isinstance(p, bool):
                args.append({"type": "integer", "value": "1" if p else "0"})
            elif isinstance(p, int):
                args.append({"type": "integer", "value": str(p)})
            elif isinstance(p, float):
                args.append({"type": "float", "value": str(p)})
            else:
                args.append({"type": "text", "value": str(p)})
        return args

    def _http_pipeline(self, stmts):
        """Send stmts as a single pipeline POST wrapped in BEGIN/COMMIT.
        stmts: list of (sql, params) tuples.
        Raises RuntimeError if any result is not 'ok'.
        """
        requests_list = [{"type": "execute", "stmt": {"sql": "BEGIN", "args": []}}]
        for sql, params in stmts:
            requests_list.append({
                "type": "execute",
                "stmt": {"sql": sql, "args": self._build_args(params)},
            })
        requests_list.append({"type": "execute", "stmt": {"sql": "COMMIT", "args": []}})

        resp = requests.post(
            self._remote_url,
            json={"requests": requests_list},
            headers=self._headers,
            timeout=30,
        )
        resp.raise_for_status()
        for result in resp.json()["results"]:
            if result["type"] != "ok":
                raise RuntimeError(
                    f"libSQL error: {result.get('error', {}).get('message', 'unknown')}"
                )

    def _http_execute(self, sql, params=None):
        payload = {
            "requests": [{"type": "execute", "stmt": {"sql": sql, "args": self._build_args(params)}}]
        }
        resp = requests.post(self._remote_url, json=payload, headers=self._headers, timeout=30)
        resp.raise_for_status()
        result = resp.json()["results"][0]
        if result["type"] != "ok":
            raise RuntimeError(
                f"libSQL error: {result.get('error', {}).get('message', 'unknown')}"
            )
        execute_result = result["response"]["result"]
        cols = [c["name"] for c in execute_result.get("cols", [])]
        rows = execute_result.get("rows", [])

        def convert(cell):
            if cell["type"] == "null":
                return None
            if cell["type"] == "integer":
                return int(cell["value"])
            if cell["type"] == "float":
                return float(cell["value"])
            return cell["value"]

        return [{cols[i]: convert(row[i]) for i in range(len(cols))} for row in rows]
