# Public Body Actions Dataset

**Dataset URI:** `https://publicinformation-ie.codeberg.page/publicinformation-data/dataset/public-body-actions`

The published commitments of Irish public bodies and how their reported status changed over time. Covers the Department of Transport's Sustainable Mobility Policy (SMP) corpus — the 2022-2025 action plan, its four progress reports, and the 2026-2030 plan. Part of the PublicInformation.ie Open Data Publishing initiative.

**Base URI:** `https://publicinformation-ie.codeberg.page/publicinformation-data/`

## What this dataset is and is not

This dataset records what a plan or progress report *stated* — the action as published, the deadline as published, the status as published. It is not an assessment of whether a commitment was actually met, and it does not adjudicate discrepancies between a plan's stated deadline and a report's restated one. That judgement is left to the consumer.

## Slippage is one subtraction away, deliberately not precomputed

`original_deadline_*` (on `actions.csv`) and `reported_deadline_*` (on `action-status-observations.csv`) are normalised through the same date parser, so they are directly comparable. The dataset does not bake in a definition of "slipped" — that would require a judgement call about which comparison counts (start vs. start, end vs. end, precision mismatches) that belongs with the analysis, not the publication.

## Data Model

### `actions.csv` — every action a plan declares

| Property | Type | Description | Required |
|----------|------|--------------|----------|
| `action_id` | String | `{plan_slug}#{action_number}` — stable identity, derived from what the plan states, never from where text sits on a page | Yes |
| `public_body_id` | Integer | Canonical id of the body that published the plan | Yes |
| `plan_slug` | String | `doc_slug` of the plan declaring this action; also the provenance of its original deadline | Yes |
| `plan_title` | String | Title of the declaring plan | Yes |
| `source_url` | URI | Source URL of the declaring plan | Yes |
| `action_number` | Integer | The number the plan itself gives the action; unique only within a plan | Yes |
| `action_text` | String | The action as published, with its leading ordinal and bullet artifacts stripped | Yes |
| `original_deadline_raw` | String | The plan's deadline cell, verbatim | Yes |
| `original_deadline_start` | Date | Normalised deadline start | No |
| `original_deadline_end` | Date | Normalised deadline end | No |
| `original_deadline_precision` | String | `day`, `month`, `quarter`, `year` or `range` | Yes |
| `original_deadline_confidence` | String | `stated` (a single unambiguous date, transcribed) or `interpreted` (derived by the latest-milestone rule from a multi-milestone cell); empty when no date was parseable | Yes |
| `original_timeline_raw` | String | The plan's full timeline cell verbatim, preserving milestone structure the single deadline collapses | Yes |
| `lead` | String | Lead organisation | Yes |
| `support` | String | Supporting organisation(s) | Yes |
| `output` | String | Proposed output | Yes |
| `source_page` | Integer | Page number in the source PDF | Yes |
| `source_ref` | String | Positional reference in the source PDF, for provenance only — never an identity | Yes |

### `action-status-observations.csv` — one row per report per action it mentions

| Property | Type | Description | Required |
|----------|------|--------------|----------|
| `action_id` | String | Joins to `actions.csv.action_id` | Yes |
| `report_slug` | String | `doc_slug` of the progress report making this observation | Yes |
| `report_title` | String | Title of the progress report | Yes |
| `as_of` | Date | The report's own publication date; never inferred from document content | Yes |
| `status` | String | A notation from the [`action-status`](../../vocabularies/action-status.csv) vocabulary | Yes |
| `reported_deadline_raw` | String | The report's restated deadline cell, verbatim | Yes |
| `reported_deadline_start` | Date | Normalised restated deadline start | No |
| `reported_deadline_end` | Date | Normalised restated deadline end | No |
| `reported_deadline_precision` | String | `day`, `month`, `quarter`, `year` or `range` | Yes |
| `progress_text` | String | Free-text progress narrative | Yes |
| `asi` | String | Avoid / Shift / Improve classification; published only by the Year One and Year Two reports, empty for the others | Yes |
| `source_page` | Integer | Page number in the source PDF | Yes |
| `source_ref` | String | Positional reference in the source PDF, for provenance only | Yes |

A plan with zero observations is correct, not missing data — the 2026-2030 plan's first progress report does not exist yet.

### `action-relationships.csv` — how actions relate to one another

| Property | Type | Description | Required |
|----------|------|--------------|----------|
| `from_action_id` | String | Joins to `actions.csv.action_id` | Yes |
| `to_action_id` | String | Joins to `actions.csv.action_id`; empty when the target plan is not in the corpus — a first-class state, not an error | No |
| `to_plan_hint` | String | The target plan exactly as the source document names it | Yes |
| `to_action_number` | String | The target action number as written; empty for a plan-level edge, where the source document names a plan but no action number | No |
| `relationship` | String | A notation from the [`action-relationship`](../../vocabularies/action-relationship.csv) vocabulary | Yes |
| `family` | String | `lineage` or `reference`. Only `lineage` edges are valid for reconstructing an action's history across plan editions | Yes |
| `method` | String | `extracted`, `declared` or `curated` | Yes |
| `asserted_in` | String | `doc_slug` of the document making the assertion | Yes |
| `evidence` | String | Verbatim source text for the assertion | Yes |

`family` before traversal: only `lineage` edges (`renumbered_as`, `supersedes`, `split_into`, `merged_into`, `carried_forward_to`) reconstruct an action's history across plan editions. `complements` and `references` are `reference`-family — they do not imply continuity, and following them as if they were lineage will fabricate a history that was never asserted.

A null `to_action_id` means the target plan is not in the corpus. A null `to_action_number` means the source document named a plan but no numbered action within it (a plan-level edge).

## `original_deadline_confidence`

23 of the 2022-2025 plan's 91 baselines are `interpreted` — derived by a latest-milestone rule from a multi-milestone timeline cell — rather than transcribed as a single stated date. This is disclosed, not hidden: consult `original_timeline_raw` to audit any `interpreted` baseline against the source text directly, without re-fetching the PDF.

## Known limitations

`action-status-observations.csv` includes status observations only from the Year One progress report. The Year Two, Year Three and Final progress reports use a table format that the shared PDF table-header detection (`extract_pages`) does not yet parse, so `extract_action_status` correctly skips them (`UnknownReportFormat`) rather than fabricating observations. This is tracked as a follow-up; a fix to `extract_pages`'s table-header detection will let a future release add their observations without any change to this dataset's shape.

## Text quality (spec §16.1)

The source PDFs contain ligature-reordering artifacts introduced by PDF text extraction — real examples from this corpus are `"staf.f"` (for "staff") and `"Please ofef r me a seat"` (for "Please offer me a seat"). `action_text` and `progress_text` are published as extracted, with no attempt to silently repair this class of error. This is disclosed rather than implying a cleanliness the data does not have.

## Files

- **[actions.csv](actions.csv)** — one row per published action
- **[action-status-observations.csv](action-status-observations.csv)** — one row per report's observation of an action
- **[action-relationships.csv](action-relationships.csv)** — one row per asserted relationship between actions
- **[public-body-actions.csv-metadata.json](public-body-actions.csv-metadata.json)** — CSV on the Web (CSVW) `TableGroup` metadata covering all three CSVs and their foreign keys
- **[public-body-actions.jsonld](public-body-actions.jsonld)** — JSON-LD, single `@context` + `@graph` of all records across all three tables
- **[../../schemas/public-body-actions.schema.json](../../schemas/public-body-actions.schema.json)** — JSON Schema, one `$defs` entry per table
- **[../../catalog/dataset-public-body-actions.ttl](../../catalog/dataset-public-body-actions.ttl)** — DCAT-AP metadata (RDF/Turtle), related to the Public Bodies and Documents datasets via `dct:relation`
- **[../../vocabularies/action-status.csv](../../vocabularies/action-status.csv)** — controlled vocabulary for `status`
- **[../../vocabularies/action-relationship.csv](../../vocabularies/action-relationship.csv)** — controlled vocabulary for `relationship`

## Versioning

This directory (`v1.0.0/`) is an immutable, versioned release. `../../latest/public-body-actions/` always mirrors the newest version. Releases are also tagged in git (`public-body-actions-v1.0.0`).

## Accessing Data

```bash
curl -L https://publicinformation-ie.codeberg.page/publicinformation-data/latest/public-body-actions/actions.csv
curl -L https://publicinformation-ie.codeberg.page/publicinformation-data/latest/public-body-actions/action-status-observations.csv
curl -L https://publicinformation-ie.codeberg.page/publicinformation-data/latest/public-body-actions/action-relationships.csv
curl -L https://publicinformation-ie.codeberg.page/publicinformation-data/latest/public-body-actions/public-body-actions.jsonld
```

## Conformance

| Standard | Level | Notes |
|----------|-------|-------|
| 5-Star Linked Data | ★★★★ | JSON-LD with dereferenceable URIs; no SPARQL endpoint |
| CSVW | Full | One `TableGroup` covering all three tables and their foreign keys |
| DCAT-AP | Full | Complete dataset metadata, related to Public Bodies and Documents via `dct:relation` |
| JSON Schema | Full | `$defs` entry per table, enums drawn from the published vocabularies |

## License

Creative Commons Attribution 4.0 International (CC-BY 4.0). See [LICENSE](../../LICENSE).

## Contact

**Publisher:** [PublicInformation.ie](https://www.publicinformation.ie/)
**Email:** dave@publicinformation.ie
**Repository:** https://codeberg.org/publicinformation-ie/publicinformation-data
