# document-structure-evaluation Specification

## Purpose
Measures how accurately the document pipeline splits documents into chapters, by scoring the detected chapter list against hand-authored gold chapter lists transcribed from each document's printed table of contents. The goal is that detector improvements and regressions can be quantified.

## Requirements

### Requirement: Chapters are defined by the printed table of contents

A document's gold chapters SHALL be exactly the top-level entries of its main printed table of contents, in TOC order. Entries indented under another entry SHALL NOT be gold chapters. Only the document's first contents listing is used. Later per-part TOCs and lists of tables, figures or maps are ignored. Pages before the first gold chapter are front matter.

#### Scenario: Indented entries are not chapters

- **GIVEN** a TOC that lists `Appendices` at the top level with `Appendix A` to `Appendix F` indented beneath it
- **WHEN** the document is annotated
- **THEN** the gold file has one `Appendices` chapter and no chapter for any individual appendix

#### Scenario: Top-level appendices are chapters

- **GIVEN** a TOC that lists `Appendix A` and `Appendix B` at the same indentation as numbered chapters
- **WHEN** the document is annotated
- **THEN** each appendix is a separate gold chapter

#### Scenario: Secondary listings ignored

- **GIVEN** a document whose contents pages are followed by a List of Figures and, later, a per-part TOC
- **WHEN** the document is annotated
- **THEN** only entries from the first contents listing become gold chapters

### Requirement: Gold chapter-list files

Each gold document SHALL have one committed, hand-authored gold file. It records the doc slug, the source PDF's sha256, the PDF page or pages of its contents listing, the annotator and the annotation date. Each chapter records its title as printed in the TOC, the printed page number, and the 1-indexed PDF page where the chapter starts. A malformed gold file SHALL be reported as an error and not scored.

#### Scenario: Chapter record

- **WHEN** a gold chapter is recorded
- **THEN** it carries `title` (TOC wording), `printed_page` (as printed, possibly null when the TOC prints none) and `pdf_page` (verified on the rendered page)

#### Scenario: Malformed gold file

- **GIVEN** a gold file missing `pdf_sha256`, with a chapter missing `pdf_page`, or with `pdf_page` values that are not non-decreasing
- **WHEN** the report runs
- **THEN** the document is listed as a gold error with the reason and excluded from all scores

### Requirement: Gold is independent of the detector

A gold chapter list SHALL NOT be produced from, or accepted from, the detector's own TOC parsing or output without each entry being checked by a person against the rendered contents page and the rendered chapter start page. The gold file SHALL record that this check was done.

#### Scenario: Pre-filled draft not yet reviewed

- **GIVEN** a gold file whose `reviewed` flag is not `true`
- **WHEN** the report runs
- **THEN** the document is listed as unreviewed and excluded from all scores

### Requirement: Gold consistency checks

Each gold file SHALL be checked for likely transcription errors. Checks are reported as warnings, which do not stop the document being scored: a change in the offset between printed and PDF page numbers with no explaining note; a chapter title not found in the text layer of its `pdf_page`; and two chapters given the same `pdf_page`. A warning is cleared by correcting the file or by recording the reason in `notes`.

#### Scenario: Page offset jump

- **GIVEN** a gold file whose chapters have printed-to-PDF page offsets of 6, 6, 6, then 8, and whose `notes` do not mention it
- **WHEN** the report runs
- **THEN** it warns that the offset changes at the fourth chapter, and still scores the document

#### Scenario: Title not on its start page

- **GIVEN** a gold chapter whose normalised title does not appear in the text layer of its `pdf_page`
- **WHEN** the report runs
- **THEN** it warns, naming the chapter and page, and still scores the document

### Requirement: Gold re-annotation agreement

The report SHALL be able to score one gold file against another gold file for the same document, using the same boundary, page attribution and title metrics as detector scoring. This measures the gold's own repeatability when the single annotator re-annotates a document blind.

#### Scenario: Blind re-annotation compared

- **GIVEN** a committed gold file and a second, independently produced gold file for the same document
- **WHEN** the report is asked to compare them
- **THEN** it prints exact boundary F1, page attribution and title accuracy between the two, and lists every chapter on which they disagree

### Requirement: Documents without a printed table of contents

A document with no printed table of contents SHALL NOT be given a gold file. It SHALL instead be listed in the evaluation's register of documents without a TOC, so the report shows it as unscorable rather than omitting it silently.

#### Scenario: Unscorable document listed

- **GIVEN** a document recorded in the no-TOC register
- **WHEN** the report runs
- **THEN** the report lists it under "not scorable: no printed TOC" and it contributes to no score

### Requirement: Predicted chapters

The report SHALL treat as a predicted chapter every node of the detected tree that has no resolvable parent. This is the same definition the published bundles use. Its start page is the node's `start_page` and its title is the node's title.

#### Scenario: Orphaned section counts as a chapter

- **GIVEN** a detected level-2 node whose parent slug does not exist in the tree
- **WHEN** the report scores the document
- **THEN** that node is scored as a predicted chapter

### Requirement: Boundary matching

Predicted chapters SHALL be matched one-to-one to gold chapters by start page, preserving document order. A predicted chapter matches exactly when its start page equals the gold chapter's `pdf_page`. It matches within tolerance when it is at most one page away. Matching SHALL be deterministic: the same inputs always produce the same pairs.

#### Scenario: Two chapters on one page

- **GIVEN** two gold chapters and two predicted chapters that all start on the same page
- **WHEN** boundaries are matched
- **THEN** they pair in document order, giving two exact matches

#### Scenario: Off by one page

- **GIVEN** a gold chapter on page 20 and a predicted chapter on page 21, with nothing else nearby
- **WHEN** boundaries are matched
- **THEN** the pair is a match within ±1 tolerance and not an exact match

### Requirement: Accuracy metrics

For each scored document, the report SHALL give: chapter boundary precision, recall and F1, both exact and within ±1 page; page attribution accuracy, the share of pages whose predicted chapter is exactly matched to the gold chapter containing that page, with front matter treated as a chapter on both sides; title accuracy over exactly matched pairs; and whether the document is fully correct.

#### Scenario: Over-split document

- **GIVEN** a document with 9 gold chapters, detected with those 9 at the exact pages plus 5 extra chapters
- **WHEN** the report scores it
- **THEN** exact recall is 1.0, exact precision is 9/14, and the document is not fully correct

#### Scenario: Swallowed pages

- **GIVEN** a detected chapter that starts on a real gold chapter's page but runs on through the next 10 gold chapters, because their starts were not detected
- **WHEN** page attribution is computed
- **THEN** pages belonging to the 10 undetected gold chapters count as wrongly attributed

#### Scenario: Fully correct

- **WHEN** every gold chapter has an exact match, there are no unmatched predicted chapters, and every matched title is correct
- **THEN** the document is reported as fully correct

#### Scenario: Title comparison

- **WHEN** an exact-matched pair's titles are compared
- **THEN** they are compared after normalisation: case folded, whitespace collapsed, control characters, leading chapter numbers and trailing punctuation stripped. The gold TOC wording is the reference

### Requirement: Raw and post-override scoring

The report SHALL score every gold document twice: once on the detector's raw tree, and once on the tree after that document's `override.json` entries are applied. Both scores SHALL be reported side by side, so a hand override cannot hide a detector regression.

#### Scenario: Overridden document

- **GIVEN** a gold document that has `override.json` entries
- **WHEN** the report runs
- **THEN** it reports both the raw score and the post-override score, and which of the two the document's published tree reflects

### Requirement: Corpus summary

The report SHALL summarise all scored documents with macro averages (mean of per-document values) and micro averages (pooled boundary and page counts) for each metric. It SHALL also give the count of fully correct documents out of the number scored, and list every excluded document with the reason it was excluded.

#### Scenario: Large document does not dominate macro averages

- **GIVEN** a scored corpus where one document has 1,107 pages and the rest have under 300
- **WHEN** the summary is produced
- **THEN** the macro page attribution accuracy weights each document equally

### Requirement: Committed baseline and diff

The report SHALL produce a machine-readable result alongside its human-readable form. A committed baseline result SHALL be kept. Each run SHALL show, per document and per metric, the change from the baseline. A flag SHALL rewrite the baseline after an intentional change.

#### Scenario: Regression visible

- **GIVEN** a detector change that raises one document's F1 and lowers another's
- **WHEN** the report runs against the committed baseline
- **THEN** both per-document changes are shown, not only the change in the corpus average

### Requirement: Report is read-only and offline

Running the report SHALL NOT modify any pipeline step output, `errors.json`, `override.json`, gold file or published artifact. The only exception is that the baseline is rewritten when explicitly requested. The report SHALL make no network or paid calls.

#### Scenario: Plain run

- **WHEN** the report runs without the baseline flag
- **THEN** no file in the repository is written or changed

### Requirement: Detection snapshot

The report SHALL by default score the committed detection snapshot. The snapshot SHALL cover every document in the corpus, and SHALL record per document a fingerprint of its extracted spans and outline and its source PDF's sha256. A live mode SHALL score the current local `extract_pages` output instead.

#### Scenario: Snapshot runs without local pipeline output

- **GIVEN** a checkout with Git LFS files materialised but no `extract_pages` output
- **WHEN** the report runs in default mode
- **THEN** it scores every reviewed gold document

#### Scenario: Snapshot drift warning

- **GIVEN** local `extract_pages` output whose spans or outline differ from the snapshot for some document
- **WHEN** the report runs
- **THEN** it lists those documents as drifted from the snapshot, and still scores the source it was asked to score

#### Scenario: Gold PDF mismatch

- **GIVEN** a gold file whose `pdf_sha256` differs from the sha256 recorded for the document being scored
- **WHEN** the report runs
- **THEN** that document is excluded and listed as a gold/PDF mismatch, because its page numbers may no longer be valid

### Requirement: Report scores the production detection path

The report SHALL produce each document's raw tree through the same detection entry point that the production step uses. That entry point includes outline filtering, position resolution and entry normalisation. The report SHALL NOT call a narrower function that skips any of these steps. The post-override tree SHALL be produced from that raw tree with the production override merge.

#### Scenario: Outline preparation applied

- **GIVEN** a gold document whose raw outline contains Word auto-bookmarks and entries that point one page after their heading
- **WHEN** the report scores it
- **THEN** the scored tree matches what the production step would write, with the bookmarks removed and the entries moved to their heading pages

### Requirement: Held-out gold documents

A gold file SHALL be able to declare itself held out. The report SHALL summarise held-out documents separately from the other scored documents, with the same macro and micro metrics and the same fully-correct count. Held-out documents SHALL appear in the per-document table, marked as held out, and SHALL be included in the baseline and its diff. A held-out file SHALL meet every rule that applies to other gold files.

#### Scenario: Separate summaries

- **GIVEN** ten reviewed gold documents, four of them marked as held out
- **WHEN** the report runs
- **THEN** it prints one summary for the six tuning documents, one for the four held-out documents, and one for all ten

#### Scenario: Held-out flag absent

- **WHEN** a gold file does not declare itself held out
- **THEN** it is a tuning document

### Requirement: Detector-change results log

Each detector change measured with the report SHALL be recorded in a committed results log. A log entry SHALL name the change and the commit it was measured at. It SHALL give the tuning and held-out corpus summaries before and after the change, and list every per-document metric change from the baseline diff. Every per-document regression SHALL be given a stated reason. The baseline SHALL be refreshed only after the entry is written.

#### Scenario: Regression recorded

- **WHEN** a detector change raises corpus F1 but lowers one document's page attribution
- **THEN** the log entry lists that document's drop and its reason before the baseline is refreshed
