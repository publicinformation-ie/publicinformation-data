#!/usr/bin/env python3
"""TOC-name occurrence-scoring prototype — read-only comparison.

Runs a prototype of the proposed `from_toc` strategy alongside the legacy
detection cascade over every document's cached `extract_pages` output, and
reports the diagnostics the change needs to settle its thresholds. It never
writes to any pipeline step's output — only `results/results.json` in this
directory.

Run from the document_pipeline directory:

    PYTHONPATH=".:../../src" python experiments/2026-10-17-toc-splitting-comparison/run.py

The prototype deliberately mirrors the shape the production `from_toc` will
take so the numbers transfer: `normalize_heading_text`, `is_heading_candidate`,
`running_header_texts`, `parse_toc`, `find_occurrences`, `score_occurrence`,
`from_toc`, and `validate_split` are written here first, then ported (with
thresholds refined from these results) into `detect_structure/process.py`.
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

_HERE = Path(__file__).parent
_DOC_PIPELINE = _HERE.parents[1]
_REPO_ROOT = _HERE.parents[2]
sys.path.insert(0, str(_DOC_PIPELINE))       # for `documents`, `policies`, `steps.*`
sys.path.insert(0, str(_REPO_ROOT / "src"))  # for `lib.*`

from steps.detect_structure.process import (  # noqa: E402
    CONFIDENCE,
    NUMBER_PREFIX_RE,
    Line,
    Node,
    _legacy_cascade,
    _split_number,
    assign_hierarchy,
    assign_page_ranges,
    body_size,
    dedupe_slugs,
    from_font_hierarchy,
    from_numbering,
    from_outline,
    is_bold,
    page_lines,
    slugify,
    style_histogram,
)

_PAGES_BASE = _DOC_PIPELINE / "steps" / "extract_pages"
_OUTPUT_JSON = _PAGES_BASE / "output.json"
_RESULTS_DIR = _HERE / "results"
_RESULTS_PATH = _RESULTS_DIR / "results.json"

# ---------------------------------------------------------------------------
# Prototype constants — initial guesses, refined from the results below.
# ---------------------------------------------------------------------------

TOC_TITLES = {"contents", "table of contents"}
RUNNING_HEADER_FRACTION = 0.25
DOT_LEADER_RE = re.compile(r"\.{4,}|\u2026")
RIGHT_COLUMN_MIN_X_FRACTION = 0.5
SCORE_FLOOR = 0.0        # placeholder; pinned from results
MATCH_RATE_GATE = 0.60   # initial value (design decision 4)

# Furniture: TOC entries with no corresponding body heading. Excluded from the
# match-rate denominator so they cannot depress the gate.
FURNITURE_TITLES = {
    "abbreviations", "abbreviation", "glossary", "glossary of terms",
    "list of figures", "list of tables", "list of maps", "list of boxes",
    "list of photographs", "list of appendices", "index", "contents",
    "table of contents", "bibliography",
}


def normalize_heading_text(text):
    """Lowercase, collapse whitespace, strip control chars and trailing
    punctuation/dots (incl. …). Control chars (\x07, \x08) appear as extraction
    artifacts in some documents and must not break exact matching."""
    t = str(text)
    t = re.sub(r"[\x00-\x1f\x7f]", " ", t)
    t = re.sub(r"\s+", " ", t).strip().lower()
    return t.rstrip(".,;:!?\u2026 \t")


def is_heading_candidate(title):
    t = str(title).strip()
    if not t or not re.search(r"[a-zA-Z]", t):
        return False
    if len(t) == 1 or len(t) > 120:
        return False
    if DOT_LEADER_RE.search(t):
        return False
    if re.match(r"^[\u2022\u00b7\-\u2013\u2014\*\u25cf\u25aa]\s", t):
        return False
    if re.match(r"^[\u20ac\u00a3$]", t):
        return False
    return True


def running_header_texts(pages, fraction=RUNNING_HEADER_FRACTION):
    """Normalized texts of lines appearing on >= `fraction` of pages."""
    count = Counter()
    total = len(pages)
    for page in pages:
        for line in page_lines(page):
            norm = normalize_heading_text(line.text)
            if len(norm) >= 4:
                count[norm] += 1
    return {text for text, n in count.items() if n / max(total, 1) >= fraction}


# ---------------------------------------------------------------------------
# TOC page detection + entry parsing
# ---------------------------------------------------------------------------

def _page_signals(page, body):
    lines = page_lines(page)
    width = float(page.get("width") or 595.0)
    title_heading = False
    title_any = False
    for line in lines:
        if normalize_heading_text(line.text) in TOC_TITLES:
            title_any = True
            if line.size >= body + 0.5:
                title_heading = True
    dot_lines = [l for l in lines if DOT_LEADER_RE.search(l.text)]
    right_nums = [l for l in lines
                  if re.fullmatch(r"\d{1,3}", l.text.strip())
                  and l.bbox[0] > width * RIGHT_COLUMN_MIN_X_FRACTION]
    return {
        "title_heading": title_heading,
        "title_any": title_any,
        "dot_lines": len(dot_lines),
        "right_nums": len(right_nums),
        "line_count": len(lines),
    }


def _strip_toc_suffix(text):
    """Remove trailing dot leaders and any page number glued to them."""
    t = text.strip()
    t = re.sub(r"[\s.\u2026]+\d{1,3}\s*$", "", t)  # "Title ... 12"
    t = re.sub(r"[\s.\u2026]+$", "", t)             # "Title ......."
    return t.strip()


def _classify_furniture(title):
    norm = normalize_heading_text(title)
    return norm in FURNITURE_TITLES or norm.startswith("list of ")


def _parse_toc_page(page, body):
    """Return (entries, shape_flags) for one TOC page.

    Each entry is a dict: {title, number, level_hint, separate_line_number,
    has_dot_leader, dot_leader_kind, furniture}.
    """
    lines = page_lines(page)
    entries = []
    flags = {"separate_line_number": False, "right_page_number": False,
             "unicode_dot_leader": False, "ascii_dot_leader": False}
    width = float(page.get("width") or 595.0)
    i = 0
    while i < len(lines):
        line = lines[i]
        text = line.text.strip()
        norm = normalize_heading_text(text)

        if norm in TOC_TITLES:
            i += 1
            continue

        # A bare page number sitting far right (right-hand column shape).
        if re.fullmatch(r"\d{1,3}", text) and line.bbox[0] > width * RIGHT_COLUMN_MIN_X_FRACTION:
            flags["right_page_number"] = True
            i += 1
            continue

        # A number on its own line followed by a title line (separate-line shape).
        if re.fullmatch(r"\d{1,2}(?:\.\d{1,2}){0,2}\.?", text) and len(text) <= 7:
            flags["separate_line_number"] = True
            number = text.rstrip(".")
            i += 1
            title_parts = []
            while i < len(lines):
                nxt = lines[i]
                nt = nxt.text.strip()
                if re.fullmatch(r"\d{1,3}", nt) or normalize_heading_text(nt) in TOC_TITLES:
                    break
                if re.fullmatch(r"\d{1,2}(?:\.\d{1,2}){0,2}\.?", nt) and len(nt) <= 7:
                    break
                title_parts.append(nt)
                i += 1
            title = _strip_toc_suffix(" ".join(title_parts))
            if title and is_heading_candidate(title):
                entries.append(_make_entry(title, number, DOT_LEADER_RE.search(" ".join(title_parts)),
                                           line, flags))
            continue

        # Ordinary entry: title, maybe dot leaders, maybe inline number.
        m = NUMBER_PREFIX_RE.match(text)
        number = None
        if m:
            number = m.group(1)
            text = m.group(2)
        title = _strip_toc_suffix(text)
        if title and is_heading_candidate(title):
            entries.append(_make_entry(title, number, DOT_LEADER_RE.search(text), line, flags))
        i += 1
    return entries, flags


def _make_entry(title, number, has_dot, line, flags):
    if has_dot:
        if "\u2026" in str(line.text):
            flags["unicode_dot_leader"] = True
        else:
            flags["ascii_dot_leader"] = True
    return {
        "title": title,
        "number": number,
        "level_hint": len(number.split(".")) if number else None,
        "x0": round(line.bbox[0], 1),
        "furniture": _classify_furniture(title),
    }


def _infer_levels(entries):
    """Infer a level per entry from numbering depth or indentation.

    Returns (entries_with_level, signal) where signal is 'numbering', 'indent',
    or 'none'.
    """
    numbered = [e for e in entries if e["number"]]
    if len(numbered) >= 2 and any(e["level_hint"] > 1 for e in numbered):
        return [{**e, "level": e["level_hint"] or 1} for e in entries], "numbering"

    x0s = sorted({e["x0"] for e in entries})
    if len(x0s) >= 2:
        # cluster into at most 3 indentation levels
        levels = {x0: min(i + 1, 3) for i, x0 in enumerate(x0s[:3])}
        # map every x0 to nearest cluster
        result = []
        for e in entries:
            nearest = min(levels, key=lambda x: abs(x - e["x0"]))
            result.append({**e, "level": levels[nearest]})
        return result, "indent"
    return [{**e, "level": 1} for e in entries], "none"


_LIST_OF_RE = re.compile(r"^list of (figures|tables|maps|boxes|photographs|appendices|abbreviations)")


def _page_kind(page, body):
    """Classify a TOC-signal page as 'contents', 'list-of' (furniture), or None."""
    lines = page_lines(page)
    for line in lines:
        norm = normalize_heading_text(line.text)
        if norm in TOC_TITLES:
            return "contents"
        if _LIST_OF_RE.match(norm):
            return "list-of"
    return None


def parse_toc(pages, body):
    """Detect TOC pages and return (entries, toc_page_numbers, signal, flags).

    Only the first contiguous run of `contents` pages is parsed (a multi-page
    main TOC). Later part-TOCs (appendices, embedded reports) and `list-of-*`
    furniture pages are reported in `flags` but do not contribute entries, so
    a multi-part document does not over-split.
    """
    flagged = []
    for page in pages:
        sig = _page_signals(page, body)
        is_toc = (
            sig["title_heading"]
            or sig["dot_lines"] >= 3
            or (sig["title_any"] and sig["right_nums"] >= 3)
        )
        if is_toc:
            flagged.append(page["number"])

    # First contiguous block of TOC pages (skip list-of-* furniture).
    toc_pages = []
    for num in flagged:
        kind = _page_kind(next(p for p in pages if p["number"] == num), body)
        if kind == "list-of":
            continue
        if toc_pages and num != toc_pages[-1] + 1:
            break  # gap: a later part-TOC, not the main one
        toc_pages.append(num)

    flags = {"separate_line_number": False, "right_page_number": False,
             "unicode_dot_leader": False, "ascii_dot_leader": False,
             "multi_toc": False, "title_at_body_size": False,
             "part_tocs": []}

    all_entries = []
    for num in toc_pages:
        page = next(p for p in pages if p["number"] == num)
        sig = _page_signals(page, body)
        if sig["title_any"] and not sig["title_heading"]:
            flags["title_at_body_size"] = True
        entries, page_flags = _parse_toc_page(page, body)
        for k in ("separate_line_number", "right_page_number",
                  "unicode_dot_leader", "ascii_dot_leader"):
            flags[k] = flags[k] or page_flags[k]
        all_entries.extend(entries)

    extra = [n for n in flagged if n not in toc_pages]
    if extra:
        flags["multi_toc"] = True
        flags["part_tocs"] = extra

    if all_entries:
        all_entries, level_signal = _infer_levels(all_entries)
    else:
        level_signal = "none"

    return all_entries, toc_pages, level_signal, flags


# ---------------------------------------------------------------------------
# Occurrence search + scoring
# ---------------------------------------------------------------------------

def _joined_runs(lines):
    """Yield (start_index, k, text) for k=1..3 consecutive line joins."""
    n = len(lines)
    for k in (1, 2, 3):
        for start in range(0, n - k + 1):
            yield start, k, " ".join(l.text for l in lines[start:start + k])


def build_occurrence_index(pages, toc_page_numbers, running_headers,
                           number_tolerant):
    """Map normalized joined text -> list of occurrences (one pass over pages).

    `find_occurrences` becomes an O(1) lookup against this index, which keeps
    the experiment fast on the 1107-page document.
    """
    index = {}
    for page in pages:
        if page["number"] in toc_page_numbers:
            continue
        lines = page_lines(page)
        for start, k, joined in _joined_runs(lines):
            norm = normalize_heading_text(joined)
            if norm in running_headers:
                continue
            block = lines[start:start + k]
            occ = {
                "page": page["number"],
                "start_index": start,
                "k": k,
                "y0": block[0].y0,
                "y1": block[-1].bbox[3],
                "size": max(l.size for l in block),
                "font": block[0].font,
                "bold": any(is_bold(l.font) for l in block),
                "text": joined,
            }
            index.setdefault(norm, []).append(occ)
            if number_tolerant:
                number, rest = _split_number(joined)
                if number:
                    index.setdefault(normalize_heading_text(rest), []).append(occ)
    return index


def find_occurrences(index, toc_title):
    """Look up candidate occurrences of `toc_title` in the prebuilt index."""
    return index.get(normalize_heading_text(toc_title), [])


def score_occurrence(occ, body, lines):
    """Monotonic size score + bold/isolation bonuses."""
    score = occ["size"] / max(body, 0.1)
    if occ["bold"]:
        score += 0.5
    return score


def from_toc(pages, body, entries, index):
    """Build nodes for the TOC-name strategy (prototype)."""
    nodes = []
    used = set()  # (page, y0) already claimed
    for entry in entries:
        occs = find_occurrences(index, entry["title"])
        if not occs:
            continue
        occs.sort(key=lambda o: (score_occurrence(o, body, None), o["page"], o["y0"]),
                  reverse=True)
        best = occs[0]
        key = (best["page"], round(best["y0"], 1))
        if key in used:
            continue
        used.add(key)
        number, title = _split_number(best["text"])
        node = Node(level=entry["level"], number=number, title=title,
                    slug=slugify(f"{number} {title}" if number else title),
                    start_page=best["page"], start_y=best["y0"],
                    confidence=CONFIDENCE["numbering"])  # placeholder between 0.9 and 1.0
        nodes.append(node)
    return nodes


def supplement_nodes(pages, body, base_nodes, toc_titles, running_headers):
    """Add legacy numbered headings not already covered by the TOC set.

    Only the `numbering` strategy is used for supplementing — the `font`
    strategy is the low-precision over-splitter this change exists to replace,
    so re-adding its nodes would reintroduce the junk.
    """
    toc_set = {normalize_heading_text(t) for t in toc_titles}
    claimed = {(n.start_page, round(n.start_y, 1)) for n in base_nodes}
    legacy = from_numbering(pages, body)
    extra = []
    for node in legacy:
        norm = normalize_heading_text(node.title)
        if norm in toc_set or norm in running_headers:
            continue
        key = (node.start_page, round(node.start_y, 1))
        if key in claimed:
            continue
        claimed.add(key)
        extra.append(node)
    return base_nodes + extra


def validate_split(nodes, page_count):
    """Return a list of issue strings for a node list (prototype)."""
    issues = []
    for node in nodes:
        if not is_heading_candidate(node.title):
            issues.append(f"junk title {node.slug!r} = {node.title!r}")
    seen = {}
    for node in nodes:
        key = (node.start_page, round(node.start_y, 1))
        if key in seen:
            issues.append(f"duplicate boundary {node.slug!r} and {seen[key]!r}")
        seen[key] = node.slug
    ordered = sorted(nodes, key=lambda n: (n.start_page, n.start_y))
    if not ordered:
        return issues
    first = ordered[0].start_page
    covered = set()
    for node in ordered:
        for p in range(node.start_page, node.end_page + 1):
            covered.add(p)
    for p in range(first, page_count + 1):
        if p not in covered:
            issues.append(f"coverage gap at page {p}")
    return issues


# ---------------------------------------------------------------------------
# Comparison loop
# ---------------------------------------------------------------------------

def load_pages(record):
    pages = []
    for entry in sorted(record["pages"], key=lambda e: e["number"]):
        pages.append(json.loads((_PAGES_BASE / entry["file"]).read_text(encoding="utf-8")))
    return pages


def compare(record, number_tolerant):
    pages = load_pages(record)
    page_count = int(record.get("page_count") or len(pages))
    body = body_size(pages)
    running = running_header_texts(pages)

    # Legacy cascade — the pre-TOC behaviour: outline wins, else numbering/font/flat.
    if record.get("outline"):
        legacy_nodes, legacy_method = from_outline(record["outline"]), "outline"
    else:
        legacy_nodes, legacy_method = _legacy_cascade(pages, body)
    legacy_nodes = dedupe_slugs(sorted(legacy_nodes, key=lambda n: (n.start_page, n.start_y)))
    legacy_nodes = assign_hierarchy(legacy_nodes)
    legacy_nodes = assign_page_ranges(legacy_nodes, page_count)
    legacy_issues = validate_split(legacy_nodes, page_count)
    legacy_slugs = [n.slug for n in legacy_nodes]

    # TOC prototype.
    entries, toc_pages, level_signal, flags = parse_toc(pages, body)
    plausible = [e for e in entries if not e["furniture"]]
    index = build_occurrence_index(pages, toc_pages, running, number_tolerant)
    toc_nodes = from_toc(pages, body, entries, index)
    toc_titles = [e["title"] for e in entries]
    combined = supplement_nodes(pages, body, toc_nodes, toc_titles, running)
    combined = dedupe_slugs(sorted(combined, key=lambda n: (n.start_page, n.start_y)))
    combined = assign_hierarchy(combined)
    combined = assign_page_ranges(combined, page_count)
    toc_issues = validate_split(combined, page_count)

    # Match-rate diagnostics.
    def match_count(entry_list):
        matched = 0
        for e in entry_list:
            if find_occurrences(index, e["title"]):
                matched += 1
        return matched

    all_matched = match_count(entries)
    plausible_matched = match_count(plausible)

    # Repeated-title rate.
    title_counts = Counter(normalize_heading_text(e["title"]) for e in entries)
    repeated = sum(1 for t, c in title_counts.items() if c > 1)

    # Slug preservation vs legacy.
    toc_slugs = [n.slug for n in combined]
    preserved = sum(1 for s in toc_slugs if s in set(legacy_slugs))

    return {
        "doc_slug": record["doc_slug"],
        "legacy_method": legacy_method,
        "page_count": page_count,
        "body_size": body,
        "toc_detected": bool(toc_pages),
        "toc_pages": toc_pages,
        "level_signal": level_signal,
        "flags": flags,
        "entry_count": len(entries),
        "furniture_count": sum(1 for e in entries if e["furniture"]),
        "plausible_count": len(plausible),
        "repeated_titles": repeated,
        "all_matched": all_matched,
        "plausible_matched": plausible_matched,
        "match_rate_all": round(all_matched / len(entries), 3) if entries else None,
        "match_rate_plausible": round(plausible_matched / len(plausible), 3) if plausible else None,
        "running_headers": len(running),
        "legacy_nodes": len(legacy_nodes),
        "legacy_issues": len(legacy_issues),
        "legacy_slugs": legacy_slugs,
        "toc_nodes": len(toc_nodes),
        "combined_nodes": len(combined),
        "toc_issues": len(toc_issues),
        "toc_slugs": toc_slugs,
        "slug_preserved": preserved,
        "slug_changed": len(legacy_slugs) - preserved,
    }


def main():
    parser = argparse.ArgumentParser(description="TOC-name strategy read-only comparison")
    parser.add_argument("--rule", choices=["exact", "number-tolerant"], default="exact",
                        help="which matching rule to apply")
    parser.add_argument("--doc", default=None, help="restrict to one doc_slug")
    args = parser.parse_args()

    records = json.loads(_OUTPUT_JSON.read_text(encoding="utf-8"))["results"]
    if args.doc:
        records = [r for r in records if r["doc_slug"] == args.doc]

    number_tolerant = args.rule == "number-tolerant"
    per_doc = []
    for record in records:
        per_doc.append(compare(record, number_tolerant))
        d = per_doc[-1]
        rate = d["match_rate_plausible"]
        rate_s = f"{rate:.0%}" if rate is not None else "  n/a"
        print(f"{d['doc_slug']:<55} {d['legacy_method']:<10} toc={str(d['toc_detected']):<5} "
              f"entries={d['entry_count']:>3} plausible={d['plausible_count']:>3} "
              f"rate={rate_s:>6} nodes {d['legacy_nodes']:>4}->{d['combined_nodes']:>4} "
              f"issues {d['legacy_issues']:>3}->{d['toc_issues']:>3} "
              f"slug_kept={d['slug_preserved']}/{d['legacy_nodes']}")

    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    _RESULTS_PATH.write_text(json.dumps({"rule": args.rule, "per_doc": per_doc}, indent=2),
                             encoding="utf-8")
    print(f"\nWrote {_RESULTS_PATH}")


if __name__ == "__main__":
    main()
