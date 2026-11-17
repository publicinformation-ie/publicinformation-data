"""Blast-radius check: what would a candidate non-FOI pattern reject, and is that safe?"""
import argparse
import sys
from datetime import date
from pathlib import Path

import pymupdf

from experiments.gating import scope, triage
from experiments.gating.paths import STEPS, load_results, pdf_bytes

sys.path.insert(0, str(STEPS.parent))
from steps.verify_disclosure_files.process import _normalize_url_text  # noqa: E402

MIN_CONFIRMED = 3


def affected(url_patterns: list[str], content_patterns: list[tuple[str, ...]],
             verify_results: list[dict], texts: dict[str, str | None]) -> list[dict]:
    """Files not already rejected that the patterns would reject (mirrors _is_non_foi_document)."""
    out = []
    for item in verify_results:
        if item.get("verification_status") == "rejected":
            continue
        url = item["file_url"]
        url_text = _normalize_url_text(url, item.get("link_text") or "").lower()
        matched = next((p for p in url_patterns if p in url_text), None)
        if matched is None:
            text = texts.get(url)
            if text:
                low = text.lower()
                for phrases in content_patterns:
                    if all(ph in low for ph in phrases):
                        matched = "|".join(phrases)
                        break
        if matched is not None:
            out.append({"file_url": url, "public_body_id": item.get("public_body_id"),
                        "records": item.get("records", 0), "matched": matched})
    return out


def verdict(rows: list[dict], confirmed_not_foi: set[str]) -> dict:
    covers = sum(1 for r in rows if r["file_url"] in confirmed_not_foi)
    with_records = [r["file_url"] for r in rows if r["records"] > 0]
    unconfirmed = [r["file_url"] for r in rows if r["file_url"] not in confirmed_not_foi]
    return {"covers_confirmed": covers, "would_reject_with_records": with_records,
            "would_reject_unconfirmed": unconfirmed,
            "ok": covers >= MIN_CONFIRMED and not with_records}


def _text(url: str) -> str | None:
    data = pdf_bytes(url)
    if data is None:
        return None
    try:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            if doc.needs_pass:
                return None
            return "".join(page.get_text() for page in doc)
    except Exception:  # noqa: BLE001 - unreadable file simply has no text
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url-pattern", action="append", default=[])
    ap.add_argument("--content-pattern", action="append", default=[], help='phrases joined by "|"')
    ap.add_argument("--round-dir", required=True, type=Path)
    a = ap.parse_args()
    content = [tuple(p.split("|")) for p in a.content_pattern]
    vr = load_results(STEPS / "verify_disclosure_files" / "output.json")
    stats = scope.file_stats()
    for it in vr:
        s = stats.get(it["file_url"])
        it["records"] = s.records if s else 0
    texts = {it["file_url"]: _text(it["file_url"]) for it in vr} if content else {}
    confirmed = set(triage.exclusion_entries(a.round_dir, date.today().isoformat()))
    v = verdict(affected(a.url_pattern, content, vr, texts), confirmed)
    print(f"ok={v['ok']} covers_confirmed={v['covers_confirmed']}")
    for key in ("would_reject_with_records", "would_reject_unconfirmed"):
        print(f"{key}: {len(v[key])}")
        for u in v[key]:
            print("  ", u)


if __name__ == "__main__":
    main()
