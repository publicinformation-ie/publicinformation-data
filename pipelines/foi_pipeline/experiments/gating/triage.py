"""Per-file facts for FOI source-file triage.

Run from pipelines/foi_pipeline:
  uv run python -m experiments.gating.triage inputs --round-dir D
"""
import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pymupdf

from experiments.gating.paths import GATING, STEPS, content_sha, load_results, pdf_bytes

SCAN_CHARS_PER_PAGE = 50
TEXT_HEAD_CHARS = 2000
IMAGE_DPI = 110


@dataclass
class TriageFacts:
    file_url: str
    public_body_id: int | None
    name: str
    sha256: str | None
    pages: int
    chars_per_page: float
    likely_scan: bool
    text_head: str
    link_text: str | None
    verification_signal: str | None
    image: str | None
    unreadable: str | None


def _unreadable(entry: dict, sha: str | None, reason: str) -> TriageFacts:
    return TriageFacts(entry["file_url"], entry.get("public_body_id"), entry.get("name"), sha,
                       0, 0.0, False, "", None, None, None, reason)


def facts(entry: dict, data: bytes | None) -> TriageFacts:
    if data is None:
        return _unreadable(entry, None, "no_bytes")
    sha = content_sha(data)
    try:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            if doc.needs_pass:
                return _unreadable(entry, sha, "encrypted")
            n = doc.page_count
            if n == 0:
                return _unreadable(entry, sha, "zero_pages")
            text = "".join(page.get_text() for page in doc)
    except Exception as e:  # noqa: BLE001 - any parse failure is a fact, not an error
        return _unreadable(entry, sha, type(e).__name__)
    cpp = len(text.strip()) / n
    return TriageFacts(entry["file_url"], entry.get("public_body_id"), entry.get("name"), sha, n,
                       round(cpp, 1), cpp < SCAN_CHARS_PER_PAGE, text[:TEXT_HEAD_CHARS],
                       None, None, None, None)


def _render_first_page(data: bytes, out: Path) -> bool:
    try:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            if doc.needs_pass or doc.page_count == 0:
                return False
            out.parent.mkdir(parents=True, exist_ok=True)
            doc[0].get_pixmap(dpi=IMAGE_DPI).save(out)
            return True
    except Exception:  # noqa: BLE001
        return False


def build_inputs(round_dir: Path, ledger_path: Path = GATING / "ledger.json",
                 steps_dir: Path = STEPS, cache_dir: Path | None = None) -> list[TriageFacts]:
    round_dir = Path(round_dir)
    entries = [e for e in json.loads(Path(ledger_path).read_text()) if e["fault_kind"] == "S"]
    verif = {r["file_url"]: r for r in load_results(Path(steps_dir) / "verify_disclosure_files" / "output.json")}
    out = []
    for e in entries:
        data = pdf_bytes(e["file_url"]) if cache_dir is None else pdf_bytes(e["file_url"], cache_dir)
        f = facts(e, data)
        v = verif.get(e["file_url"], {})
        f.link_text = v.get("link_text")
        f.verification_signal = v.get("verification_signal")
        if data is not None and f.unreadable is None:
            rel = f"review/img/{f.sha256}.png"
            if _render_first_page(data, round_dir / rel):
                f.image = rel
        out.append(f)
    round_dir.mkdir(parents=True, exist_ok=True)
    (round_dir / "inputs.json").write_text(json.dumps([asdict(f) for f in out], indent=2) + "\n")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("inputs")
    p.add_argument("--round-dir", required=True, type=Path)
    a = ap.parse_args()
    fs = build_inputs(a.round_dir)
    print(f"{len(fs)} entries; likely_scan={sum(f.likely_scan for f in fs)}; "
          f"unreadable={sum(f.unreadable is not None for f in fs)}")
    print("chars_per_page:", sorted(f.chars_per_page for f in fs if f.unreadable is None))


if __name__ == "__main__":
    main()
