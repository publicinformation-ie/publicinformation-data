"""Gold chapter lists: loading, validation and consistency checks.

A gold file is the hand-authored answer to "what are this document's chapters
and where does each start?" (see `gold/GUIDELINE.md`). This module owns the
parts that must not vary between runs:

* what a valid gold file looks like (`validate_gold`), so a typo is an explicit
  error rather than a quietly-scored document;
* which documents are deliberately unscorable (`gold/no_toc.json`);
* the consistency warnings that catch transcription slips (page-offset jumps,
  a title that is not on the page it claims, two chapters on one page).

It never reads detector output. The report (`score.py`) is the caller.
"""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

GOLD_DIR = Path(__file__).parent / "gold"
NO_TOC_FILENAME = "no_toc.json"

REQUIRED_FIELDS = ("doc_slug", "pdf_sha256", "toc_pdf_pages", "annotator",
                   "annotated_on", "reviewed", "chapters")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_DIGITS_RE = re.compile(r"^\d{1,4}$")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")

# A leading chapter number: `3 `, `3.1 `, `IV.`, `Chapter 4:`, `Appendix A `.
# The roman-numeral alternative is case-sensitive on purpose: with IGNORECASE
# it would strip the first syllable of an ordinary word ("Civil Rights").
_LEADING_NUMBER_RE = re.compile(
    r"^(?:(?i:chapter|section|appendix|annex|part|book|schedule)\s+"
    r"(?:\d{1,3}(?:\.\d{1,3})*|[IVXLCDM]{1,7}|[A-Z])"
    r"|(?:\d{1,3}(?:\.\d{1,3})*|[IVXLCDM]{1,7})"
    r"|[A-Z]{1,3}\s*\|)"
    r"(?=$|[\s.:\u2013\u2014\-|])"
    r"[\s.:\u2013\u2014\-|]*"
)
_TRAILING_PUNCT_RE = re.compile(r"[\s.,;:!?\u2026\u2013\u2014\-]+$")
_SHARED_PAGE_NOTE_RE = re.compile(r"same page|shared page|spread|side by side", re.I)
# A note explaining that a chapter title cannot be found in the text layer:
# it is set as artwork, or the page's text layer is garbled/missing.
_TEXT_LAYER_NOTE_RE = re.compile(r"artwork|graphic|set as (?:an )?image|garbled|text layer",
                                 re.I)


def strip_leading_number(text) -> str:
    """Remove a leading chapter label (`3`, `3.1`, `Chapter 4:`, `Appendix A`)."""
    value = _CONTROL_RE.sub(" ", str(text or ""))
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"^[|\s]+", "", value)   # decorative TOC bar, not text
    return _LEADING_NUMBER_RE.sub("", value).strip()


def normalise_title(text) -> str:
    """Canonical title form for comparison and for the "is it on this page" check.

    Case-folded, whitespace collapsed, control characters removed, a leading
    chapter number (`3`, `3.1`, `Chapter 4:`, `Appendix A`) stripped, and
    trailing punctuation removed. The gold TOC wording is the reference; the
    same function is applied to both sides so a printed number can never make
    an otherwise correct title fail.
    """
    value = _CONTROL_RE.sub(" ", str(text or ""))
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"^[|\s]+", "", value)   # decorative TOC bar, not text
    value = _LEADING_NUMBER_RE.sub("", value)
    value = _TRAILING_PUNCT_RE.sub("", value)
    return value.casefold().strip()


def normalise_page_text(text) -> str:
    """Canonical page text for the "is this title on its start page" check."""
    value = _CONTROL_RE.sub(" ", str(text or ""))
    return re.sub(r"\s+", " ", value).strip().casefold()


def page_text(page: dict) -> str:
    """Join a page's spans into text, in stored order.

    Detection reads spans, not the PDF, so the same spans are the honest
    evidence for "the heading is printed on this page".
    """
    return " ".join(str(span.get("text") or "") for span in page.get("spans") or [])


@dataclass
class GoldDocument:
    doc_slug: str
    pdf_sha256: str
    toc_pdf_pages: list
    reviewed: bool
    chapters: list
    annotator: str = ""
    annotated_on: str = ""
    notes: str = ""
    warnings: list = field(default_factory=list)

    def chapter_titles(self) -> list:
        return [chapter["title"] for chapter in self.chapters]


@dataclass
class GoldLoad:
    """Outcome of loading a gold directory: scorable files and exclusions."""

    documents: dict = field(default_factory=dict)   # doc_slug -> GoldDocument
    excluded: list = field(default_factory=list)    # {doc_slug, reason, detail}

    def exclude(self, doc_slug: str, reason: str, detail: str = "") -> None:
        self.excluded.append({"doc_slug": doc_slug, "reason": reason, "detail": detail})


def validate_gold(data, expected_slug=None) -> list:
    """Return a list of validation error strings; empty means valid."""
    errors = []
    if not isinstance(data, dict):
        return ["gold file must be a JSON object"]

    for key in REQUIRED_FIELDS:
        if key not in data:
            errors.append(f"missing required field {key!r}")
    if errors:
        return errors

    slug = data["doc_slug"]
    if not isinstance(slug, str) or not slug:
        errors.append("doc_slug must be a non-empty string")
    elif expected_slug is not None and slug != expected_slug:
        errors.append(f"doc_slug {slug!r} does not match filename {expected_slug!r}")

    sha = data["pdf_sha256"]
    if not isinstance(sha, str) or not _SHA256_RE.match(sha):
        errors.append("pdf_sha256 must be 64 lowercase hex characters")

    toc_pages = data["toc_pdf_pages"]
    if (not isinstance(toc_pages, list) or not toc_pages
            or not all(isinstance(p, int) and not isinstance(p, bool) and p >= 1
                       for p in toc_pages)):
        errors.append("toc_pdf_pages must be a non-empty list of 1-indexed integers")

    if not isinstance(data["reviewed"], bool):
        errors.append("reviewed must be true or false")
    for key in ("annotator", "annotated_on", "notes"):
        if not isinstance(data[key], str):
            errors.append(f"{key} must be a string")

    chapters = data["chapters"]
    if not isinstance(chapters, list) or not chapters:
        errors.append("chapters must be a non-empty list")
        return errors

    previous_page = None
    for index, chapter in enumerate(chapters, start=1):
        where = f"chapter {index}"
        if not isinstance(chapter, dict):
            errors.append(f"{where} must be an object")
            continue
        title = chapter.get("title")
        if not isinstance(title, str) or not title.strip():
            errors.append(f"{where} needs a non-empty 'title'")
        elif not normalise_title(title):
            errors.append(f"{where} title {title!r} is only a number")
        if "printed_page" not in chapter:
            errors.append(f"{where} needs 'printed_page' (null when the TOC prints none)")
        else:
            printed = chapter["printed_page"]
            if printed is not None and not isinstance(printed, str):
                errors.append(f"{where} printed_page must be a string or null")
        page = chapter.get("pdf_page")
        if not isinstance(page, int) or isinstance(page, bool) or page < 1:
            errors.append(f"{where} needs a positive integer 'pdf_page'")
            continue
        if previous_page is not None and page < previous_page:
            errors.append(
                f"{where} pdf_page {page} is before the previous chapter's page {previous_page} "
                "(chapters must be non-decreasing in TOC order)")
        previous_page = page

    return errors


def load_no_toc(gold_dir=GOLD_DIR) -> dict:
    """`doc_slug` -> reason, for documents with no printed contents listing."""
    path = Path(gold_dir) / NO_TOC_FILENAME
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be an object of doc_slug -> reason")
    bad = [slug for slug, reason in data.items()
           if not isinstance(slug, str) or not isinstance(reason, str) or not reason.strip()]
    if bad:
        raise ValueError(f"{path} has entries without a one-line reason: {bad}")
    return data


def load_gold(gold_dir=GOLD_DIR) -> GoldLoad:
    """Load, validate and classify every gold file in `gold_dir`.

    A file with validation errors, or with `reviewed` not true, is recorded as
    excluded rather than scored. The no-TOC register is merged in last, so a
    document is never listed twice.
    """
    gold_dir = Path(gold_dir)
    loaded = GoldLoad()
    seen = set()

    for path in sorted(gold_dir.glob("*.json")):
        if path.name == NO_TOC_FILENAME:
            continue
        slug_from_name = path.stem
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            loaded.exclude(slug_from_name, "malformed gold file", f"invalid JSON: {exc}")
            continue

        errors = validate_gold(data, expected_slug=slug_from_name)
        if errors:
            loaded.exclude(slug_from_name, "malformed gold file", "; ".join(errors))
            continue
        seen.add(data["doc_slug"])
        if data["reviewed"] is not True:
            loaded.exclude(data["doc_slug"], "unreviewed",
                           "annotation draft (reviewed is not true)")
            continue
        loaded.documents[data["doc_slug"]] = GoldDocument(
            doc_slug=data["doc_slug"],
            pdf_sha256=data["pdf_sha256"],
            toc_pdf_pages=list(data["toc_pdf_pages"]),
            reviewed=True,
            chapters=[dict(chapter) for chapter in data["chapters"]],
            annotator=data["annotator"],
            annotated_on=data["annotated_on"],
            notes=data["notes"],
        )

    for slug, reason in sorted(load_no_toc(gold_dir).items()):
        if slug in seen:
            raise ValueError(
                f"{slug!r} has a gold file and an entry in {NO_TOC_FILENAME}; "
                "one document cannot be both scorable and unscorable")
        loaded.exclude(slug, "no printed TOC", reason)
    return loaded


def consistency_warnings(gold: GoldDocument, pages: list) -> list:
    """Likely transcription slips in one gold file.

    `pages` is the document's pages in snapshot/live form (each `{number, spans}`).
    Warnings never stop scoring; they are prompts to look again. Each is
    cleared by correcting the file or by explaining it in `notes` (the wording
    that clears it is given in the message).
    """
    warnings = []
    notes = gold.notes or ""
    notes_folded = notes.casefold()
    texts = {int(page["number"]): normalise_page_text(page_text(page))
             for page in pages if page.get("number") is not None}

    # 1. The printed-to-PDF offset should hold across the arabic-numbered
    #    entries. Roman front matter has its own offset and is skipped.
    previous = None
    for chapter in gold.chapters:
        printed = chapter.get("printed_page")
        if not isinstance(printed, str) or not _DIGITS_RE.match(printed.strip()):
            continue
        offset = int(chapter["pdf_page"]) - int(printed.strip())
        if previous is not None and offset != previous[0] and "offset" not in notes_folded:
            warnings.append(
                f"page offset changes from {previous[0]} to {offset} at "
                f"{chapter['title']!r} (printed {printed}, PDF {chapter['pdf_page']}); "
                "correct it or explain the offset change in notes")
        previous = (offset, chapter["title"])

    # 2. Each title should be printed on its claimed start page.
    for chapter in gold.chapters:
        text = texts.get(int(chapter["pdf_page"]))
        want = normalise_title(chapter["title"])
        if not want:
            continue
        if text is not None and want in text:
            continue
        if want and want in normalise_page_text(notes):
            continue  # explained: e.g. the heading is set as a graphic
        if _TEXT_LAYER_NOTE_RE.search(notes):
            continue  # explained: artwork heading / garbled page text layer
        where = "is beyond the document" if text is None else "is not in its text layer"
        warnings.append(
            f"{chapter['title']!r} {where} on PDF page {chapter['pdf_page']}; "
            "check the page, or explain it in notes (name the title, or say the title is "
            "artwork / the text layer is garbled)")

    # 3. Two chapters starting on one page is possible but usually a slip.
    by_page = {}
    for chapter in gold.chapters:
        by_page.setdefault(int(chapter["pdf_page"]), []).append(chapter["title"])
    for page, titles in sorted(by_page.items()):
        if len(titles) < 2:
            continue
        if _SHARED_PAGE_NOTE_RE.search(notes):
            continue
        warnings.append(
            f"{len(titles)} chapters share PDF page {page} ({', '.join(map(repr, titles))}); "
            "correct the pages, or explain the shared page in notes")

    gold.warnings = warnings
    return warnings
