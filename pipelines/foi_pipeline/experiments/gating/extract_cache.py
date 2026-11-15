"""Cached extraction per (fix, content sha)."""
import json
import time
from dataclasses import dataclass
from pathlib import Path

from experiments.gating.fixes import Fix, NotExtracted, get
from experiments.gating.paths import CACHE, content_sha


@dataclass
class Extraction:
    rows: list[list] | None
    status: str  # ok | no_table | error | not_extracted
    seconds: float = 0.0
    error: str | None = None


def _cache_path(fix: Fix, sha: str, cache_dir: Path) -> Path:
    safe = fix.name.replace(":", "_").replace("+", "_")
    return Path(cache_dir) / f"{safe}@{fix.version}" / f"{sha}.json"


def get_rows(fix: Fix, file_url: str, data: bytes, stored_item: dict, cache_dir: Path = CACHE) -> Extraction:
    if fix.extract is None:
        if fix.rows_from is not None:
            return get_rows(get(fix.rows_from), file_url, data, stored_item, cache_dir)
        rows = stored_item.get("rows")  # baseline: not cached
        return Extraction(rows, "ok" if rows else "no_table", 0.0, None)
    p = _cache_path(fix, content_sha(data), cache_dir)
    if p.is_file():
        d = json.loads(p.read_text())
        return Extraction(d["rows"], d["status"], d.get("seconds", 0.0), d.get("error"))
    t = time.time()
    try:
        rows = fix.extract(data, file_url)
        ex = Extraction(rows, "ok" if rows else "no_table", 0.0, None)
        if not rows:
            ex.rows = None
    except NotExtracted:
        return Extraction(None, "not_extracted", time.time() - t, None)
    except Exception as e:  # noqa: BLE001
        ex = Extraction(None, "error", 0.0, str(e))
    ex.seconds = round(time.time() - t, 3)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"rows": ex.rows, "status": ex.status, "seconds": ex.seconds, "error": ex.error}))
    return ex
