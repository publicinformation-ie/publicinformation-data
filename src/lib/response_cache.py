"""Content-keyed JSON cache on disk.

Used to persist raw responses from paid APIs (Apify, Haiku) so a search is never
paid for twice and can be re-interpreted later with better logic.
"""
import hashlib
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


class ResponseCache:
    def __init__(self, directory):
        self.dir = Path(directory)

    @staticmethod
    def key(*parts) -> str:
        blob = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]

    def _path(self, key: str) -> Path:
        return self.dir / f"{key}.json"

    def get(self, key: str, max_age_days: float | None = None) -> dict | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if max_age_days is not None:
            try:
                cached_at = datetime.fromisoformat(record["cached_at"])
            except (KeyError, ValueError):
                return None
            if datetime.now(timezone.utc) - cached_at > timedelta(days=max_age_days):
                return None
        return record

    def put(self, key: str, payload: dict) -> dict:
        record = {"cached_at": datetime.now(timezone.utc).isoformat(), **payload}
        self.dir.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.dir, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self._path(key))
        return record
