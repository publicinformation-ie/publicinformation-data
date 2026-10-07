#!/usr/bin/env python3
"""Seeded stratified sample freeze for the motion-model-sweep experiment.

Run from minutes_pipeline/:
    uv run python experiments/2026-10-07-motion-model-sweep/sample.py

Reads the worktree OCR + extract_motions outputs, draws a frozen sample of
20 files, and writes experiments/2026-10-07-motion-model-sweep/sample.json
(`{seed, files: [{file_url, text, extractor, old_motion_count, old_motions}]}`).
Later tasks import `draw_sample` and read `sample.json`; this script is
standalone (not a pipeline step) and never touches the pipeline runner.

Stratification is over text-length bands x extractor x old-motion-count
buckets, with a deterministic enforcement pass guaranteeing >= 2 no-motion
files and both extractors in the final 20.
"""
import json
import random
from pathlib import Path

_HERE = Path(__file__).parent
_MINUTES_PIPELINE = _HERE.parent.parent
_OCR_OUTPUT = _MINUTES_PIPELINE / "steps" / "ocr_minutes_files" / "output.json"
_EXTRACT_OUTPUT = _MINUTES_PIPELINE / "steps" / "extract_motions" / "output.json"
_QUARANTINE_SIDECAR = (_MINUTES_PIPELINE / "steps" / "ocr_minutes_files"
                       / "quarantined_ids.json")
_SAMPLE_JSON = _HERE / "sample.json"

#: Frozen experiment seed (global constraint).
SEED = 20261007
#: Frozen sample size (global constraint).
SAMPLE_SIZE = 20
#: Mirrors the ocr_minutes_files usability gate: shorter texts were quarantined.
MIN_TEXT_CHARS = 200
#: Text-length band cutoffs (chars): short <10k, medium 10-30k, long >30k.
SHORT_MAX = 10_000
MED_MAX = 30_000
#: Extractors the pipeline emits (output_schema.json enum).
EXTRACTORS = ("pdfplumber", "tesseract")


def _length_band(n_chars: int) -> str:
    if n_chars < SHORT_MAX:
        return "short"
    if n_chars < MED_MAX:
        return "medium"
    return "long"


def _motion_bucket(count: int) -> str:
    if count <= 0:
        return "0"
    if count <= 3:
        return "1-3"
    return "4+"


def _count_of(value) -> int:
    if isinstance(value, dict):
        return int(value.get("count", 0))
    return int(value or 0)


def _motions_of(value) -> list:
    if isinstance(value, dict):
        motions = value.get("motions", [])
        return list(motions) if isinstance(motions, list) else []
    return []


def _usable_url(file_url) -> bool:
    return (isinstance(file_url, str) and file_url.strip()
            and file_url.strip().lower() != "unknown"
            and file_url.startswith("http"))


def build_motion_index(extract_records) -> dict:
    """Map file_url -> {"count": int, "motions": [...]} from extract_motions records."""
    index = {}
    for rec in extract_records or []:
        url = rec.get("file_url")
        if not _usable_url(url) or url in index:
            continue
        motions = rec.get("motions")
        motions = list(motions) if isinstance(motions, list) else []
        index[url] = {"count": len(motions), "motions": motions}
    return index


def _entries(records, old_counts: dict) -> list:
    """Filter to eligible entries, deduped by file_url (first wins)."""
    entries = []
    seen = set()
    for rec in records or []:
        url = rec.get("file_url")
        if not _usable_url(url) or url in seen:
            continue
        if rec.get("quarantined"):
            continue
        text = rec.get("text") or ""
        if len(text.strip()) < MIN_TEXT_CHARS:
            continue
        seen.add(url)
        value = (old_counts or {}).get(url, 0)
        entries.append({"file_url": url,
                        "text": text,
                        "extractor": rec.get("extractor"),
                        "old_motion_count": _count_of(value),
                        "old_motions": _motions_of(value)})
    return entries


def _enforce_guarantees(picks: list, eligible: list, rng: random.Random) -> list:
    """Deterministically top up picks to >= 2 no-motion files and both extractors.

    Replaces victims in place (from the end, preferring motion-bearing files
    and never files added by an earlier enforcement swap), drawing
    replacements from the eligible pool (seeded order). No-ops when the pool
    cannot satisfy a guarantee.
    """
    picks = list(picks)
    inserted = set()

    def replacements(pred):
        used = {p["file_url"] for p in picks} | inserted
        cand = [e for e in eligible if pred(e) and e["file_url"] not in used]
        rng.shuffle(cand)
        return cand

    def swap_in(new):
        for idx in range(len(picks) - 1, -1, -1):
            victim = picks[idx]
            if victim["file_url"] not in inserted and victim["old_motion_count"] > 0:
                picks[idx] = new
                inserted.add(new["file_url"])
                return True
        return False

    need_zero = max(0, 2 - sum(1 for p in picks if p["old_motion_count"] == 0))
    for new in replacements(lambda e: e["old_motion_count"] == 0)[:need_zero]:
        swap_in(new)

    for missing in sorted(set(EXTRACTORS) - {p["extractor"] for p in picks}):
        cand = replacements(lambda e, m=missing: e["extractor"] == m)
        if cand and not swap_in(cand[0]):
            # No motion-bearing victim available: take any non-inserted file
            # of the other extractor, unless it would break the zero minimum.
            for idx in range(len(picks) - 1, -1, -1):
                victim = picks[idx]
                if victim["file_url"] in inserted or victim["extractor"] == missing:
                    continue
                if (victim["old_motion_count"] == 0
                        and sum(1 for p in picks if p["old_motion_count"] == 0) <= 2):
                    continue
                picks[idx] = cand[0]
                inserted.add(cand[0]["file_url"])
                break
    return picks


def draw_sample(records, old_counts: dict, seed: int = SEED) -> list:
    """Draw a seeded stratified sample of SAMPLE_SIZE files.

    records: OCR output records (file_url, text, extractor, ...).
    old_counts: file_url -> int motion count, or file_url ->
        {"count": int, "motions": [...]} (as built by build_motion_index).
        Files absent from old_counts default to count 0 / no motions.
    seed: frozen at SEED; same seed + same inputs -> identical output.
    """
    rng = random.Random(seed)
    eligible = _entries(records, old_counts or {})
    strata: dict = {}
    for entry in eligible:
        key = (_length_band(len((entry["text"] or "").strip())),
               entry["extractor"], _motion_bucket(entry["old_motion_count"]))
        strata.setdefault(key, []).append(entry)
    for key in sorted(strata):
        strata[key] = sorted(strata[key], key=lambda e: e["file_url"])
        rng.shuffle(strata[key])
    order = sorted(strata)
    positions = {key: 0 for key in order}
    picks = []
    while len(picks) < SAMPLE_SIZE:
        progressed = False
        for key in order:
            if len(picks) >= SAMPLE_SIZE:
                break
            if positions[key] < len(strata[key]):
                picks.append(strata[key][positions[key]])
                positions[key] += 1
                progressed = True
        if not progressed:
            break
    return _enforce_guarantees(picks, eligible, rng)


def main() -> None:
    ocr = json.loads(_OCR_OUTPUT.read_text())
    extract = json.loads(_EXTRACT_OUTPUT.read_text())
    records = ocr["results"]
    quarantined = set()
    if _QUARANTINE_SIDECAR.exists():
        try:
            data = json.loads(_QUARANTINE_SIDECAR.read_text())
            quarantined = set(data) if isinstance(data, list) else set()
        except ValueError:
            quarantined = set()
    if quarantined:
        records = [r for r in records if r.get("file_url") not in quarantined]
    index = build_motion_index(extract.get("results", []))
    files = draw_sample(records, index, seed=SEED)
    if len(files) < SAMPLE_SIZE:
        raise RuntimeError(f"Only {len(files)} eligible files; need {SAMPLE_SIZE}")
    _SAMPLE_JSON.write_text(json.dumps({"seed": SEED, "files": files}, indent=2))
    zeros = sum(1 for f in files if f["old_motion_count"] == 0)
    extractors = sorted({f["extractor"] for f in files})
    print(f"Drew {len(files)} files (seed={SEED}, no-motion={zeros}, "
          f"extractors={extractors}) -> {_SAMPLE_JSON}")


if __name__ == "__main__":
    main()
