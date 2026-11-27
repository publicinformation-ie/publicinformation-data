# Design

## Context

See `proposal.md` for motivation. What shapes the approach:

**Repository conventions this must fit.** Pipelines are step directories under `pipelines/<name>/steps/<step>/` (each with `process.py` + `README.md`), ordered by `pipeline.json`, run by `src/lib/pipeline_runner.py`, and triaged through a `status.py`. Steps write `output.json` and `errors.json`; manually-verified records live in `override.json` files as committed source of truth. Publishing follows the minutes pipeline: a pipeline export step writes canonical `output.json`, then a `scripts/transform_*.py` builds the versioned dataset and mirrors `public/latest/`, stamping `dct:modified` only when content changed (`src/lib/dataset_publish.py`).

**Reusable primitives already in `src/lib`.** `table_structure` (label-free structural scorer), `continuation_rows`, `table_utils` (header detection/repair), `value_kinds` (typed cell roles), `text_utils.normalize_cell`, `body_refs` (permanent public-body slugs), `dataset_publish`. The FOI `extract_disclosures_*` steps are *not* reusable: their canonical columns are FOI-specific (`foi_reference_id`, `decision_status`, requester types).

**What the source documents are.** Five PDFs, 2022–2026, ~5,060 project rows total (1,039 / 1,154 / 917 / 945 / 1,009). Every page yields a clean three-column table with `pdfplumber`'s default extraction; no page is image-only, so no OCR is needed. Row vocabulary is small and closed: `Project Code` column header, `Table A: <recipient>` section title, recipient-name heading rows, `Allocations Through Other NTA Funding Streams` divider, `Subtotal:` / `Total:` / `Totals:` / `Total` anchors, `* …` footnotes, and project rows. Recipients are 30 local-authority sections plus one non-local-authority block.

**Three source properties the design leans on.** (a) Each authority section closes with a declared total, so extraction can be checked against the document's own arithmetic. (b) Project codes recur across years (~420 codes in 2024, 2025 and 2026), giving a real time series. (c) 15–40% of rows per year print provisional codes (`WCC/26/XXXX`, `DCC/25/00xx`) that repeat within a section and are explicitly "to be assigned".

## Goals / Non-Goals

**Goals**

- Deterministic, resumable ingestion of the five editions with no per-document hand-mapping on the happy path.
- Every published record traces to a document, page and printed row, and every published section is arithmetically confirmed.
- A small, actionable review queue instead of a large fuzzy-match queue.
- Same maintenance surface as existing pipelines: `pipeline.json`, `status.py`, step READMEs, tests, generated docs.

**Non-Goals**

- Revision history. A reissued PDF replaces figures on the next run.
- OCR. A document that arrives image-only is an error for a human, not a silent empty extraction.
- Cross-year project entity resolution beyond code equality — no fuzzy name matching between years.
- Public-body linkage for non-local-authority recipients.
- TII greenway project lists, and body-level columns (2026's BSEP column) that have no project-level counterpart.

## Decisions

### 1. A new pipeline, reusing library primitives rather than step chains

A new `pipelines/activetravel_pipeline/`, importing `src/lib` primitives. Alternatives considered: extending `foi_pipeline` (its canonicalisation chain is FOI-shaped and would need an override entry per document, which is the same work as writing a classifier but with worse readability); treating these as `document_pipeline` inputs (that pipeline produces per-section prose for reading, not structured records); a generic grants pipeline (deferred — the record shape below is deliberately compatible with one).

### 2. Committed publication list; digests recorded, not pinned

`steps/fetch_grant_documents/publications.json` declares each year: publication page, document URL, and document kind (`project_table`, `recipient_summary`, `programme_summary`). No crawling, no year inference from page text. Each run records the observed sha256 for every fetched document in `output.json`, and the digest is published on each record. A reissue therefore shows up as a digest change in the run output and a public data diff, without a hard failure. *Alternative rejected:* pinning expected checksums in committed config — because a reissue is explicitly in scope for the publisher, a pinned digest would block the annual run behind a code change.

### 3. Ten steps

```
fetch_grant_documents      publications.json → cached bytes + digests
        ↓
extract_grant_tables       pdfplumber per page → rows + per-page structural gate
        ↓
classify_grant_rows        every row → exactly one kind, or an error
        ↓
normalize_grant_amounts    project rows + anchors → whole euro, repairs logged
        ↓
segment_funding_streams    rows → stream, bounded by money anchors
        ↓
resolve_recipients         heading + code prefix → recipient (LA or printed name)
        ↓
reconcile_sections         Σ rows == declared anchors; withhold + report on mismatch
        ↓
reconcile_summary          per-recipient totals vs 2025/2026 front table
        ↓
canonicalize_allocations   identity, provisional flags, public_body_id, dedupe
        ↓
export_allocations         canonical records for the publisher + run counts
```

`--doc <document_id>` (already supported by the shared runner) scopes a run to one document, which is the natural unit here; there is no `body_list_step`.

### 4. Row classification, not header detection

The FOI chain detects a header row and maps columns by synonym. Here the column roles are fixed by the document generator and repeated on every page, while *row kinds* vary: a section heading, a divider, an anchor and a footnote all appear in column 0. So classification is row-oriented, matching the closed vocabulary above plus `blank`, and anything unmatched is an `UnknownRowKind` error with the raw cells. A table never reaches the project-row stage just because it has three columns.

### 5. Funding streams are defined by money anchors, not by position

Each block is bounded by its closing anchor: `Subtotal:` closes a sub-block, `Total:` closes the section (or the combined total when a `Subtotal:` precedes it). Rows after a section's `Total:` belong to the next block, even when the divider heading is missing — observed in the 2026 Wicklow section, where the second block's rows continue on a new page with no `Allocations Through Other NTA Funding Streams` row. *Alternative rejected:* segmenting by divider heading and page breaks, which silently mislabels blocks when a divider is absent; here the arithmetic itself decides, and rows that no anchor brackets are an error.

### 6. Recipients attributed from two independent signals

Section heading and project-code prefix must agree. Both maps are committed: `recipient_aliases.json` (canonical local-authority names plus observed variants such as `Dun Loaghaire Rathdown County Council`), and `code_prefixes.json` (`CW` → Carlow, `KCC` → Kildare, `KK` → Kilkenny, `WCC` → Wicklow, `NAAS`/`TUD`/`OPW` → the non-LA block, and so on). Agreement is required because neither signal is sufficient alone: 2022's first page carries Carlow rows before the Carlow heading appears, and 2025/2026 print headings that disagree with the prefix set. A conflict is `RecipientConflict`, and an unmatched heading or prefix is `RecipientUnresolved`; neither is guessed. Recipients inside the non-LA block are recorded by printed name with `public_body` absent.

### 7. Record identity separates real codes from provisional ones

`id = <recipient_slug>/<year>/<stream>/<key>`, published as `@id` under `https://data.publicinformation.ie/allocation/`. `key` is the lowercased project code when the code is real, and the slugified project name when the code is provisional (`XXXX`/`00xx` or any placeholder pattern). Duplicate keys within one recipient/year/stream gain `-2`, `-3` in document order, which keeps ids stable across re-runs because document order is deterministic. The provisional flag is published so consumers can tell a stable code from a placeholder.

### 8. Amount normalisation validates the number, it does not harvest one

Accept `€`, thousands separators and incidental internal whitespace as formatting (`€ 2 0,000,000` → `20000000`); require the residue to be digits with consistent three-digit grouping. Reject any cell containing letters (the six 2022 name-overflow cells such as `ection€60,000`), a bare `-`, emptiness, or ambiguous grouping, as `UnreadableAmount`. Every cell whose printed text was changed to obtain the value is reported as a repair with raw and used values — normalisation is visible, never silent.

### 9. Withholding is section-level, and overrides are the escape hatch

A row that cannot be published makes its section's arithmetic fail, so the section is withheld entirely and the run reports the delta. That gives one guarantee instead of a partial one: **anything published is complete for its recipient, year and stream, and adds up.** The cost is coverage when a row is genuinely bad — recovered through `row_repairs.json` (committed, `source_method: manual`, one entry per document + page + row with the corrected value and a reason), the same override discipline used elsewhere. Applied repairs are reported as `RowRepairApplied` so the correction stays visible in the run.

### 10. The summary check applies only where the summary is per recipient

2025 and 2026 front matter list a total per recipient; those are compared with the extracted `active_travel` section totals, and 2026's separate BSEP column is excluded (no project-level counterpart). 2022's separate annex is a *programme* budget view — €289.0m across A3.1–A3.4 by GDA/regional/rural split — which does not correspond to the €387.8m sum of its project-table totals. It is declared `kind: programme_summary` and deliberately **not** used as a check; building that comparison would produce a permanent false failure. 2023 and 2024 ship no summary.

### 11. Published record shape

| Field | Notes |
|---|---|
| `@id` | `…/allocation/<recipient_slug>/<year>/<stream>/<key>` |
| `@type` | `ata:Allocation`, context inline in the JSON-LD document |
| `year` | from the committed list |
| `public_body`, `public_body_id` | local authorities only; resolved via `body_refs` slug lookup |
| `recipient_name` | as printed, always present |
| `funding_stream` | `active_travel` or `other_nta_streams` |
| `project_code` | as printed |
| `project_code_provisional` | boolean |
| `project_name` | as printed |
| `allocation_eur` | non-negative integer euro |
| `source_document_url`, `source_document_sha256`, `source_page` | provenance, 1-based page |

Distribution files: `active-travel-allocations.jsonld`, `.csv`, `.csv-metadata.json`, `README.md` under `public/v1.0.0/active-travel-allocations/`, mirrored to `public/latest/active-travel-allocations/`; catalogue entry `public/catalog/dataset-active-travel-allocations.ttl`; schema `public/schemas/active-travel-allocations.schema.json`.

### 12. Error taxonomy

| Type | Raised when | Effect |
|---|---|---|
| `DocumentFetchError` | a declared document is unreachable and uncached | no records from it |
| `PageHasNoText` | a page yields no text layer | no records from it |
| `TableStructureUnreliable` | a page fails the structural checks | no records from that page |
| `UnknownRowKind` | a row matches no known kind | row withheld |
| `UnreadableAmount` | amount cell is not a valid whole-euro figure | row withheld |
| `UnbracketedBlock` | project rows are outside any anchored block | rows withheld |
| `RecipientConflict` | heading and code prefix disagree | row withheld |
| `RecipientUnresolved` | neither signal resolves | row withheld |
| `SectionReconciliationMismatch` | section rows ≠ declared anchors | whole section withheld |
| `SummaryMismatch` | section total ≠ per-recipient summary | whole section withheld |
| `RowRepairApplied` | a committed repair was used | informational, recorded |

## Risks / Trade-offs

- **Section-level withholding lowers first-run coverage.** → Expected: exploration already identified a bounded set (2022 name-overflow cells, 2024 South Dublin's duplicated block sequence, the 2024 non-LA block €1.75m short, Waterford's €1 difference). Triage with `status.py`, add repairs only where a human has confirmed the source value.
- **A layout change in a future edition fails closed and yields nothing.** → Deliberate: a failed gate is a review task, not silent misparsing. The classifier's closed vocabulary makes the failure legible (which kind didn't match).
- **Provisional-code identity is name-based and can drift if a name is edited.** → Accepted: the dataset is allocation-level, not a project registry; only real codes join across years, and that is documented in the README.
- **Reissued PDFs overwrite figures with no revision history.** → Accepted per scope; `source_document_sha256` on every record makes the issue identifiable, and merging is what publishes, so the `public/` diff is the control point.
- **Amount repairs could merge digits wrongly.** → The validator requires consistent grouping and rejects letters, so a name-overflow cell fails rather than being harvested; ambiguity is an error, not a guess.
- **`Table A:` titles and recipient headings appear inconsistently** (missing on a section's first page, repeated mid-page, misspelled). → Both signals plus anchors must agree before a row is published; none alone is trusted.

## Migration Plan

New dataset, nothing to migrate. Sequence: land pipeline + tests → run scoped per document, triage errors → run whole → add confirmed repairs → run publish script → review `public/` diff and `CHANGELOG.md` entry → merge (Pages deployment publishes). Rollback is a commit revert: `public/latest/` and the versioned directory return to their previous content on the next Pages deploy.

## Open Questions

- Whether per-recipient totals deserve their own distribution later (they are currently reconciliation inputs, not published figures).
- Whether a `projects` entity should be introduced once more than five years of codes exist, so renamed projects can be followed.
- Whether 2026's BSEP column should become a body-level allocation distribution of its own.
