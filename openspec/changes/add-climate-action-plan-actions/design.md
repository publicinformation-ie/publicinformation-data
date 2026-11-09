# Design

> **Scaffold.** This records what was verified about the existing code while scoping `add-climate-action-plan-documents`, so the elaboration of this change starts from facts rather than assumptions. It deliberately takes **no decisions** — the four that block implementation are stated in the proposal, and the earlier draft of this work got into trouble by assuming three of them were already settled.

## Context

The pieces this change has to fit between, all read from the code rather than inferred:

**Action identity.** `resolve_action_identity` derives a published action's identity from what the document states, not where it sat on a page: `action_id = {plan_slug}#{action_number}`, with `action_number` recovered as a leading ordinal from the action cell (`strip_leading_ordinal`, regex `^\s*(\d{1,3})\s*[.)]`). The plan edition is deliberately part of the key — an action renumbered in a later plan is a different published row, and continuity is expressed as a relationship by `extract_relationships`, never by collapsing rows. Upstream, `extract_actions`' `action_id` (`p009-t01-r01`) is provenance, not identity.

**The published contract.** `public/schemas/public-body-actions.schema.json` requires `action_number` to be an integer ≥ 1, and `scripts/transform_public_body_actions.py:232` builds the permanent action URI as `/action/{plan_slug}/{action_number}`. That script also enforces the `expected_action_count` / `expected_status_counts` invariants (`:129-150`) at publish time — no pipeline step checks them.

**Observation joins.** `build_observations` looks up `mint_action_id(record["reports_on"], number)` and nothing else. `reports_on` is the live join key, not a validation artifact, and `documents.py:147-152` requires a report and its plan to share a `policy_id`.

**What is an action source.** `extract_actions:380-390` processes a document only when `role: plan` **and** `policy_role: action-plan`; its own comment notes that flipping a document's role in `documents.yml` is a real curation decision, because reports' annex tables also carry an `Action` column and would otherwise duplicate every plan action once per report.

**Step plumbing.** `fetch_pdfs` validates PDF content types and the `%PDF-` magic; `extract_pages:254-258` opens every fetched file with pymupdf and `detect_structure`, `extract_figures`, `clean_text`, `assemble_sections` and `publish_bundles` all follow it. `src/lib/pipeline_runner.py:99-105` resolves one input step per step and passes a single `--input`; `actions_pipeline/pipeline.json` reaches into the document pipeline by absolute step path, and `resolve_action_identity` locates `extract_action_status` as a sibling of its input path (`process.py:326-329`).

**Prior art for spreadsheets.** `foi_pipeline`'s `transform_disclosure_files` → `extract_disclosures_detect_header_row` → normalize → canonicalize chain is a battle-tested fail-closed Excel intake on `openpyxl` 3.1.5 / `xlrd` 2.0.1, already in the shared venv. It is a technique to copy, not a library to share — the two domains' vocabularies have nothing in common, and premature extraction into `src/lib` would couple them. If a third domain needs spreadsheets, extract then.

**What the sources look like.** CAP action references are sector codes (`EL/23/1`) with sub-actions (`EL/23/6/A`, `EL/23/6/B`). Plan-year annexes are PDFs; quarterly progress-report annexes are XLSX. CAP25's annex PDF carries CAP23 legacy actions *with* a status column, so "plans declare, annexes observe" is not a clean split. The annexes use a colour key, so some status is conveyed by cell fill.

## Goals / Non-Goals

**Goals (indicative):**
- CAP actions and their quarterly status observations publish through `public-body-actions` with identities a reader can cite from the State's own documents.
- Carried-over actions are attributed to the plan year that declared them.
- All parsing stays fail-closed: unrecognised layouts, unmappable statuses and ambiguous dates are logged, never guessed.

**Non-Goals (indicative):**
- No CAP2019/2021 retro-ingestion.
- No shared spreadsheet engine extracted from `foi_pipeline`.
- No change to transport corpus behaviour or output.

## Risks / Trade-offs

- **A dataset contract decision is on the critical path.** D-A cannot be deferred past the first published CAP action, because action URIs are permanent.
- **Record-count growth.** Hundreds of actions plus one observation per action per report makes a large publish diff; `errors.json` triage per step before the publishing commit is the control.
- **Annex layout drift between quarterly workbooks.** Pinned counts turn silent shrinkage into loud failure, but only at publish time (see Context) — decide whether that is early enough.
- **Two pipelines touching Excel.** Accepted duplication, revisited at a third domain.
