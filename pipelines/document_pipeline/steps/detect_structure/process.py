#!/usr/bin/env python3
"""Step: detect_structure — turn each document's extracted pages into a
chapter/section tree.

Reads only `extract_pages`'s JSON; it never opens a PDF. That boundary is the
whole point: every heuristic here is a pure function over span dicts, so the
tests run in milliseconds against hand-written page fixtures instead of
against a rendered document.

Detection is a cascade of strategies, best evidence first — the PDF's own
outline, then heading numbering (`1 First Chapter`, `1.1 Introduction`), then
a font-size hierarchy, then a flat one-node-per-page fallback. Whichever
fires is recorded per document as `detection_method` alongside a per-node
`confidence`, so a weakly-detected tree is visible in the data rather than an
invisible assumption baked into the published site.

A document that falls all the way through to `flat` is **not** an error: it is
published with `detection_method: "flat"` so the web repo can badge it. It
does get an informational `LowConfidenceStructure` entry in errors.json so it
surfaces in triage.

`override.json` in this step's own directory is the hand-correction escape
hatch, keyed by doc_slug:

    {"fixture-doc": [{"slug": "1-1-introduction", "title": "Corrected title"}]}

Each entry is a partial node record matched by `slug`, merged over the
detected tree. The slug is the node's identity — retitling a node never
changes its slug, so a correction cannot break a published URL. An override
naming a slug that detection no longer produces is logged as
`UnknownOverrideSlug` rather than silently doing nothing. (This is a
node-level override and is unrelated to `IncrementalWriter`'s record-level
`override_path`, which replaces whole output records.)

Ported from pdf2site's plan (source plan Tasks 7 and 8, lines 1974-2845): the
line grouping, the four strategies, and the override merge. Adapted to keep
the pure functions in this step's own process.py rather than a shared
`lib/structure.py`, to loop over documents, to reuse `documents.SLUG_RE`
rather than introduce a second slugifier, to derive `end_page` from the next
*same-or-higher-level* node (the source plan used the next node at any level,
which makes a chapter end where its own first section starts), and to make
the flat fallback a logged-but-published outcome instead of a hard error.
"""
import argparse
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from documents import SLUG_RE
from lib.cli_utils import add_doc_arg
from lib.file_utils import IncrementalWriter, append_error, read_json, write_json, write_status

STEP_NAME = "detect_structure"
OVERRIDE_FILENAME = "override.json"

# `1 First Chapter`, `1.1 Introduction`, `1.1.1 Detail` — at most three levels,
# at most two digits per level, and always a non-empty title after the number.
HEADING_RE = re.compile(r"^(\d{1,2})(?:\.(\d{1,2}))?(?:\.(\d{1,2}))?\s+(\S.*)$")
NUMBER_PREFIX_RE = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,2})[.\s]+(\S.*)$")
_BOLD_RE = re.compile(r"bold|black|heavy|semib|\bhebo\b|\bcobo\b|\btibo\b", re.IGNORECASE)
_NON_SLUG_RE = re.compile(r"[^a-z0-9]+")

CONFIDENCE = {"outline": 1.0, "numbering": 0.9, "font": 0.6, "flat": 0.2}

# A heading is short and is not a sentence. Both guards exist because body
# prose regularly starts with a number ("2.4 million trips are made each day.")
# and would otherwise be promoted to a heading.
MAX_TITLE_CHARS = 120
MAX_SENTENCE_WORDS = 4

# Fields an override.json entry may set. `slug` is the match key, not a value.
OVERRIDE_FIELDS = {"level", "number", "title", "start_page", "start_y", "end_page",
                   "confidence", "parent", "order"}


# --------------------------------------------------------------------------
# Lines: spans grouped into lines, and the document's body style
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Line:
    text: str
    size: float
    font: str
    bbox: tuple
    block: int
    index: int
    page: int

    @property
    def y0(self) -> float:
        return self.bbox[1]


def is_bold(font) -> bool:
    return bool(_BOLD_RE.search(font or ""))


def page_lines(page: dict) -> list:
    """Group a page's spans into lines, in reading order.

    A line's size and font come from its largest span, so a line that starts
    with a small bullet or footnote marker is still classified by the type it
    is mostly set in.
    """
    grouped = {}
    order = []
    for span in page.get("spans", []):
        key = (span.get("block", 0), span.get("line", 0))
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(span)

    result = []
    for key in order:
        spans = sorted(grouped[key], key=lambda s: s.get("span", 0))
        text = "".join(s["text"] for s in spans).strip()
        if not text:
            continue
        biggest = max(spans, key=lambda s: (s["size"], len(s["text"].strip())))
        result.append(Line(
            text=text,
            size=round(float(biggest["size"]), 1),
            font=biggest["font"],
            bbox=(min(s["bbox"][0] for s in spans),
                  min(s["bbox"][1] for s in spans),
                  max(s["bbox"][2] for s in spans),
                  max(s["bbox"][3] for s in spans)),
            block=key[0],
            index=key[1],
            page=page["number"],
        ))
    return result


def style_histogram(pages: list) -> Counter:
    """Character-weighted (size, font) histogram.

    Weighting by characters rather than by line matters: a document has few
    heading lines but they can be long, and a run of short headings would
    otherwise outvote the prose it labels.
    """
    hist = Counter()
    for page in pages:
        for span in page.get("spans", []):
            weight = len(span["text"].strip())
            if weight:
                hist[(round(float(span["size"]), 1), span["font"])] += weight
    return hist


def body_size(pages: list) -> float:
    hist = style_histogram(pages)
    if not hist:
        return 10.0
    (size, _font), _count = hist.most_common(1)[0]
    return size


def heading_levels(pages: list, body: float, max_levels: int = 3) -> dict:
    """Map font size -> heading level, largest first. A style has to be
    meaningfully bigger than body text to count; +0.5pt filters out the
    sub-point wobble in a mixed font stack."""
    sizes = sorted({size for (size, _font) in style_histogram(pages) if size > body + 0.5},
                   reverse=True)[:max_levels]
    return {size: level for level, size in enumerate(sizes, start=1)}


# --------------------------------------------------------------------------
# Nodes
# --------------------------------------------------------------------------

@dataclass
class Node:
    level: int
    number: object
    title: str
    slug: str
    start_page: int
    start_y: float
    end_page: int = 0
    confidence: float = 0.0
    parent: object = None
    order: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def slugify(text: str) -> str:
    """Slug for a heading, retaining its number: `1.1 Introduction` becomes
    `1-1-introduction`. Validated against documents.SLUG_RE — the same pattern
    doc_slugs must satisfy — because these slugs become published URL
    segments."""
    slug = _NON_SLUG_RE.sub("-", str(text).lower()).strip("-")
    if not slug or not SLUG_RE.match(slug):
        slug = _NON_SLUG_RE.sub("-", str(text).encode("ascii", "ignore").decode().lower()).strip("-")
    return slug or "section"


def _make(level, number, title, page, y, confidence) -> Node:
    title = str(title).strip()
    slug_source = f"{number} {title}" if number else title
    return Node(level=int(level), number=number, title=title, slug=slugify(slug_source),
                start_page=int(page), start_y=round(float(y), 2), confidence=confidence)


def _split_number(text: str):
    match = NUMBER_PREFIX_RE.match(text.strip())
    if match:
        return match.group(1), match.group(2).strip()
    return None, text.strip()


def _looks_like_a_sentence(title: str) -> bool:
    return title.endswith(".") and len(title.split()) > MAX_SENTENCE_WORDS


# --------------------------------------------------------------------------
# Strategies
# --------------------------------------------------------------------------

def from_outline(outline: list) -> list:
    nodes = []
    for entry in outline or []:
        number, title = _split_number(str(entry.get("title", "")))
        if not title:
            continue
        nodes.append(_make(entry.get("level", 1), number, title, entry.get("page", 1),
                           entry.get("y") or 0.0, CONFIDENCE["outline"]))
    return nodes


def from_numbering(pages: list, body: float) -> list:
    """Headings of the form `1 Chapter` / `1.1 Section`, filtered by type size.

    The size guard is what keeps prose out: `2.4 million trips are made each
    day.` matches the pattern perfectly and is only rejected because it is set
    at body size and not bold.
    """
    nodes = []
    for page in pages:
        for line in page_lines(page):
            match = HEADING_RE.match(line.text)
            if not match:
                continue
            if line.size < body * 1.05 and not is_bold(line.font):
                continue
            title = match.group(4).strip()
            if len(title) > MAX_TITLE_CHARS or _looks_like_a_sentence(title):
                continue
            parts = [g for g in match.groups()[:3] if g]
            nodes.append(_make(len(parts), ".".join(parts), title, line.page, line.y0,
                               CONFIDENCE["numbering"]))
    return nodes


def from_font_hierarchy(pages: list, body: float) -> list:
    levels = heading_levels(pages, body)
    if not levels:
        return []
    nodes = []
    for page in pages:
        for line in page_lines(page):
            level = levels.get(line.size)
            if level is None or len(line.text) > MAX_TITLE_CHARS:
                continue
            number, title = _split_number(line.text)
            nodes.append(_make(level, number, title, line.page, line.y0, CONFIDENCE["font"]))
    return nodes


def flat_fallback(page_numbers: list) -> list:
    return [Node(level=1, number=None, title=f"Page {number}", slug=f"page-{number:03d}",
                 start_page=int(number), start_y=0.0, confidence=CONFIDENCE["flat"])
            for number in page_numbers]


# --------------------------------------------------------------------------
# Tree assembly
# --------------------------------------------------------------------------

def _in_document_order(nodes: list) -> list:
    return sorted(nodes, key=lambda n: (n.start_page, n.start_y, n.level))


def dedupe_slugs(nodes: list) -> list:
    """Give repeated slugs a `-2`, `-3` … suffix, in document order.

    A heading really can repeat — `1.1 Introduction` continued onto the next
    page, or the same section title used in two chapters — and the slug is the
    published URL segment, so collisions have to be resolved rather than
    silently overwriting each other.
    """
    seen = {}
    for node in nodes:
        count = seen.get(node.slug, 0) + 1
        seen[node.slug] = count
        if count > 1:
            candidate = f"{node.slug}-{count}"
            while candidate in seen:
                count += 1
                candidate = f"{node.slug}-{count}"
            seen[node.slug] = count
            seen[candidate] = 1
            node.slug = candidate
    return nodes


def assign_hierarchy(nodes: list) -> list:
    """Set `parent` and `order` from levels and heading numbers."""
    ordered = _in_document_order(nodes)
    stack = []
    chapter_index, section_index = 0, 0
    used_orders = set()
    for node in ordered:
        while stack and stack[-1].level >= node.level:
            stack.pop()
        node.parent = stack[-1].slug if stack else None
        stack.append(node)

        parts = str(node.number).split(".") if node.number else []
        numeric = [int(p) for p in parts] if parts and all(p.isdigit() for p in parts) else []
        if numeric:
            order = numeric[0] * 100 + (numeric[1] if len(numeric) > 1 else 0)
        else:
            if node.level == 1:
                chapter_index += 1
                section_index = 0
            else:
                section_index += 1
            order = max(chapter_index, 1) * 100 + section_index
        while order in used_orders:
            order += 1
        used_orders.add(order)
        node.order = order
    return ordered


def assign_page_ranges(nodes: list, page_count: int) -> list:
    """A node ends on the page before the next same-or-higher-level node
    starts; the last such node ends on the document's last page.

    Same-or-higher-level, not next-node-at-any-level: a chapter must not end
    where its own first section begins.
    """
    ordered = _in_document_order(nodes)
    last_page = int(page_count or (ordered[-1].start_page if ordered else 1))
    for index, node in enumerate(ordered):
        following = next((n for n in ordered[index + 1:] if n.level <= node.level), None)
        end = last_page if following is None else following.start_page - 1
        node.end_page = max(int(end), node.start_page)
    return ordered


def detect_structure(pages: list, outline=None, page_count=None):
    """Return (nodes, detection_method) for one document's pages.

    Strategies are tried best-evidence-first. A strategy has to find at least
    two nodes to be believed: a single heading is as likely to be a cover
    title as a chapter.
    """
    if outline:
        nodes, method = from_outline(outline), "outline"
    else:
        body = body_size(pages)
        nodes, method = from_numbering(pages, body), "numbering"
        if len(nodes) < 2:
            nodes, method = from_font_hierarchy(pages, body), "font"
        if len(nodes) < 2:
            nodes, method = flat_fallback([p["number"] for p in pages]), "flat"

    total = int(page_count or len(pages))
    nodes = dedupe_slugs(_in_document_order(nodes))
    nodes = assign_hierarchy(nodes)
    return assign_page_ranges(nodes, total), method


def merge_overrides(nodes: list, patches: list, page_count=None):
    """Merge a document's override.json entries over its detected tree.

    Returns (nodes, errors). Matching is by slug and the slug itself is never
    rewritten, so a correction cannot change a published URL. Fields the
    override sets explicitly win over anything recomputed afterwards, which is
    what makes a hand-set `parent` or `end_page` stick.
    """
    errors = []
    indexed = {node.slug: node for node in nodes}
    applied = {}

    for patch in patches or []:
        if not isinstance(patch, dict):
            errors.append(_error("MalformedOverride",
                                 f"override entry is not an object: {patch!r}", {}))
            continue
        slug = patch.get("slug")
        if not slug:
            errors.append(_error("MalformedOverride",
                                 "override entry has no 'slug' to match on",
                                 {"entry": json.dumps(patch, ensure_ascii=False)[:200]}))
            continue
        unknown = sorted(set(patch) - OVERRIDE_FIELDS - {"slug"})
        if unknown:
            errors.append(_error("MalformedOverride",
                                 f"override for {slug!r} sets unknown field(s): {unknown}",
                                 {"slug": slug}))
            continue
        if slug not in indexed:
            errors.append(_error(
                "UnknownOverrideSlug",
                f"override targets slug {slug!r}, which detection did not produce; "
                "the heading may have been renamed or the detection method changed",
                {"slug": slug}))
            continue
        values = {k: v for k, v in patch.items() if k != "slug"}
        indexed[slug] = replace(indexed[slug], **values)
        applied[slug] = values

    merged = list(indexed.values())
    if applied:
        # Recompute the derived fields so a moved or re-levelled node still has
        # consistent parents and page ranges, then re-apply the explicit values
        # on top so a hand-set derived field is not immediately clobbered.
        merged = dedupe_slugs(_in_document_order(merged))
        merged = assign_hierarchy(merged)
        merged = assign_page_ranges(merged, page_count or max(
            (n.end_page for n in merged), default=len(merged)))
        indexed = {node.slug: node for node in merged}
        for slug, values in applied.items():
            if slug in indexed:
                for key, value in values.items():
                    setattr(indexed[slug], key, value)
    return merged, errors


def _error(error_type: str, message: str, context: dict) -> dict:
    return {"error_type": error_type, "error_message": message, "context": context}


# --------------------------------------------------------------------------
# Step
# --------------------------------------------------------------------------

def load_pages(pages_base_dir: Path, record: dict) -> list:
    """Read a document's per-page JSON sidecars, in page order."""
    pages = []
    for entry in sorted(record.get("pages", []), key=lambda e: e["number"]):
        pages.append(read_json(Path(pages_base_dir) / entry["file"]))
    return pages


def load_overrides(step_dir) -> dict:
    path = Path(step_dir) / OVERRIDE_FILENAME
    if not path.exists():
        return {}
    overrides = read_json(path)
    if not isinstance(overrides, dict):
        raise ValueError(f"{path} must be an object keyed by doc_slug")
    return overrides


def process(upstream_records, pages_base_dir, step_dir, writer, doc_slug=None,
            overrides=None, verbose=False):
    """Detect a chapter/section tree for every document in upstream_records."""
    step_dir = Path(step_dir)
    pages_base_dir = Path(pages_base_dir)
    write_json(step_dir / "errors.json", [])
    if overrides is None:
        overrides = load_overrides(step_dir)

    documents = upstream_records
    if doc_slug is not None:
        documents = [r for r in documents if r["doc_slug"] == doc_slug]

    for record in documents:
        slug = record["doc_slug"]
        if writer.is_processed(slug):
            continue
        if verbose:
            print(f"  {record.get('doc_title') or slug} ...", end=" ", flush=True)

        pages = load_pages(pages_base_dir, record)
        page_count = int(record.get("page_count") or len(pages))
        nodes, method = detect_structure(pages, record.get("outline"), page_count)

        patches = overrides.get(slug) or []
        overridden = False
        if patches:
            nodes, problems = merge_overrides(nodes, patches, page_count)
            overridden = len(problems) < len(patches)
            for problem in problems:
                append_error(step_dir, {
                    "step": STEP_NAME,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error_type": problem["error_type"],
                    "error_message": problem["error_message"],
                    "context": {"doc_slug": slug, **problem["context"]},
                })

        if method == "flat":
            # Not a failure — the document still publishes — but a human should
            # look at it, so it goes in errors.json for triage alongside the
            # real failures.
            append_error(step_dir, {
                "step": STEP_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": "LowConfidenceStructure",
                "error_message": ("No outline, heading numbering or font hierarchy found; "
                                  "fell back to one section per page. Correct it by hand in "
                                  f"{OVERRIDE_FILENAME}."),
                "context": {"doc_slug": slug, "detection_method": method,
                            "page_count": page_count},
            })

        writer.append([{
            "doc_slug": slug,
            "detection_method": method,
            "overridden": overridden,
            "page_count": page_count,
            "nodes": [node.to_dict() for node in nodes],
        }])
        if verbose:
            print(f"[{method}] {len(nodes)} node(s)", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Detect each document's chapter/section tree from its extracted pages")
    parser.add_argument("--input", required=True, help="Path to extract_pages/output.json")
    parser.add_argument("--output", default=None, help="Path to write output.json")
    parser.add_argument("--force", action="store_true", help="Re-detect every document")
    parser.add_argument("--verbose", action="store_true", help="Print progress")
    add_doc_arg(parser)
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output) if args.output else step_dir / "output.json"

    input_path = Path(args.input)
    upstream_records = read_json(input_path).get("results", [])
    pages_base_dir = input_path.parent

    writer = IncrementalWriter(output_path, STEP_NAME, key_field="doc_slug",
                               force=args.force, target_key=args.doc)
    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")

    process(upstream_records, pages_base_dir, step_dir, writer,
            doc_slug=args.doc, verbose=args.verbose)

    count = writer.finalize()
    write_status(step_dir, count)
    print(f"Wrote {count} of {len(upstream_records)} document structure record(s) "
          f"to {output_path}")


if __name__ == "__main__":
    main()
