# Public Body Actions Dataset

**Dataset URI:** `https://data.publicinformation.ie/dataset/public-body-actions`

The published commitments of Irish public bodies and how their reported status changed over time. Covers the Department of Transport's Sustainable Mobility Policy (SMP) corpus — the 2022-2025 action plan, its four progress reports, and the 2026-2030 plan — and the Climate Action Plan annexes of actions for 2023, 2024 and 2025. Part of the PublicInformation.ie Open Data Publishing initiative.

**Base URI:** `https://data.publicinformation.ie/`

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
| `action_number` | String | The reference the plan itself gives the action (`12`, or coded such as `EL/23/6/A`); unique only within a plan. Text, not an integer, since v3.0.0 | Yes |
| `action_reference_printed` | String | The reference exactly as printed, including any flag marks (`*`, `**`, `(TF)`) | Yes |
| `action_flags` | String | Named flags for the marks printed against the reference (`*` gives `non_reportable`, `**` gives `duplicate`, `(TF)` gives `taskforce`), separated by `;`; empty when none | Yes |
| `action_text` | String | The action as published, with its leading ordinal and bullet artifacts stripped | Yes |
| `action_text_clean` | String | Action text with confirmed PDF-extraction artefacts repaired; the display field. `action_text` remains the untouched extraction | Yes |
| `original_deadline_raw` | String | The plan's deadline cell, verbatim | Yes |
| `original_deadline_start` | Date | Normalised deadline start | No |
| `original_deadline_end` | Date | Normalised deadline end | No |
| `original_deadline_precision` | String | `day`, `month`, `quarter`, `year`, `range`, `annual` or `ongoing` (the last two carry no start or end); null when the printed timeline cannot be parsed | No |
| `original_deadline_confidence` | String | `stated` (a single unambiguous deadline, transcribed, including Annual/Ongoing) or `interpreted` (derived by the latest-milestone rule); empty exactly when no precision was resolved | Yes |
| `original_deadline_label` | String | Short, display-ready final deadline (`2023`, `Q4 2027`, `Annual`, `Ongoing`). Where no date can be parsed it is the Timeline text as printed (`Q1 and Q3`). Null where the plan prints no deadline | No |
| `original_deadline_milestones` | String | Milestone prose preserved from the plan's timeline or interim-milestones cell; empty for a single-date action | Yes |
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
| `reported_deadline_precision` | String | `day`, `month`, `quarter`, `year`, `range`, `annual` or `ongoing` | Yes |
| `progress_text` | String | Free-text progress narrative | Yes |
| `progress_text_clean` | String | Progress narrative with confirmed PDF-extraction artefacts repaired; the display field | Yes |
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
| `family` | String | `lineage`, `reference` or `structure`. Only `lineage` edges are valid for reconstructing an action's history across plan editions | Yes |
| `method` | String | `extracted`, `declared` or `curated` | Yes |
| `asserted_in` | String | `doc_slug` of the document making the assertion | Yes |
| `evidence` | String | Verbatim source text for the assertion | Yes |

`part_of` (family `structure`) links a sub-action such as `EL/23/6/A` to its parent `EL/23/6`; it records how a plan is organised, not history. `family` before traversal: only `lineage` edges (`renumbered_as`, `supersedes`, `split_into`, `merged_into`, `carried_forward_to`) reconstruct an action's history across plan editions. `complements` and `references` are `reference`-family — they do not imply continuity, and following them as if they were lineage will fabricate a history that was never asserted.

A null `to_action_id` means the target plan is not in the corpus. A null `to_action_number` means the source document named a plan but no numbered action within it (a plan-level edge).

### `action-milestones.csv` — one row per interim milestone

Splits each action's `original_deadline_milestones` prose, so an action with several dated milestones (for example SMP 2026-2030 action 4) is queryable per milestone. `original_deadline_milestones` is unchanged.

| Property | Type | Description | Required |
|----------|------|--------------|----------|
| `milestone_id` | String | `{action_id}/m{ordinal}` | Yes |
| `action_id` | String | Joins to `actions.csv.action_id` | Yes |
| `ordinal` | Integer | 1-based position in document order | Yes |
| `due_label` | String | Canonical date label (`Q1 2029`, `2027`; `2028 onwards` keeps its words); empty when undated | No |
| `due_start` | Date | Start of the quarter or year; empty when undated | No |
| `due_end` | Date | End of the quarter or year; empty when undated | No |
| `due_precision` | String | `quarter` or `year`; empty when undated | No |
| `milestone_text` | String | The milestone with its date removed; empty for the date-only Climate Action Plan lists | No |

A date appears only where the plan states one; text with no stated date is one undated milestone. Actions with no milestone text have no rows. The split is deterministic and lossless, but is a text split: one 2022-2025 row (action 20) has a year with no delimiter and stays inside the previous milestone.

## `original_deadline_confidence`

23 of the 2022-2025 plan's 91 baselines are `interpreted` — derived by a latest-milestone rule from a multi-milestone timeline cell — rather than transcribed as a single stated date. This is disclosed, not hidden: consult `original_timeline_raw` to audit any `interpreted` baseline against the source text directly, without re-fetching the PDF.

## Deadline labels and open-ended commitments

`original_deadline_label` is the final date in a multi-milestone cell, provided the cell has at least one year-labelled milestone; a separate DEADLINE column always wins. The earlier milestones are not lost: they stay in `original_deadline_milestones` and `original_timeline_raw`.

`annual` and `ongoing` precisions mean the plan stated an open-ended commitment rather than a date. They have no start or end, so sort them deliberately rather than treating them as missing. A `stated` confidence is valid for these rows (the plan stated an open-ended commitment, not a date).

`original_deadline_label` may be null where a plan prints no deadline (a "-" or empty Timeline cell: 20 Climate Action Plan 2023 rows). A "-" Timeline is not inherited from the parent action. Where the Timeline is printed but cannot be parsed (for example `Q1 and Q3`), the label holds the printed text and the precision, start and end are null.

## Climate Action Plan annexes (new in 3.0.0)

The Climate Action Plan 2023, 2024 and 2025 annexes of actions add 445, 126 and 82 actions respectively (653 in all). The CAP 2024 and CAP 2025 annexes hold only the new high-impact actions of that year, not each plan's full roadmap; do not read their counts as the size of the plan. Rows referring to earlier years' actions are excluded, and `carried_forward_to` links editions.

Coded references repeat across sub-actions; where a table prints "-" in the action cell, the sub-action text is inherited from its parent row. One misprinted reference in the CAP 2023 annex (BE/23/38) is corrected by a curated entry, with `action_reference_printed` keeping the printed form.

## Climate Action Plan status annexes (new in 3.1.0)

Eight Climate Action Plan progress reports (2023 Q1 to the Q1 and Q2 2026 legacy report) publish status in a companion XLSX annex. Each annex row is an observation dated from its report's publication date and attributed to the plan edition that declared the action (`reports_on` may list several plans; a reference declared by two editions goes to the one matching the code year). Status is read from the cell text only (`Complete`, `Delayed`, `On Schedule`); fill colours are ignored. This release adds records only: no field, type or vocabulary changed.

Not published, and logged for review: one `Discontinued` row (`AG/23/10`, 2024 Q1&Q2), which the status vocabulary cannot express; two rows whose printed reference (`EL/23/10A`, `EL/23/10B`) does not match the plan's `EL/23/10/A` and `EL/23/10/B`. The Q2&Q3 2025 and Q4 2025 reports have no curated publication date and contribute no observations. Where an annex timeline is not a strict quarter and year, `reported_deadline_raw` keeps the printed text and the structured deadline fields are null. For 64 observations the annex wording of the action differs from the plan's published text; they are published against the plan's action and flagged for review.

## Reading `latest_status`

`latest_status`/`latest_as_of` are derived by joining observations on `action_id` and taking the greatest `as_of`; null means "not yet reported", not "unknown". In this release that is all 95 actions of the 2026–2030 plan and the 200 Climate Action Plan annex actions that no status annex observes (453 of the 653 have at least one observation).

## Known limitations

The current run has 998 observations: 279 from the four transport progress reports (Year One, Year Two, Year Three and Final) and 719 from the eight dated Climate Action Plan status annexes. Rows in a report whose status term is not in the published `action-status` vocabulary are omitted (`UnknownStatusValue`) rather than coerced to a nearest value; these are logged individually in the step's `errors.json`, so the gap is auditable rather than silent.

`parent_id` and `government_department_id` on the public body are different things: the first is the body's parent in the register hierarchy, the second the department that sponsors it. Do not use one as a substitute for the other.

## Text quality (spec §16.1)

The source PDFs contain ligature-reordering artifacts introduced by PDF text extraction — real examples from this corpus are `"staf.f"` (for "staff") and `"Please ofef r me a seat"` (for "Please offer me a seat"). The raw fields (`action_text`, `progress_text`, `original_deadline_raw`) remain as extracted. `action_text_clean`, `progress_text_clean` and `original_deadline_milestones` carry the repaired display text; transport text fields also carry the table ligature repairs; the audit report lists every repair and every remaining flag.

## Files

- **[actions.csv](actions.csv)** — one row per published action
- **[action-status-observations.csv](action-status-observations.csv)** — one row per report's observation of an action
- **[action-relationships.csv](action-relationships.csv)** — one row per asserted relationship between actions
- **[action-milestones.csv](action-milestones.csv)** — one row per interim milestone of an action
- **[public-body-actions.csv-metadata.json](public-body-actions.csv-metadata.json)** — CSV on the Web (CSVW) `TableGroup` metadata covering all four CSVs and their foreign keys
- **[public-body-actions.jsonld](public-body-actions.jsonld)** — JSON-LD, single `@context` + `@graph` of all records across all four tables
- **[../../schemas/public-body-actions.schema.json](../../schemas/public-body-actions.schema.json)** — JSON Schema, one `$defs` entry per table
- **[../../catalog/dataset-public-body-actions.ttl](../../catalog/dataset-public-body-actions.ttl)** — DCAT-AP metadata (RDF/Turtle), related to the Public Bodies and Documents datasets via `dct:relation`
- **[../../vocabularies/action-status.csv](../../vocabularies/action-status.csv)** — controlled vocabulary for `status`
- **[../../vocabularies/action-relationship.csv](../../vocabularies/action-relationship.csv)** — controlled vocabulary for `relationship`

## Versioning

This directory (`v3.2.0/`) is an immutable, versioned release. `../../latest/public-body-actions/` always mirrors the newest version. Releases are also tagged in git (`public-body-actions-v3.2.0`).

## Accessing Data

```bash
curl -L https://data.publicinformation.ie/latest/public-body-actions/actions.csv
curl -L https://data.publicinformation.ie/latest/public-body-actions/action-status-observations.csv
curl -L https://data.publicinformation.ie/latest/public-body-actions/action-relationships.csv
curl -L https://data.publicinformation.ie/latest/public-body-actions/action-milestones.csv
curl -L https://data.publicinformation.ie/latest/public-body-actions/public-body-actions.jsonld
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
**Repository:** https://github.com/publicinformation-ie/publicinformation-data
