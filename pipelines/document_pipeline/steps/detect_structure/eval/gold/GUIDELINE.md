# Gold chapter-list guideline

This file is the rulebook for `steps/detect_structure/eval/gold/<doc_slug>.json`. It exists so that the
same document annotated twice gives the same answer, and so that a second reader can check an
annotation without guessing at the annotator's intent. Read it before adding or reviewing a gold file.

The gold list is the **right answer** for one question only: *what are this document's chapters, and
on which PDF page does each begin?* It is not a description of the detector's output, and it is never
copied from `parse_toc`, `detect_structure`, or `output.json`.

## What a gold file records

```json
{
  "doc_slug": "national-roads-2040-final-report",
  "pdf_sha256": "…64 hex chars, from fetch_pdfs output…",
  "toc_pdf_pages": [3, 4],
  "annotator": "…who checked every entry against the page images…",
  "annotated_on": "2026-11-23",
  "reviewed": true,
  "notes": "",
  "chapters": [
    {"title": "Executive Summary", "printed_page": "v", "pdf_page": 5},
    {"title": "Introduction", "printed_page": "1", "pdf_page": 11}
  ]
}
```

- `pdf_sha256` is the source PDF's `source_sha256` in `steps/fetch_pdfs/output.json`. If it does not
  match the PDF being scored, page numbers may be stale and the report excludes the document.
- `toc_pdf_pages` lists the PDF pages of the **first contents listing**, 1-indexed.
- `reviewed` is `true` only after a person has looked at the rendered contents page(s) and every
  chapter's rendered start page. The annotation helper writes drafts with `reviewed: false`; the
  report excludes drafts.
- `notes` records every judgement call: a heading missing from the body, an inserted map that shifts
  the page offset, a TOC that contradicts the body, anything a second reader would wonder about.

## Rules

**R1 — The printed table of contents is the definition of "chapter".**
Use the top level of the document's **first** contents listing, in TOC order. A document with no
printed contents listing gets no gold file; it goes in `gold/no_toc.json` with a one-line reason
(see "Documents without a printed TOC" below). A document whose TOC is only a per-part list, a list of
figures/tables/maps, or a single "Contents" page with no entries is also "no printed TOC". A List of
Figures, Tables or Maps is a secondary listing, not a chapter, even when it is printed at the top
level. A glossary, an acronym list or an abbreviations list *is* a top-level section and is a chapter
when the TOC prints it at the top level.

**R1a — A separately-titled report bound into the same PDF is a chapter of the bundle.**
Some files are composites: after the document's own last chapter, one or more separately-authored
reports (an SEA Environmental Report, a Natura Impact Statement, …) are bound into the same PDF,
with their own title pages and restarted pagination, and the document's printed contents does not
list them. When a human review establishes that (a FOLLOWUPS issue, a publication decision), each
bound-in report is a gold chapter: copy the report's own title from its title page, record the title
page as `pdf_page`, and record `printed_page: null` — the report's restarted numbering is not the
document's. Say in `notes` that they are bound-in reports and who decided. The detector is not
changed — it stays TOC-faithful by R1 — so such chapters are supplied by hand via
`steps/detect_structure/override.json`, and such a document legitimately scores lower raw than
post-override.

**R2 — "Top level" is decided by the TOC's typography, in this order:**
1. indentation (an entry indented under another is not top level);
2. numbering depth (`1` is top level, `1.1` is not; `Appendix A` at the same indent as `1` is top
   level, `Appendix A.1` is not);
3. weight/size (where indentation and numbering tie, the heavier/larger style is top level);
4. background shading / rules (some contents pages mark chapter rows with a shaded band or rule where
   indentation and weight are identical — the shaded rows are the top level).

When a TOC lists `Appendices` as one top-level line with `Appendix A`…`Appendix F` indented beneath
it, the gold file has **one** `Appendices` chapter. When the appendices are printed at the same
indentation as numbered chapters, **each appendix is its own chapter**.

**R3 — Copy the title exactly as the TOC prints it, without its number.**
`3 Long Term Strategic Issues for National Roads` → `Long Term Strategic Issues for National Roads`.
`Appendix A National Policy Actions for National Roads` → `National Policy Actions for National
Roads` (the label `Appendix A` is the number). Keep the TOC's own spelling, capitalisation and
punctuation, including a typo the publisher made: gold records the source, not a corrected version.
A title wrapped over two lines in the TOC is one title; join it with a single space.

A decorative bar is design, not text: `Chapter 1 | Purpose` → `Purpose`, `Appendix C | Mitigation and
Monitoring Measures` → `Mitigation and Monitoring Measures`, and a short sector code is the chapter's
number: `RE | Research and Innovation` → `Research and Innovation`.

**R4 — `pdf_page` is where the chapter starts in the body, read off the rendered page.**
It is 1-indexed and counts the PDF's pages, not the printed page numbers. Never compute it as
`printed_page` plus a remembered offset — check it on the image. `printed_page` is recorded as a
cross-check, as printed (a string, because front matter uses roman numerals), or `null` when the TOC
prints no number.

When a chapter opens with a **full-page divider** that carries its number and title, the divider is
the chapter start — record the divider page, even if it prints no folio. If the chapter has no
divider, record the page where the heading is set. Do not skip a divider to the first page of prose:
that is a different (later) page and would drift the offset for every following chapter.

**R5 — A TOC entry whose heading is missing from the body still gets a chapter.**
Place it at the page its printed number points to (verified against the surrounding body pages), and
say so in `notes`. Do not drop it: the TOC is the definition, and a dropped entry silently improves
every detector's recall.

**R6 — Front matter is never annotated.**
Pages before the first gold chapter are front matter for scoring purposes. That includes a cover, a
foreword, and the contents pages themselves. Exception: the TOC itself lists front matter such as
`Executive Summary` or `Foreword` as a top-level entry — then it *is* the first gold chapter, at the
PDF page where that item appears in the body.

**R7 — Chapters are non-decreasing by page.**
The report rejects a gold file whose `pdf_page` values decrease. If the body genuinely repeats a
chapter start (it should not), record the reason in `notes` and check the document by hand; do not
reorder the TOC to make the file pass.

**R8 — Two chapters may not share a `pdf_page` unless the document really does start both there.**
The report warns on a shared page. Either correct the page or explain it in `notes` (for example, two
chapter openers printed side by side on one spread).

## Documents without a printed TOC

`gold/no_toc.json` is a register of documents that have no printed contents listing:

```json
{
  "executive-summary-only-example": "No contents page; the document is a single two-page letter.",
  "untitled-example": "Contents page present but it lists only figures; no chapter headings printed."
}
```

Adding an entry requires looking at the document's first pages — not a parser result. The report
lists these documents as "not scorable: no printed TOC" so they are never mistaken for missing gold.

## Worked example — `national-roads-2040-final-report`

Its first contents listing is on PDF pages 3–4. Typographically the numbered chapters and the
appendices share one indent level, and each appendix is printed at that level, so each one is a
chapter. `Executive Summary` is also printed at the top level, so it is the first chapter (R6).
Section lines such as `2.1 Project Ireland 2040` are indented and numbered one level deeper, so they
are not chapters (R2).

Excerpt of the gold file (`chapters` abridged; the real file has all twelve entries):

```json
{
  "doc_slug": "national-roads-2040-final-report",
  "toc_pdf_pages": [3, 4],
  "reviewed": true,
  "chapters": [
    {"title": "Executive Summary", "printed_page": "v", "pdf_page": 5},
    {"title": "Introduction", "printed_page": "1", "pdf_page": 11},
    {"title": "Policy Context", "printed_page": "4", "pdf_page": 14},
    {"title": "Long Term Strategic Issues for National Roads", "printed_page": "11", "pdf_page": 21},
    {"title": "National Policy Actions for National Roads", "printed_page": "46", "pdf_page": 56}
  ]
}
```

Things this example demonstrates:

- `Executive Summary` is printed on roman page `v`, which is PDF page 5 — not page 5 of the arabic
  sequence. The roman and arabic offsets differ, which is normal and not a consistency warning.
- `Long Term Strategic Issues for National Roads` is wrapped over two TOC lines and joined (R3).
- `Appendix A` is printed at the same indent as `1`, so it is a chapter, and its label is dropped
  from the title (R2, R3).
- Chapters printed `1`, `4`, `11`, `46` start on PDF pages `11`, `14`, `21`, `56`: a constant offset
  of 10. Glossary (`76`) → PDF `86` continues it. The consistency check expects exactly this.

## Automatic consistency checks

Every report run checks each gold file and prints warnings. A warning does not stop the document
being scored; it is a prompt to look again. Clear it by correcting the file, or by explaining it in
`notes`:

- the **page-offset** check looks for the word "offset" (e.g. "divider pages are not counted, so the
  offset grows");
- the **shared-page** check looks for "same page", "shared page", "spread" or "side by side";
- the **title** check clears when `notes` names the title, or says the title is set as "artwork" /
  "graphic" / "image", or that the page's "text layer" is garbled.

1. **Page-offset jump.** Among the arabic-numbered entries, the offset `pdf_page - printed_page`
   should be constant. A change warns unless `notes` mentions an offset change.
2. **Title not on its start page.** The normalised title should appear in that page's extracted text
   layer. A title split across a line break, set inside an image, or printed as a graphic warns.
3. **Shared start page.** Two chapters on the same `pdf_page` warn unless `notes` explains it.

## Re-annotation (gold repeatability, optional)

Gold quality cannot be checked against a second annotator. The report can instead score one gold
file against another (`--compare-gold`), so the same annotator can re-annotate blind at a later date
and see exactly where the two readings disagree. This is **optional**: the initial corpus was reviewed
without it, by maintainer decision on 2026-11-22, and the capability remains available.

If you run it:

1. At least a week after the first annotation, re-annotate two documents into a scratch file
   (gitignored), **without opening the committed gold file**. Use one ambiguous TOC
   (`national-cycle-network-plan`) and one ordinary document
   (`all-island-strategic-rail-review-final-report`).
2. Compare with `score.py --compare-gold <committed> <scratch>`.
3. Resolve every disagreement: a new rule here, a corrected gold file, or a recorded ambiguity in
   `notes`. Record the resulting agreement figures below.

The agreement is the noise floor for reading detector scores: a detector change smaller than the
gold's own disagreement on that kind of document is not evidence of improvement.

<!-- Append re-annotation results below, most recent first. -->
