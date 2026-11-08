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
# Up to four levels (1.2.3.4). The lookahead stops a deeper number being split
# mid-number into a digit-led title (`11.7.2` + `1 Craft…`).
NUMBER_PREFIX_RE = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,3})(?!\.?\d)(?:[.\s]+|(?=[A-Z][a-z]))(\S.*)$")
_BOLD_RE = re.compile(r"bold|black|heavy|semib|\bhebo\b|\bcobo\b|\btibo\b", re.IGNORECASE)
_NON_SLUG_RE = re.compile(r"[^a-z0-9]+")

CONFIDENCE = {"outline": 1.0, "numbering": 0.9, "font": 0.6, "flat": 0.2}
# The TOC-name strategy sits between numbering (0.9) and outline (1.0): its
# headings are canonical (from the document's own table of contents), but the
# body occurrence is still an inference, so it is not as certain as outline.
CONFIDENCE["toc"] = 0.95

# A heading is short and is not a sentence. Both guards exist because body
# prose regularly starts with a number ("2.4 million trips are made each day.")
# and would otherwise be promoted to a heading.
MAX_TITLE_CHARS = 120
MAX_SENTENCE_WORDS = 4

# --------------------------------------------------------------------------
# TOC-name strategy constants. Thresholds were pinned by the 2026-10-17
# experiment (pipelines/document_pipeline/experiments/2026-10-17-toc-splitting-comparison).
# --------------------------------------------------------------------------

TOC_TITLES = {"contents", "table of contents"}
DOT_LEADER_RE = re.compile(r"\.{4,}|\u2026")
_LIST_OF_RE = re.compile(r"^list of (figures|tables|maps|boxes|photographs|appendices|abbreviations)")
FURNITURE_TITLES = {
    "abbreviations", "abbreviation", "glossary", "glossary of terms",
    "list of figures", "list of tables", "list of maps", "list of boxes",
    "list of photographs", "list of appendices", "index", "contents",
    "table of contents", "bibliography",
}

RUNNING_HEADER_FRACTION = 0.25  # a line on >=25% of pages is a running header
MATCH_RATE_GATE = 0.60          # min share of plausible entries matched to fire
SCORE_FLOOR = 1.05              # body-size multiplier; below this and not bold is rejected
ISOLATION_BONUS = 0.3           # reward an occurrence flanked by body-sized text
RIGHT_COLUMN_MIN_X_FRACTION = 0.5  # a bare number this far right is a page number
# A wrapped heading's continuation line sits below the first at a baseline
# pitch of at most this multiple of the heading's own type size (a tight
# pitch is ~1.1-1.3x). Lines on one baseline (pitch ~0, i.e. separate columns)
# and lines further apart than this are never joined.
HEADING_JOIN_MAX_GAP = 1.6
# A bookmark title is matched against at most this many wrapped lines.
OUTLINE_TITLE_MAX_LINES = 4
HEADING_JOIN_MIN_GAP = 0.5      # below this pitch, two lines share a baseline
# A heading can be emitted as two spans grouped into two "lines" on one
# baseline (`Appendix C |` + `Mitigation and Monitoring Measures`): the second
# starts within this many points of where the first ends. A wider gap is a
# column gutter, not a wrapped heading.
SAME_LINE_SPAN_GAP = 6.0
# Reading order rounds a line's y0 to this many points before comparing, so
# lines on one visual baseline (differing by sub-point noise) sort left to
# right. Too coarse and a two-column page interleaves; too fine and noise
# reorders a single visual line.
READING_ORDER_Y_GRID = 3.0

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
    # Text of the line's first span. A running header is often a constant
    # lead ("National Sustainable Mobility Policy | ") followed by a span that
    # changes per page, so the whole line never repeats but the lead does.
    lead: str = ""

    @property
    def y0(self) -> float:
        return self.bbox[1]


def is_bold(font) -> bool:
    return bool(_BOLD_RE.search(font or ""))


def page_lines(page: dict) -> list:
    """Group a page's spans into lines, in the extractor's raw span order.

    Other steps (`clean_text`, `extract_figures`) share this function and rely
    on that order — `clean_text` even uses out-of-y-order spans within a block
    as its suspect-reading-order signal — so it deliberately does not sort.
    Detection strategies use `reading_order_lines` instead.

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
            lead=spans[0]["text"],
        ))
    return result


def reading_order_lines(page: dict) -> list:
    """A page's lines in reading order: top to bottom, then left to right.

    Sorted by `(round(y0 / READING_ORDER_Y_GRID), x0, block, line)`. The
    extractor's raw span order can put a footer page number before the running
    header and a page title after all the body text. The grid rounds y so that
    lines on one visual baseline sort by x rather than by sub-point noise.
    Every detection strategy consumes lines through this function.
    """
    return sorted(page_lines(page),
                  key=lambda l: (round(l.y0 / READING_ORDER_Y_GRID), l.bbox[0], l.block, l.index))


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


def running_header_texts(pages: list, fraction: float = RUNNING_HEADER_FRACTION) -> set:
    """Normalized texts of lines appearing on >= `fraction` of pages. Running
    headers and footers repeat identically on most pages, so a TOC entry whose
    title collides with one must not be promoted to a boundary."""
    count = Counter()
    total = len(pages)
    for page in pages:
        for line in reading_order_lines(page):
            norm = normalize_heading_text(line.text)
            if len(norm) >= 4:
                count[norm] += 1
    # n >= 2: a line seen on a single page is not repeating, however short the
    # document (on a one-page input every line would otherwise be 100%).
    return {text for text, n in count.items() if n >= 2 and n / max(total, 1) >= fraction}


def running_header_leads(pages: list, fraction: float = RUNNING_HEADER_FRACTION) -> set:
    """Normalized first-span texts that repeat on >= `fraction` of pages (and
    on at least two). A running header such as `National Sustainable Mobility
    Policy | <section name>` carries a constant lead span and a span that
    changes per page, so the whole line never repeats while the lead does.
    Counted once per page."""
    count = Counter()
    for page in pages:
        leads = {normalize_heading_text(line.lead) for line in reading_order_lines(page)}
        for lead in leads:
            if len(lead) >= 4:
                count[lead] += 1
    total = max(len(pages), 1)
    return {lead for lead, n in count.items() if n >= 2 and n / total >= fraction}


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
    title = clean_title(title)
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


def normalize_heading_text(text) -> str:
    """Canonical form for TOC/body comparison: strip control characters
    (extraction artifacts like ``\\x07``/``\\x08``), collapse whitespace
    (folding thin spaces such as U+2009), lowercase, and trim trailing
    punctuation/dots including the Unicode ellipsis ``…``."""
    t = re.sub(r"[\x00-\x1f\x7f]", " ", str(text))
    t = re.sub(r"\s+", " ", t).strip().lower()
    return t.rstrip(".,;:!?\u2026 \t")


_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
# A leading pipe fragment (`| Investing in Transport`) or a dash glued straight
# onto a letter (`-Moving`). A dash followed by a space is a bullet, which
# `is_heading_candidate` rejects; stripping it first would launder a bullet
# line into a passing title.
_LEADING_FRAGMENT_RE = re.compile(r"^(?:[\s|]+|[-\u2013\u2014](?=[^\W\d_]))")


def clean_title(text) -> str:
    """Remove extraction artifacts from a title or slug source: control
    characters (`\\x07`), whitespace runs, and a leading pipe/glued-dash
    fragment. It does **not** strip dot leaders — a line carrying them is a
    table-of-contents line, and `is_heading_candidate` must still see the
    leaders to reject it (the TOC entry path strips them itself, via
    `_strip_toc_suffix`, because there they are the expected shape)."""
    t = _CONTROL_RE.sub(" ", str(text))
    t = re.sub(r"\s+", " ", t).strip()
    return _LEADING_FRAGMENT_RE.sub("", t).strip()


def is_heading_candidate(title) -> bool:
    """A title that can plausibly be a heading: it has letters, is neither a
    single character nor over-long, and carries no dot leaders, bullets, or a
    leading currency symbol. Used by both `validate_split` and the TOC parse."""
    t = str(title).strip()
    if not t or not re.search(r"[a-zA-Z]", t):
        return False
    if len(t) == 1 or len(t) > MAX_TITLE_CHARS:
        return False
    if DOT_LEADER_RE.search(t):
        return False
    if re.match(r"^[\u2022\u00b7\-\u2013\u2014\*\u25cf\u25aa]\s", t):
        return False
    if re.match(r"^[\u20ac\u00a3$]", t):
        return False
    return True


# --------------------------------------------------------------------------
# Strategies
# --------------------------------------------------------------------------

_WORD_AUTO_BOOKMARK_RE = re.compile(r"^_(?:Hlk|Toc|Ref|GoBack)\w*$", re.I)


def filter_outline(outline):
    """Drop bookmarks that have no usable title.

    A bookmark is unusable when its title is empty, has no letters (`1.`), is
    a Word auto-bookmark (`_Hlk25760943`), or otherwise fails
    `is_heading_candidate`. Each drop is reported as `OutlineEntryDropped`
    so a reviewer can see exactly what was removed; nothing is renamed.

    Returns `(kept, problems)`.
    """
    kept, problems = [], []
    for entry in outline or []:
        raw = str(entry.get("title", ""))
        title = clean_title(raw)
        if _WORD_AUTO_BOOKMARK_RE.match(title) or not is_heading_candidate(title):
            problems.append({
                "error_type": "OutlineEntryDropped",
                "error_message": f"Outline bookmark {raw!r} (page {entry.get('page')}) has no usable title and was dropped",
                "context": {"title": raw, "page": entry.get("page")},
            })
            continue
        kept.append(entry)
    return kept, problems


def _line_key(page_no: int, line) -> tuple:
    """Identity of a line for the `used` set. Includes x so two column headings
    on one baseline are distinct lines."""
    return (page_no, round(line.y0, 1), round(line.bbox[0]))


def _find_title_line(page_no: int, page, want: str, used: set, min_size=None):
    """The unclaimed line on `page` whose text, alone or joined with up to
    OUTLINE_TITLE_MAX_LINES - 1 wrapped continuation lines, normalizes to
    exactly `want`; None if there is none. Partial matches never count. With
    `min_size`, the first line must also be larger than that and pass
    `is_heading_candidate` (the previous-page fallback's guard against a short
    title exactly matching a body-text line)."""
    if page is None or not want:
        return None
    lines = reading_order_lines(page)
    for line in lines:
        if _line_key(page_no, line) in used:
            continue
        if min_size is not None and (line.size <= min_size or not is_heading_candidate(clean_title(line.text))):
            continue
        _, text = _split_number(clean_title(line.text))
        joined = text
        current = line
        for _ in range(OUTLINE_TITLE_MAX_LINES):
            got = normalize_heading_text(joined)
            if got == want:
                return line
            if len(got) < 3 or not want.startswith(got):
                break
            nxt = _heading_continuation(current, lines)
            if nxt is None:
                break
            current = lines[nxt]
            # A continuation line is title text even when it starts with a
            # number (`13.7 metres in length`), so it is not number-split.
            joined = f"{joined} {clean_title(current.text)}"
    return None


def resolve_outline_positions(outline, pages: list):
    """Fill in `y` for outline entries that name only a page.

    Many PDF bookmarks point at a page, not a position on it, so every entry on
    a page would otherwise start at y=0 and the sections between them could not
    be separated. For each such entry, find the line on that page whose text is
    the entry's title, joined with up to OUTLINE_TITLE_MAX_LINES - 1 wrapped
    continuation lines (a differently sized running header between them is
    skipped), and use that line's top. Some producers (InDesign `/Fit`
    destinations) point one page after the heading; only when the title has no
    exact match on the stated page is the previous page tried, under the same
    exact-match rule and only for a line larger than the body size (so a short
    title cannot match body text), and a match there moves the entry's `page`. An entry
    whose title cannot be located is left unchanged and reported, never
    guessed; the validation gate then flags the tree.

    Returns `(outline, problems)`; problems are `OutlineEntryUnresolved` dicts.
    """
    if not outline:
        return outline, []
    by_page = {int(p.get("number", i + 1)): p for i, p in enumerate(pages)}
    used, resolved, problems = set(), [], []
    for entry in outline:
        if entry.get("y"):
            resolved.append(entry)
            continue
        page_no = int(entry.get("page", 1))
        _, title = _split_number(str(entry.get("title", "")))
        want = normalize_heading_text(clean_title(title))
        found_page = page_no
        found = _find_title_line(page_no, by_page.get(page_no), want, used)
        if found is None and page_no > 1:
            found_page = page_no - 1
            found = _find_title_line(found_page, by_page.get(found_page), want, used,
                                     min_size=body_size(pages))
        if found is None:
            resolved.append(entry)
            problems.append({
                "error_type": "OutlineEntryUnresolved",
                "error_message": f"Outline entry {entry.get('title')!r} (page {page_no}) names no position and its title was not found on the page; left at the page top",
                "context": {"title": entry.get("title"), "page": page_no},
            })
            continue
        used.add(_line_key(found_page, found))
        resolved.append({**entry, "page": found_page, "y": found.y0})
    return resolved, problems


def from_outline(outline: list) -> list:
    nodes = []
    for entry in outline or []:
        number, title = _split_number(str(entry.get("title", "")))
        if not title:
            continue
        nodes.append(_make(entry.get("level", 1), number, title, entry.get("page", 1),
                           entry.get("y") or 0.0, CONFIDENCE["outline"]))
    return nodes


def _heading_continuation(line: Line, lines: list):
    """Index in `lines` of the line that continues a wrapped heading, or None.

    A continuation shares the heading's rounded type size and bold class, sits
    directly below it (horizontal overlap, baseline pitch within
    HEADING_JOIN_MIN_GAP..HEADING_JOIN_MAX_GAP type sizes), and the heading
    line does not end a sentence. Chosen by position, not by reading-order
    adjacency: on a two-column page the line after a column-one line in
    reading order is the column-two line on the same baseline.
    """
    if line.text.rstrip().endswith((".", "!", "?")):
        return None
    best, best_pitch = None, None
    for index, other in enumerate(lines):
        if other is line or other.size != line.size or is_bold(other.font) != is_bold(line.font):
            continue
        pitch = other.y0 - line.y0
        if not (HEADING_JOIN_MIN_GAP * line.size <= pitch <= HEADING_JOIN_MAX_GAP * line.size):
            continue
        if min(line.bbox[2], other.bbox[2]) - max(line.bbox[0], other.bbox[0]) <= 0:
            continue
        if best_pitch is None or pitch < best_pitch:
            best, best_pitch = index, pitch
    return best


def from_numbering(pages: list, body: float, skip_pages=frozenset()) -> list:
    """Headings of the form `1 Chapter` / `1.1 Section`, filtered by type size.
    Pages in `skip_pages` (the detected TOC pages) contribute no candidates: a
    table-of-contents line is never a body heading.

    The size guard is what keeps prose out: `2.4 million trips are made each
    day.` matches the pattern perfectly and is only rejected because it is set
    at body size and not bold.
    """
    nodes = []
    for page in pages:
        if page["number"] in skip_pages:
            continue
        lines = reading_order_lines(page)
        for line in lines:
            match = HEADING_RE.match(line.text)
            if not match:
                continue
            if line.size < body * 1.05 and not is_bold(line.font):
                continue
            title = match.group(4)
            follow = _heading_continuation(line, lines)
            if follow is not None and not HEADING_RE.match(lines[follow].text):
                title = f"{title} {lines[follow].text}"
            title = clean_title(title)
            # A lowercase start is a wrapped sentence that happens to begin
            # with a number (`26 weather events. The Q4 ...`), not a heading.
            if (len(title) > MAX_TITLE_CHARS or _looks_like_a_sentence(title)
                    or title[:1].islower() or not is_heading_candidate(title)):
                continue
            parts = [g for g in match.groups()[:3] if g]
            nodes.append(_make(len(parts), ".".join(parts), title, line.page, line.y0,
                               CONFIDENCE["numbering"]))
    return nodes


def from_font_hierarchy(pages: list, body: float, skip_pages=frozenset()) -> list:
    levels = heading_levels(pages, body)
    if not levels:
        return []
    nodes = []
    for page in pages:
        if page["number"] in skip_pages:
            continue
        lines = reading_order_lines(page)
        consumed = set()
        for position, line in enumerate(lines):
            if position in consumed:
                continue
            level = levels.get(line.size)
            if level is None or len(line.text) > MAX_TITLE_CHARS:
                continue
            text = line.text
            follow = _heading_continuation(line, lines)
            if follow is not None:
                consumed.add(follow)
                text = f"{text} {lines[follow].text}"
            number, title = _split_number(clean_title(text))
            title = clean_title(title)
            if not is_heading_candidate(title):
                continue
            nodes.append(_make(level, number, title, line.page, line.y0, CONFIDENCE["font"]))
    return nodes


def flat_fallback(page_numbers: list) -> list:
    return [Node(level=1, number=None, title=f"Page {number}", slug=f"page-{number:03d}",
                 start_page=int(number), start_y=0.0, confidence=CONFIDENCE["flat"])
            for number in page_numbers]


# --------------------------------------------------------------------------
# TOC-name strategy
# --------------------------------------------------------------------------

def _classify_furniture(title) -> bool:
    norm = normalize_heading_text(title)
    return norm in FURNITURE_TITLES or norm.startswith("list of ")


def _page_toc_signals(page: dict, body: float):
    """TOC-page signals for one page: a `contents` title at heading size, a
    `contents` title at any size, dot-leader line count, right-column page
    numbers."""
    lines = reading_order_lines(page)
    width = float(page.get("width") or 595.0)
    title_heading = title_any = False
    for line in lines:
        if normalize_heading_text(line.text) in TOC_TITLES:
            title_any = True
            if line.size >= body + 0.5:
                title_heading = True
    dot_lines = sum(1 for l in lines if DOT_LEADER_RE.search(l.text))
    right_nums = sum(1 for l in lines
                     if re.fullmatch(r"\d{1,3}", l.text.strip())
                     and l.bbox[0] > width * RIGHT_COLUMN_MIN_X_FRACTION)
    return title_heading, title_any, dot_lines, right_nums


def _page_kind(page: dict):
    """Classify a flagged page as 'contents', 'list-of' (furniture), or None."""
    for line in reading_order_lines(page):
        norm = normalize_heading_text(line.text)
        if norm in TOC_TITLES:
            return "contents"
        if _LIST_OF_RE.match(norm):
            return "list-of"
    return None


def _strip_toc_suffix(text: str) -> str:
    """Remove trailing dot leaders and any page number glued to them."""
    t = text.strip()
    t = re.sub(r"[\s.\u2026]+\d{1,3}\s*$", "", t)  # "Title ... 12"
    t = re.sub(r"[\s.\u2026]+$", "", t)             # "Title ......."
    return t.strip()


def _toc_reading_order(page: dict) -> list:
    """A TOC page's lines in column-major reading order: the left column top to
    bottom, then the right column, each row left to right.

    A two-column contents page (emra's, for one) lists chapters down the left
    column and continues down the right; plain row-major order would interleave
    the two columns and turn one chapter line into several entries. A line is
    assigned to a column by its left edge relative to the page's mid-point, so
    a full-width line (a title, a chapter opener) stays in the left column and
    keeps its place in it.
    """
    width = float(page.get("width") or 595.0)
    return sorted(page_lines(page),
                  key=lambda l: (0 if l.bbox[0] < width * RIGHT_COLUMN_MIN_X_FRACTION else 1,
                                 round(l.y0 / READING_ORDER_Y_GRID), l.bbox[0],
                                 l.block, l.index))


def _parse_toc_page(page: dict, running=frozenset(), running_leads=frozenset()):
    """Return (entries, flags) for one TOC page.

    Each entry is {title, number, level_hint, x0, furniture}. Handles the
    entry shapes the experiment documented: separate-line numbers (`1.` on its
    own line), right-hand page-number lines, and inline numbers.

    Lines are consumed in reading order. Collection starts after the
    `contents` title line (anything above it is page furniture); bare page
    numbers are skipped wherever they sit, and so are running-header lines
    (`running` holds whole-line texts, `running_leads` the repeating first-span
    texts). A skipped line creates no entry, so it also contributes no `x0` to
    `_infer_levels`. Lines are read column by column (`_toc_reading_order`).
    """
    lines = _toc_reading_order(page)
    for position, candidate in enumerate(lines):
        if normalize_heading_text(candidate.text) in TOC_TITLES:
            lines = lines[position + 1:]
            break
    width = float(page.get("width") or 595.0)
    entries = []
    flags = {"separate_line_number": False, "right_page_number": False,
             "unicode_dot_leader": False, "ascii_dot_leader": False}

    def _note_leader(raw: str):
        if DOT_LEADER_RE.search(raw):
            if "\u2026" in raw:
                flags["unicode_dot_leader"] = True
            else:
                flags["ascii_dot_leader"] = True

    i = 0
    while i < len(lines):
        line = lines[i]
        text = line.text.strip()
        norm = normalize_heading_text(text)

        if norm in TOC_TITLES:
            i += 1
            continue

        # Running headers/footers are page furniture, not entries.
        if norm in running or normalize_heading_text(line.lead) in running_leads:
            i += 1
            continue

        # A bare page number (`12`, no trailing dot) is a page number wherever
        # it sits: far right is the usual shape, but a footer number sits at
        # the left edge. Dotted numbers (`1.`, `1.1`) stay separate-line
        # section numbers, handled below.
        if re.fullmatch(r"\d{1,3}", text):
            if line.bbox[0] > width * RIGHT_COLUMN_MIN_X_FRACTION:
                flags["right_page_number"] = True
            i += 1
            continue

        # A number on its own line, title on the following line(s).
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
                # Footer/header lines are page furniture, not title lines.
                if (normalize_heading_text(nt) in running
                        or normalize_heading_text(nxt.lead) in running_leads):
                    i += 1
                    continue
                if re.fullmatch(r"\d{1,2}(?:\.\d{1,2}){0,2}\.?", nt) and len(nt) <= 7:
                    break
                title_parts.append(nt)
                i += 1
            raw = " ".join(title_parts)
            title = clean_title(_strip_toc_suffix(raw))
            if title and is_heading_candidate(title):
                _note_leader(raw)
                entries.append({"title": title, "number": number,
                                "level_hint": len(number.split(".")),
                                "x0": round(line.bbox[0], 1),
                                "furniture": _classify_furniture(title)})
            continue

        # Ordinary entry: title, maybe dot leaders, maybe an inline number.
        m = NUMBER_PREFIX_RE.match(text)
        number = None
        if m:
            number = m.group(1)
            text = m.group(2)
        title = clean_title(_strip_toc_suffix(text))
        if title and is_heading_candidate(title):
            _note_leader(text)
            entries.append({"title": title, "number": number,
                            "level_hint": len(number.split(".")) if number else None,
                            "x0": round(line.bbox[0], 1),
                            "furniture": _classify_furniture(title)})
        i += 1
    return entries, flags


def _infer_levels(entries):
    """Infer a level per entry from numbering depth, else indentation, else 1.

    Returns (entries_with_level, signal) where signal is 'numbering', 'indent',
    or 'none'. A missing signal is not a failure: a flat document gets a flat
    level-1 tree, which is correct for it.
    """
    numbered = [e for e in entries if e["number"]]
    if len(numbered) >= 2 and any(e["level_hint"] and e["level_hint"] > 1 for e in numbered):
        return [{**e, "level": e["level_hint"] or 1} for e in entries], "numbering"
    x0s = sorted({e["x0"] for e in entries})
    if len(x0s) >= 2:
        levels = {x0: min(i + 1, 3) for i, x0 in enumerate(x0s[:3])}
        result = []
        for e in entries:
            nearest = min(levels, key=lambda x: abs(x - e["x0"]))
            result.append({**e, "level": levels[nearest]})
        return result, "indent"
    return [{**e, "level": 1} for e in entries], "none"


def parse_toc(pages: list, body: float):
    """Detect the document's main TOC and parse its entries.

    Returns (entries, toc_pages, level_signal, flags). Only the first
    contiguous block of TOC pages is parsed; `list-of-*` pages and later
    part-TOCs are flagged (`multi_toc`, `part_tocs`) but contribute no entries.
    """
    flagged = []
    for page in pages:
        title_heading, title_any, dot_lines, right_nums = _page_toc_signals(page, body)
        if title_heading or dot_lines >= 3 or (title_any and right_nums >= 3):
            flagged.append(page["number"])

    toc_pages = []
    for num in flagged:
        page = next(p for p in pages if p["number"] == num)
        if _page_kind(page) == "list-of":
            continue
        if toc_pages and num != toc_pages[-1] + 1:
            break  # gap: a later part-TOC, not the main one
        toc_pages.append(num)

    flags = {"separate_line_number": False, "right_page_number": False,
             "unicode_dot_leader": False, "ascii_dot_leader": False,
             "multi_toc": False, "title_at_body_size": False, "part_tocs": []}

    running = running_header_texts(pages)
    running_leads = running_header_leads(pages)

    all_entries = []
    for num in toc_pages:
        page = next(p for p in pages if p["number"] == num)
        title_heading, title_any, _, _ = _page_toc_signals(page, body)
        if title_any and not title_heading:
            flags["title_at_body_size"] = True
        entries, page_flags = _parse_toc_page(page, running, running_leads)
        for key in ("separate_line_number", "right_page_number",
                    "unicode_dot_leader", "ascii_dot_leader"):
            flags[key] = flags[key] or page_flags[key]
        all_entries.extend(entries)

    extra = [n for n in flagged if n not in toc_pages]
    if extra:
        flags["multi_toc"] = True
        flags["part_tocs"] = extra

    level_signal = "none"
    if all_entries:
        all_entries, level_signal = _infer_levels(all_entries)

    return all_entries, toc_pages, level_signal, flags


def _column_successors(lines) -> dict:
    """Map a line index to the index of the line that continues it: either the
    rest of the same visual line (the next span at the same baseline, starting
    where this one ends) or the next line below in the same column.

    Not simply the next line in reading order: on a two-column page, the line
    after a column-one line is the column-two line on the same baseline, and
    joining those would sand two headings together while splitting every
    wrapped one.
    """
    successors = {}
    for index, line in enumerate(lines):
        same_line, same_line_gap = None, None
        below, below_y = None, None
        for other_index, other in enumerate(lines):
            if other_index == index:
                continue
            if abs(other.y0 - line.y0) <= HEADING_JOIN_MIN_GAP * line.size:
                gap = other.bbox[0] - line.bbox[2]
                if 0 <= gap <= SAME_LINE_SPAN_GAP and (same_line_gap is None or gap < same_line_gap):
                    same_line, same_line_gap = other_index, gap
                continue
            if other.y0 <= line.y0:
                continue
            if min(line.bbox[2], other.bbox[2]) - max(line.bbox[0], other.bbox[0]) <= 0:
                continue
            if below_y is None or other.y0 < below_y:
                below, below_y = other_index, other.y0
        best = same_line if same_line is not None else below
        if best is not None:
            successors[index] = best
    return successors


def _joined_runs(lines, successors=None):
    """Yield `(line_indices, joined_text)` for one to three lines that follow
    one another down one column."""
    successors = _column_successors(lines) if successors is None else successors
    for start in range(len(lines)):
        indices = (start,)
        yield indices, lines[start].text
        current = start
        while len(indices) < 3 and current in successors:
            current = successors[current]
            indices += (current,)
            yield indices, " ".join(lines[i].text for i in indices)


def build_occurrence_index(pages: list, toc_page_numbers: set, running_headers: set,
                           body: float) -> dict:
    """Map normalized joined text -> occurrence dicts, in one pass over pages.

    Occurrences are the k=1..3 consecutive body lines whose normalized text
    matches a TOC entry, with a deterministic number-prefix alias too. TOC
    pages and running-header lines are excluded here, so they can never be
    selected as a boundary.
    """
    index = {}
    for page in pages:
        if page["number"] in toc_page_numbers:
            continue
        lines = reading_order_lines(page)
        successors = _column_successors(lines)
        predecessors = {target: source for source, target in successors.items()}
        for indices, joined in _joined_runs(lines, successors):
            # Same cleanup the TOC side applies to entry titles, so a body
            # heading `1.1 | Introduction` still meets the entry `Introduction`.
            joined = clean_title(joined)
            norm = normalize_heading_text(joined)
            if norm in running_headers:
                continue
            block = [lines[i] for i in indices]
            prev = lines[predecessors[indices[0]]] if indices[0] in predecessors else None
            nxt = lines[successors[indices[-1]]] if indices[-1] in successors else None
            occ = {
                "page": page["number"],
                "y0": block[0].y0,
                "size": max(l.size for l in block),
                "bold": any(is_bold(l.font) for l in block),
                "isolated": (prev is None or prev.size < body * 1.05)
                            and (nxt is None or nxt.size < body * 1.05),
                "text": joined,
            }
            index.setdefault(norm, []).append(occ)
            number, rest = _split_number(joined)
            if number:
                index.setdefault(normalize_heading_text(clean_title(rest)), []).append(occ)
    return index


def find_occurrences(index: dict, toc_title: str) -> list:
    return index.get(normalize_heading_text(toc_title), [])


def score_occurrence(occ: dict, body: float) -> float:
    """Monotonic size score plus bold and isolation bonuses. Larger relative to
    body scores higher; the level index is deliberately not added (that would
    reward smaller headings). Used to rank occurrences; the accept/reject
    decision is `_below_score_floor`, which keeps the rule separable from the
    ranking."""
    return (occ["size"] / max(body, 0.1)
            + (0.5 if occ["bold"] else 0.0)
            + (ISOLATION_BONUS if occ["isolated"] else 0.0))


def _below_score_floor(occ: dict, body: float) -> bool:
    """True when an occurrence is neither above body size nor bold — the same
    guard `from_numbering` uses to keep prose out."""
    return occ["size"] < body * SCORE_FLOOR and not occ["bold"]


def _supplement_numbered_nodes(pages, body, base_nodes, entries, running_headers,
                               toc_pages=frozenset()):
    """Add legacy numbered headings not already among the base nodes. The font
    strategy is not used — it is the low-precision over-splitter this strategy
    replaces, and re-adding its nodes reintroduces the junk. TOC pages are
    excluded so a TOC line cannot re-enter as a body heading."""
    claimed = {(n.start_page, round(n.start_y, 1)) for n in base_nodes}
    extra = []
    seen = {(normalize_heading_text(n.title), n.start_page) for n in base_nodes}
    for node in from_numbering(pages, body, toc_pages):
        # Skip only a duplicate of a node already present (same title, same
        # page); a title merely listed in the TOC may recur as `N.1 Introduction`.
        if (normalize_heading_text(node.title), node.start_page) in seen:
            continue
        if normalize_heading_text(node.title) in running_headers:
            continue
        key = (node.start_page, round(node.start_y, 1))
        if key in claimed:
            continue
        claimed.add(key)
        extra.append(node)
    return base_nodes + extra


def from_toc(pages: list, body: float, parsed=None):
    """Build the TOC-name tree, or signal fallback.

    Returns (nodes, report). `nodes` is None when the strategy should not fire
    (no usable TOC, or match rate below the gate). `report` is None when there
    is no TOC at all; otherwise it carries the entry/matched counts, the match
    rate, and the errors for errors.json. `parsed` is an optional precomputed
    `parse_toc(pages, body)` result.
    """
    entries, toc_pages, _level_signal, _flags = parsed or parse_toc(pages, body)
    if not entries:
        return None, None

    running = running_header_texts(pages)
    index = build_occurrence_index(pages, set(toc_pages), running, body)
    plausible = [e for e in entries if not e["furniture"]]

    nodes = []
    errors = []
    used = set()
    matched_plausible = 0
    for entry in entries:
        occs = find_occurrences(index, entry["title"])
        if not occs:
            errors.append(_error("TocEntryUnmatched",
                                 f"TOC entry {entry['title']!r} has no body occurrence; "
                                 "no boundary created.", {"title": entry["title"]}))
            continue
        best = max(occs, key=lambda o: (score_occurrence(o, body), o["page"], o["y0"]))
        if _below_score_floor(best, body):
            errors.append(_error("TocEntryNoHeading",
                                 f"TOC entry {entry['title']!r} matched only below the score "
                                 "floor; no boundary created.", {"title": entry["title"]}))
            continue
        key = (best["page"], round(best["y0"], 1))
        if key in used:
            continue
        used.add(key)
        number, title = _split_number(best["text"])
        nodes.append(_make(entry["level"], number, title, best["page"], best["y0"],
                           CONFIDENCE["toc"]))
        if not entry["furniture"]:
            matched_plausible += 1

    match_rate = matched_plausible / len(plausible) if plausible else 0.0
    report = {
        "entry_count": len(entries),
        "matched_count": matched_plausible,
        "match_rate": round(match_rate, 3),
    }

    if match_rate < MATCH_RATE_GATE:
        report["errors"] = [_error(
            "LowTocMatchRate",
            f"TOC match rate {match_rate:.0%} is below the gate "
            f"{MATCH_RATE_GATE:.0%}; fell back to the legacy cascade.",
            {"entry_count": len(entries), "matched_count": matched_plausible,
             "match_rate": round(match_rate, 3), "gate": MATCH_RATE_GATE})]
        return None, report

    nodes = _supplement_numbered_nodes(pages, body, nodes, entries, running, set(toc_pages))
    report["errors"] = errors
    return nodes, report


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


def _legacy_cascade(pages: list, body: float, toc_pages=frozenset()):
    """The pre-TOC cascade: numbering, then font, then flat. Detected TOC pages
    are excluded from both heading strategies."""
    nodes, method = from_numbering(pages, body, toc_pages), "numbering"
    if len(nodes) < 2:
        nodes, method = from_font_hierarchy(pages, body, toc_pages), "font"
    if len(nodes) < 2:
        nodes, method = flat_fallback([p["number"] for p in pages]), "flat"
    return nodes, method


def split_issues(nodes: list, page_count: int) -> list:
    """Structured form of `validate_split`: a list of `{check, value, message}`
    dicts, one per problem, so the production step can record *which* check
    failed and the offending value rather than a free-text string."""
    issues = []
    for node in nodes:
        if not is_heading_candidate(node.title):
            issues.append({"check": "non-heading-title", "value": node.title,
                           "message": f"node {node.slug!r} has a non-heading title {node.title!r}"})
    seen = {}
    for node in nodes:
        key = (node.start_page, round(node.start_y, 1))
        if key in seen:
            issues.append({"check": "duplicate-boundary", "value": [node.slug, seen[key]],
                           "message": f"duplicate boundary {node.slug!r} and {seen[key]!r}"})
        seen[key] = node.slug
    # A tree needs a root a reader can start from. Unconditional: an all-level-2
    # tree has a single level, so a "more than one level" condition would miss
    # exactly that failure. An all-level-1 (flat) tree is valid.
    if nodes and not any(node.level == 1 for node in nodes):
        issues.append({"check": "no-level-1-node",
                       "value": sorted({node.level for node in nodes}),
                       "message": "tree has no level-1 node (levels present: "
                                  f"{sorted({node.level for node in nodes})})"})
    ordered = sorted(nodes, key=lambda n: (n.start_page, n.start_y))
    if not ordered:
        return issues
    covered = set()
    for node in ordered:
        for page in range(node.start_page, node.end_page + 1):
            covered.add(page)
    for page in range(ordered[0].start_page, page_count + 1):
        if page not in covered:
            issues.append({"check": "coverage-gap", "value": page,
                           "message": f"coverage gap at page {page}"})
    return issues


def validate_split(nodes: list, page_count: int) -> list:
    """Return a list of issue strings for a node list.

    A split is valid only when every title passes the heading-candidate guard,
    no two nodes share the same (start_page, start_y) boundary, the node set
    contains at least one level-1 node, and the union of node page ranges
    covers from the first node's start_page through page_count without gaps.
    Pages before the first node are front matter, not a gap.
    """
    return [issue["message"] for issue in split_issues(nodes, page_count)]


def detect_structure(pages: list, outline=None, page_count=None):
    """Return (nodes, detection_method, toc_report) for one document's pages.

    Strategies are tried best-evidence-first: the PDF outline, then the
    TOC-name strategy, then heading numbering, then font hierarchy, then flat.
    A strategy has to find at least two nodes to be believed: a single heading
    is as likely to be a cover title as a chapter. `toc_report` is None unless
    a TOC was detected, in which case it carries the entry/matched counts, the
    match rate, and any TOC errors (see `from_toc`).
    """
    toc_report = None
    if outline:
        nodes, method = from_outline(outline), "outline"
    else:
        body = body_size(pages)
        parsed = parse_toc(pages, body)
        toc_pages = set(parsed[1])
        toc_nodes, toc_report = from_toc(pages, body, parsed)
        if toc_nodes is not None and len(toc_nodes) >= 2:
            nodes, method = toc_nodes, "toc"
        else:
            nodes, method = _legacy_cascade(pages, body, toc_pages)

    total = int(page_count or len(pages))
    nodes = dedupe_slugs(_in_document_order(nodes))
    nodes = assign_hierarchy(nodes)
    return assign_page_ranges(nodes, total), method, toc_report


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
    dropped = False

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
        if "drop" in patch:
            # A node removed by hand: the previous boundary absorbs its text.
            # Used where detection is right but the boundary model cannot
            # represent it (two section headings side by side on one baseline).
            if patch["drop"] is not True or set(patch) != {"slug", "drop"}:
                errors.append(_error(
                    "MalformedOverride",
                    f"override for {slug!r}: 'drop' must be true and the only other field",
                    {"slug": slug}))
                continue
            if slug not in indexed:
                errors.append(_error(
                    "UnknownOverrideSlug",
                    f"override drops slug {slug!r}, which detection did not produce",
                    {"slug": slug}))
                continue
            del indexed[slug]
            applied.pop(slug, None)
            dropped = True
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
    if applied or dropped:
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
        outline, outline_problems = filter_outline(record.get("outline"))
        outline, unresolved = resolve_outline_positions(outline, pages)
        outline_problems += unresolved
        for problem in outline_problems:
            append_error(step_dir, {
                "step": STEP_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": problem["error_type"],
                "error_message": problem["error_message"],
                "context": {"doc_slug": slug, **problem["context"]},
            })
        nodes, method, toc_report = detect_structure(pages, outline, page_count)

        if toc_report is not None:
            for problem in toc_report.get("errors", []):
                append_error(step_dir, {
                    "step": STEP_NAME,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error_type": problem["error_type"],
                    "error_message": problem["error_message"],
                    "context": {"doc_slug": slug, **problem["context"]},
                })

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

        # Validate the tree as it will be written, after overrides. Never alters
        # the tree: a failing document is still written, and the failure is
        # recorded for triage. An unresolved entry is resolved by a code fix or
        # a committed override.json entry, and blocks the merge that publishes.
        for issue in split_issues(nodes, page_count):
            append_error(step_dir, {
                "step": STEP_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": "InvalidStructure",
                "error_message": f"Detected tree fails validation: {issue['message']}",
                "context": {"doc_slug": slug, "check": issue["check"],
                            "value": issue["value"], "detection_method": method},
            })

        if method == "flat":
            # Not a failure — the document still publishes — but a human should
            # look at it, so it goes in errors.json for triage alongside the
            # real failures.
            append_error(step_dir, {
                "step": STEP_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": "LowConfidenceStructure",
                "error_message": ("No outline, TOC, heading numbering or font hierarchy found; "
                                  "fell back to one section per page. Correct it by hand in "
                                  f"{OVERRIDE_FILENAME}."),
                "context": {"doc_slug": slug, "detection_method": method,
                            "page_count": page_count},
            })

        record_out = {
            "doc_slug": slug,
            "detection_method": method,
            "overridden": overridden,
            "page_count": page_count,
            "nodes": [node.to_dict() for node in nodes],
        }
        if toc_report is not None:
            record_out["toc_entry_count"] = toc_report["entry_count"]
            record_out["toc_matched_count"] = toc_report["matched_count"]
            record_out["toc_match_rate"] = toc_report["match_rate"]
        writer.append([record_out])
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
