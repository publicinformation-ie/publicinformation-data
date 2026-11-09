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

### D2a. `(TF)` is a flag, stripped from identity and kept in `action_reference_printed` (decided 2026-11-09)
`source-notes.md` found about 60 CAP23/CAP24 references printed with a `(TF)` suffix (`TR/23/46(TF)`, once `TR/24/4 (TF)`). The same action appears with and without it across workbooks, so it is a flag, not identity. Identity uses the reference with a *recognised* flag suffix removed; the only recognised flag is `(TF)`. A new field present on every action, `action_reference_printed`, keeps the reference as printed (whitespace-normalised), so the flag is not lost. For ordinal plans it equals `action_number`. It ships in the same 3.0.0. Unrecognised parenthesised suffixes are not stripped, so they fail the D2 character set and are excluded and logged.
**Rejected:**
- Widening the character set to allow `(` `)`, which forces URI escaping and splits one action into two identities.
- Excluding the ~60 rows.
- Stripping without keeping the printed form, which would lose the flag's meaning (still to be confirmed from the annex key in 0.1).

### D3. Sub-actions are actions; `part_of` records the hierarchy
**Letter attached to the number (decided 2026-11-09).** Three references print the letter without a slash (`EL/23/10A`, `EL/23/10B`, `LU/23/7A`). They are published as printed, for citability, and are still under the D2 character set. For `part_of`, the parent of a reference ending in a letter, whether in its own segment or attached to the final number, is that reference with the letter removed.

Each sub-action is its own row. When the parent reference is itself a published action of the same edition, a relationship `part_of` (new `family: structure`, `method: extracted`, since it comes from the reference itself) links child to parent. The existing families describe lineage across editions or references between plans; neither describes containment, so overloading `split_into` would be wrong. The vocabulary addition ships in the same 3.0.0.
**Open check (0.1):** whether CAP annexes print parent rows with their own text, or only sub-actions. If only sub-actions, no `part_of` rows are emitted, and the hierarchy is readable from the reference and URI alone.

### D4. The plan year in the code must match the edition
For a coded reference, the year segment (`EL/23/…` → 2023) must equal the year of the edition being extracted. A mismatched row, such as the CAP25 annex reprinting `EL/23/1`, is excluded and logged as out-of-edition. It is not published as a CAP25 action and not attributed elsewhere; attribution is Change 2's job. This also gives Change 2 the full list of legacy rows it will need.

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
- **Annex table layouts are unseen.** `extract_actions` has not parsed CAP annex tables. Header aliases may need extending, and each failure goes through `errors.json` triage per document.
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
