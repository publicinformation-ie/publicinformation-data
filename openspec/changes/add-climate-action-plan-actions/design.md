# Design

## Context

The facts this design rests on were read from the code on 2026-11-09:

- **Identity.** `resolve_action_identity` mints `action_id = {plan_slug}#{n}` from a leading ordinal (`_ORDINAL_RE = ^\s*(\d{1,3})\s*[.)]`, `strip_leading_ordinal`). Anything else is `UnresolvedActionNumber`. The plan edition is part of the key on purpose: continuity across editions is a relationship, never a merged row.
- **Contract.** `public/schemas/public-body-actions.schema.json` makes `Action.action_number` an `integer ≥ 1` and required. `ActionRelationship.to_action_number` is **already a string**. `relationship` ∈ {renumbered_as, supersedes, split_into, merged_into, carried_forward_to, complements, references}, `family` ∈ {lineage, reference}, `method` ∈ {extracted, declared, curated}.
- **URI.** `scripts/transform_public_body_actions.py:269` builds `{BASE_URI}/action/{plan_slug}/{action_number}`. The same script enforces `expected_action_count` / `expected_status_counts` at publish time (`:132-150`).
- **Version.** The catalog is at `owl:versionInfo "2.1.0"`, with versioned directories up to `public/v2.1.0/`.
- **Consumer.** `publicinformation-web` reads `latest/public-body-actions/public-body-actions.jsonld`. It types `action_number: number`, maps any non-number to `0` (`src/lib/publicBodyActions.ts:91`), sorts by `a.action_number - b.action_number` (`:130`), and renders `String(action.action_number)` (`ActionList.astro:29`). Today a string would fail **silently**: every CAP action would show as 0, sorted arbitrarily.
- **Existing CAP references.** 29 published relationships (`complements` ×25, `references` ×4, all from `sustainable-mobility-policy-action-plan-2022-2025`) carry `to_plan_hint: CAP` with integer targets 231–285. These are Climate Action Plan 2021 numbers. They must never resolve against CAP23–25.
- **Action sources.** `extract_actions` processes a document only when `role: plan` and `policy_role: action-plan`. Reports also carry an `Action` column, which is why reports must not become sources.
- **What the sources look like.** CAP references are sector codes with the plan year embedded (`EL/23/1`) and optional sub-action letters (`EL/23/6/A`). The CAP25 annex PDF reprints CAP23 legacy actions with a status column. The Taoiseach's quarterly XLSX annexes list action codes and text per quarter. Re-verify all of this at curation (task 0.1).
- **Reconciliation precedent.** On 2026-11-09 the published SMP 2026–2030 actions were compared with the Department of Transport's internal tracker (`SMP Action Plan 2026 - 2030 Tracker.csv`, 95 rows). The 95 references matched exactly, and the text matched for all 95. Action 88 differs only by a MATS/SUMP footnote that the tracker keeps.

## Goals / Non-Goals

**Goals:**
- CAP23–25 declared actions publish in `public-body-actions`, citable by the code the State prints.
- Every existing `action_id` and URI is unchanged.
- Extraction is checked against an independent State list before first publication.

**Non-Goals:**
- Status observations, XLSX ingestion, `reports_on` changes and cross-plan attribution (→ `add-climate-action-status-observations`).
- CAP19/CAP21 editions, and resolving the CAP21 relationship hints.
- Any change to transport extraction output, apart from `action_number`'s type.

## Decisions

### D1. `action_number` becomes text (3.0.0)
`action_number` carries the printed reference, with whitespace normalised. Ordinal plans publish `"12"`, so `action_id` (`plan#12`) and the URI are byte-identical to 2.1.0. CSV output is unchanged; only the JSON-LD and schema type change.
**Rejected:**
- An `action_code` column next to an integer: two numbering schemes, and the URI would keep the made-up one.
- Sequential integers: CAP actions are cited publicly as `EL/23/1`.
- `integer | string`: still breaks the web consumer, and gives consumers two types to handle forever.

### D2. URI keeps the code's slashes; the character set is restricted
`/action/<slug>/EL/23/6/A`. A sub-action's URI sits beneath its parent's, and nothing is percent-encoded (`%2F` in path segments is handled inconsistently by static hosts and proxies). References are restricted to `[A-Za-z0-9]` segments joined by `/`. Anything else is excluded and logged, never escaped.
**Rejected:** percent-encoding (`EL%2F23%2F1`), which is hard to read, ambiguous to normalise, and not what a reader would type.

### D2a. Printed flags are stripped from identity and recorded (decided 2026-11-09)
The annexes print three flag suffixes on references (see `source-notes.md`); the CAP23 and CAP24 guides define them:
- `(TF)`, the Delivery Taskforce flag: about 42 rows in CAP23, 26 in CAP24 and 13 in CAP25.
- `*`, "non-reportable": about 73 CAP23 rows.
- `**`, "duplicate action": 8 CAP23 rows, whose text names the action they are reported under.

They combine in either order (`TR/23/2*(TF)`, `TR/23/26**(TF)`), and the same action appears with and without `(TF)` across sources, so they are flags, not identity.

Identity is the reference with recognised flags removed. Two fields ship in 3.0.0 on every action:
- `action_reference_printed`: the reference as printed, whitespace-normalised.
- `action_flags`: a list from the closed set `non_reportable`, `duplicate`, `taskforce`, empty for unflagged and ordinal references. In CSV it is a `;`-separated cell, declared as a list in the CSVW metadata.

Unrecognised suffixes are not stripped, so they fail the D2 character set and are excluded and logged. Linking a `duplicate` action to the one it is "reported under" is deferred to `add-climate-action-status-observations`, where that link decides which observations count.

**Rejected:**
- Widening the character set to allow `(`, `)` and `*`, which forces URI escaping and splits one action into several identities.
- Excluding flagged rows: about 81 CAP23 actions, and the XLSX annexes list none of them, so reconciliation would not notice the loss.
- Keeping flags only in the printed string, which would make every consumer parse `*`.

### D3. Sub-actions are actions; `part_of` records the hierarchy
**Letter attached to the number (decided 2026-11-09).** Three references print the letter without a slash (`EL/23/10A`, `EL/23/10B`, `LU/23/7A`). They are published as printed, for citability, and are still under the D2 character set. For `part_of`, the parent of a reference ending in a letter, whether in its own segment or attached to the final number, is that reference with the letter removed.

Each sub-action is its own row. When the parent reference is itself a published action of the same edition, a relationship `part_of` (new `family: structure`, `method: extracted`, since it comes from the reference itself) links child to parent. The existing families describe lineage across editions or references between plans; neither describes containment, so overloading `split_into` would be wrong. The vocabulary addition ships in the same 3.0.0.
**Open check (0.1):** whether CAP annexes print parent rows with their own text, or only sub-actions. If only sub-actions, no `part_of` rows are emitted, and the hierarchy is readable from the reference and URI alone.

### D4. Legacy rows are excluded by code year; forward-year rows belong to the printing edition (revised 2026-11-09)
A code's year segment is the expected **delivery** year, not the plan year (CAP23 guide). CAP23's annex declares 11 actions coded `/24/` or `/25/` (`RE/24/1`, `LU/25/1`, …).

The rule:
- A row whose code year is **earlier** than the edition's year is a legacy reprint. For example, CAP25 reprints 46 `/24/` and 18 `/23/` rows. These are excluded from the edition and logged as out-of-edition. Attributing them is Change 2's job, and the log gives Change 2 its full list of legacy rows.
- A row whose code year is the edition year or later belongs to the printing edition.
- When a later edition's annex prints the same reference as its own (3 CAP23 `/24/` codes in CAP24, and 4 CAP23 `/25/` codes in CAP25), both editions publish it, and `carried_forward_to` (existing `lineage` family, `method: extracted`) links earlier to later. This follows the dataset's existing rule: continuity across editions is a relationship, never a merged row.

This keeps CAP25 at its 82 `/25/` rows, matching the published total of 82.
**Rejected:** "first edition wins", which would make CAP24 and CAP25 counts disagree with their own annexes and progress reports.

### D7. Annex table layouts are handled by an explicit per-document opt-in (decided 2026-11-09)
Running the real annexes showed two layouts `extract_actions` doesn't handle:
1. Each table opens with a "Key Heading" row and then a lone-cell **"Actions"** subtitle row. That row matches `ACTION_KEYWORDS`, so it is picked as the header instead of the real `Action Number | Actions | Steps | Output | Timeline | Lead | Stakeholders` row.
2. Tables **continued on a new page have no header**, so they are skipped as having no action column.

The result was 42 resolved actions out of about 680 expected. Both fixes would change how the published SMP plans are read. Following the repo's rule that a new trigger must be opt-in rather than auto-detected (the `ocr_pages` precedent), a new `documents.yml` field `action_table_layout`, a closed list of `skip_subtitle_header` and `carry_header`, turns each behaviour on per document. Documents without it are read exactly as before. That is proved by a byte-identical rerun of every curated action plan (task 3.2b).
**Rejected:**
- Changing header selection for every document, which risks the published SMP extraction for no SMP benefit.
- A separate CAP-only extractor, which duplicates the table reader.

**Revised 2026-11-09 after a third layout.**
A third table shape appeared in the real run: a multi-cell theme/KPI row (`Theme: … | 2025 KPI: … | 2025 Abatement Potential: …`), then `Measure: …`, then the lone "Actions" row, and only then the real header. `skip_subtitle_header` skips only lone-cell rows, so it can't handle this.

Instead of adding a rule per shape, the opt-in now **declares the annex's own header**. `skip_subtitle_header` is replaced by `action_number_header`: the header is the first row with a cell that normalises to "action number", and every row above it is skipped as preamble. A table with no such row is a candidate for `carry_header`. This handles the lone "Actions" row and the theme/KPI rows with one rule. The closed set is now `action_number_header` and `carry_header`. Nothing was published with the old value, so the rename has no compatibility cost.

**Accepted limit.** `carry_header` inherits only when the headerless table is on the page right after an action table and has the same column count. A headerless table that follows a non-action table, or that changes width, is not recovered. Such rows are not dropped silently: each reference-bearing row in a table that is not read is logged, and reconciliation (D5) flags any XLSX reference those rows would have supplied.

**Revised again 2026-11-09 (reconciliation).** On CAP23 p.56 the continuation of the BE/23/34 table has 7 columns. Its header table on p.55 has 8, the extra being a spacer column after Actions that is empty in every row. `carry_header` now compares widths after dropping header-table columns that are empty in every row, and maps the fragment onto the remaining columns. Adjacency is still required.

### D8. Curated reference corrections for source misprints (decided 2026-11-09)

CAP23 p.57 prints BE/23/38 as `BE/23/36`, which duplicates the row above. The XLSX annex has BE/23/38 with the same text. An annex entry may declare `reference_corrections`, a list of `{page, printed, corrected, evidence}` entries.
- The corrected reference becomes the identity. `action_reference_printed` keeps the misprint, so the correction stays visible.
- Each correction also declares `text_starts`, the opening words of the misprinted row's action text. It applies only to the row on its page whose reference is `printed` **and** whose text starts with `text_starts`. If no row matches, or more than one does, it's a fatal error. The reference alone isn't enough, because a misprinted duplicate shares it with a genuine row: if a reissued PDF fixed the typo, matching by occurrence would silently rename the genuine row.
- Corrections are only for misprints shown by an independent list. They are never used to change a plan's numbering.

### D9. A "-" action cell inherits the parent's text (decided 2026-11-09)

87 CAP23 sub-action rows print "-" in the Actions cell, meaning "same as the parent". The published `action_text` takes the parent row's text in the same table, which matches the XLSX on those rows. The relationship is still recorded by `part_of`. A "-" row with no parent row in the same table is excluded and logged, rather than publishing a bare "-".

### D10. The deadline label is the printed timeline, or null when nothing is printed (decided 2026-11-09)

The 2.x contract required a non-empty `original_deadline_label` on every action, which no SMP row ever broke. 24 CAP rows do:
- 19 CAP23 headline rows print "-" in the Timeline cell (their sub-actions carry the dates), and BE/23/34 has an empty cell;
- 4 rows print a recurrence or a quarter without a year: PS/23/5 and PS/24/5 "Q1 and Q3", CP/23/6/A "Q2 and Q4 Annually", IN/25/3 "Q4".

The label is the Timeline text as printed, whitespace-normalised, whenever there is any. `original_deadline_precision` and the parsed date are null when it can't be parsed. The label is null when the cell is "-" or empty. The 3.0.0 schema and README make the label nullable and say that null means the plan prints no deadline for that action. A "-" Timeline cell is not inherited from the parent (unlike D9's action text), because the parent's deadline isn't the sub-action's. No rows are excluded, so the pinned counts stand.

### D5. Reconcile against the XLSX annexes as a reference list, not as a source
A review script reads each edition's quarterly XLSX annexes (openpyxl, already in the shared venv), collects their codes and action text, and compares them with the extracted actions:
- every XLSX code for the edition must resolve to an extracted action (blocking);
- text is compared after normalisation, and mismatches are fixed or recorded with a reason;
- extracted actions absent from every XLSX are reported, not blocking, because quarterly annexes list only the actions due in that period.

The XLSX files are downloaded to a scratch location for the check, not curated in `documents.yml`, so D-D (spreadsheet intake) stays in Change 2. The report is committed as evidence alongside the change. `expected_action_count` is then pinned per annex. Enforcement stays at publish time; whether that is early enough is still open.
**Rejected:** relying on the published headline counts (290/125/82). Those are "actions due in year N", a subset of each annex, so they can't be pinned as totals.

### D6. Staged release for the consumer
1. The `publicinformation-web` change accepts `number | string`, displays the string, and sorts naturally (by segment, numeric where numeric). It ships while `latest/` is still 2.1.0.
2. The data repo publishes `public/v3.0.0/` and moves `latest/` together, with the catalog version and changelog.

The data repo cannot enforce step 1, so it is a task gate before the publishing commit.

## Risks / Trade-offs

- **MAJOR bump for a type widening.** It's honest, but any unknown consumer of `latest/` that assumes an integer breaks. Mitigation: the changelog entry calls out the type change, and the versioned 2.1.0 directory stays published.
- **Annex table layouts.** These turned out not to be an alias problem; see D7. Each failure still goes through `errors.json` triage per document.
- **The edition-year rule depends on the code format.** If a CAP edition's codes don't embed the year as assumed, D4 must fall back to an explicit legacy marker in the annex. Verify before implementing (0.1).
- **Publish diff size.** Hundreds of new action rows, plus every transport JSON-LD row changing `action_number`'s type. Review the `public/**` diff before the publishing commit.

## Migration Plan

1. Web consumer change (D6 step 1) lands and deploys.
2. Code: identity, edition-year check, `part_of`, schema, transform, with tests. Transport output is regenerated and must be identical in CSV and type-only different in JSON-LD.
3. Curate the three annexes, run per document, triage errors, run reconciliation, pin counts.
4. Publish 3.0.0 plus `latest/`, catalog and changelog.

Rollback: revert the annex entries and leave `latest/` on 2.1.0. The 3.0.0 directory can be withdrawn through `orphans.py` before any announcement.

## Open Questions

- Do CAP annexes print parent rows for sub-actions (affects whether D3 emits anything)?
- Is publish-time count enforcement early enough, or should `resolve_action_identity` check the pin?
- Should the SMP tracker reconciliation become a repeatable check? The tracker is an internal Department of Transport file, so its provenance and redistribution status would need settling first.
