"""Per-file facts for FOI source-file triage.

Run from pipelines/foi_pipeline:
  uv run python -m experiments.gating.triage inputs --round-dir D
"""
import argparse
import json
from datetime import date
from dataclasses import asdict, dataclass
from pathlib import Path

import pymupdf

from experiments.gating import ledger
from experiments.gating.ledger import TRIAGE_CLASSES
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


def load_proposals(round_dir: Path) -> dict[str, dict]:
    """Read and validate proposals.json against inputs.json."""
    round_dir = Path(round_dir)
    inputs = json.loads((round_dir / "inputs.json").read_text())
    known = {e["file_url"]: e for e in inputs}
    out: dict[str, dict] = {}
    for p in json.loads((round_dir / "proposals.json").read_text()):
        url = p.get("file_url")
        if url not in known:
            raise ValueError(f"proposal for URL not in inputs.json: {url}")
        if p.get("class") not in TRIAGE_CLASSES:
            raise ValueError(f"{url}: class {p.get('class')!r} not in {TRIAGE_CLASSES}")
        if not str(p.get("reason") or "").strip():
            raise ValueError(f"{url}: empty reason")
        out[url] = {"class": p["class"], "reason": p["reason"].strip()}
    for url, e in known.items():
        if not e.get("unreadable") and url not in out:
            raise ValueError(f"no proposal for {url}")
    return out


def _verdicts(round_dir: Path) -> dict[str, dict]:
    path = Path(round_dir) / "verdicts.json"
    raw = json.loads(path.read_text()) if path.exists() else {}
    return {k[len("file:"):]: v for k, v in raw.items() if k.startswith("file:")}


def _class_tags(verdict: dict | None) -> list[str]:
    tags = (verdict or {}).get("tags") or []
    return sorted({t for t in tags if t in TRIAGE_CLASSES})


def decide(proposal: dict | None, verdict: dict | None) -> tuple[str | None, bool]:
    """Return (class, confirmed). The user's class tag wins; not_foi_log is never confirmed by a proposal."""
    tags = _class_tags(verdict)
    if len(tags) == 1:
        return tags[0], True
    if len(tags) > 1 or proposal is None:
        return None, False
    if proposal["class"] == "not_foi_log":
        return None, False
    return proposal["class"], True


LEDGER_FIELDS = {
    "scan": {"fault_kind": "E", "cluster": "scan"},
    "hard_table": {"fault_kind": "E"},
    "small_log": {"fault_kind": "G", "cluster": "small-log"},
    "not_foi_log": {"fault_kind": "S", "status": "parked", "note": "excluded upstream"},
}


def _decisions(round_dir: Path) -> tuple[dict[str, tuple[str | None, bool]], dict, dict]:
    proposals = load_proposals(round_dir)
    verdicts = _verdicts(round_dir)
    urls = [e["file_url"] for e in json.loads((Path(round_dir) / "inputs.json").read_text())]
    return {u: decide(proposals.get(u), verdicts.get(u)) for u in urls}, proposals, verdicts


def apply_verdicts(round_dir: Path, state_path: Path = ledger.STATE_PATH) -> dict:
    decisions, _, _ = _decisions(round_dir)
    confirmed: dict[str, list[str]] = {}
    unconfirmed = []
    for url, (cls, ok) in decisions.items():
        if ok and cls:
            confirmed.setdefault(cls, []).append(url)
        else:
            unconfirmed.append(url)
    for cls, urls in confirmed.items():
        ledger.set_state(urls, state_path=state_path, fault_firm=True, triage_class=cls, **LEDGER_FIELDS[cls])
    return {"confirmed": confirmed, "unconfirmed": unconfirmed}


def exclusion_entries(round_dir: Path, today: str) -> dict[str, dict]:
    """Only files whose own user tag confirmed not_foi_log; a proposal alone never does."""
    decisions, proposals, verdicts = _decisions(round_dir)
    out = {}
    for url, (cls, ok) in decisions.items():
        if ok and cls == "not_foi_log" and _class_tags(verdicts.get(url)) == ["not_foi_log"]:
            reason = str((verdicts[url].get("text") or "")).strip() or (proposals.get(url) or {}).get("reason", "")
            out[url] = {"reason": reason, "class": "not_foi_log", "date": today}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("inputs")
    p.add_argument("--round-dir", required=True, type=Path)
    q = sub.add_parser("apply")
    q.add_argument("--round-dir", required=True, type=Path)
    a = ap.parse_args()
    if a.cmd == "apply":
        res = apply_verdicts(a.round_dir)
        print("confirmed:", {c: len(u) for c, u in sorted(res["confirmed"].items())})
        print(f"unconfirmed: {len(res['unconfirmed'])}")
        for u in res["unconfirmed"]:
            print("  ", u)
        ex = exclusion_entries(a.round_dir, date.today().isoformat())
        (a.round_dir / "exclusions_proposed.json").write_text(json.dumps(ex, indent=2) + "\n")
        print(f"exclusions_proposed.json: {len(ex)} entries")
        return
    fs = build_inputs(a.round_dir)
    print(f"{len(fs)} entries; likely_scan={sum(f.likely_scan for f in fs)}; "
          f"unreadable={sum(f.unreadable is not None for f in fs)}")
    print("chars_per_page:", sorted(f.chars_per_page for f in fs if f.unreadable is None))


if __name__ == "__main__":
    main()
