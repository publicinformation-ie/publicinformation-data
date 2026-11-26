# Design

## Context

See proposal.md for motivation and the specs for the required behaviour. This section records what shaped the approach. It is based on a read of all six Meath SPC minutes (February 2025 to May 2026), downloaded on 2026-11-26.

- **Source layout.** All six PDFs are 4 pages with a text layer (about 1,200–2,000 words each). Each page repeats a running header ("Miontuairiscí/Meeting Minutes") and a two-line footer (section address, phone, web, email) under "Page N of 4". Body items are numbered `N.0 Title`, with an occasional `0.0` (acting chair election) and unnumbered `AOB` sections. Bullets use `•`.
- **Attendance table.** Two columns: a label column ("Attendees – (Councillors):", "Attendees – (Sectoral Representatives):", "Absent Apologies:", "(Officials):", "Presenters" / "Presentations made by -") and a value column. Plain pdfplumber text interleaves the columns ("Cllr Sean Drew Cllr Paddy (Councillors): Meade"), so the label words land mid-name. The "Absent" and "Apologies:" labels share one row and are treated as one category.
- **Name variation.** Seen: Wyatt/Whyatt, Murray/Murry, "Mc Grath"/"McGrath", "O' Reilly"/"O'Reilly", "Mc Caul", a missing comma ("Cllr Sean Drew Cllr Paddy Meade"), a stray "Cllr,". The body refers to people mostly by initials defined in the header ("Mike Bray (MB)"), not always consistently: Sean Drew is "SD" in the body but has no initials in one header.
- **Decisions.** Proposed/seconded appears for minutes approval in every meeting. It also appears for the Terms of Reference, the acting chair and the 2026 meeting schedule. Other decisions are prose: "It was agreed that…", "Members agreed…", "referred Item to the next SPC", "will be presented for adopting by the full Plenary".
- **Existing assets.** `find_local_authorities` (minutes_pipeline) gives `public_body_id`/slug for Meath (1511). `pipelines/minutes_pipeline/reference/councillors.csv` already holds all six committee councillors and the guest councillors (Tobin, Meyer, Tolan). `src/lib/llm_extract.py` provides `extract_json` with provider/model configuration. The runner supports cross-pipeline step references (`/pipelines/<p>/steps/<s>`), as `actions_pipeline` does.
- **TLS.** `www.meath.ie` serves its leaf certificate and the DigiCert Global Root G2 but not the intermediate "DigiCert Global G2 TLS RSA SHA256 2020 CA1". macOS's trust store fetches the intermediate itself, but OpenSSL on Linux/CI does not, so verification fails. Supplying the public intermediate (sha256 `C8:02:5F:9F:…:25:A9`, valid to 2031-03-29) as an extra verification certificate fixes it with verification still on.
- **COFOG.** The UN Statistics Division structure file `https://unstats.un.org/unsd/classifications/Econ/Download/In%20Text/COFOG_english_structure.txt` (8,159 bytes, sha256 `5368887b…4b39b5`, retrieved 2026-11-26) has 188 codes: 10 divisions, groups and classes. The UNSD registry lists 1999 as the only adopted version. A revision is in global consultation.

## Goals / Non-Goals

**Goals:**

- Every step that can be deterministic is deterministic: discovery, header parsing, attendance, rendering, export. The model is used only where the meaning of prose is needed (decisions, topics), and its output is checked against closed lists and the source text.
- One paid call per meeting, small enough that a cheap model is viable, with a gold set to measure it.
- The committee list and people register take a second council's committee with configuration only, plus new aliases. New layout quirks may still need parser changes, and that is accepted.

**Non-Goals:**

- A general minutes parser for every council layout. The header and furniture rules are written for the Meath layout and fail closed on anything else.
- Linking decisions to later council actions or to motions.
- Speaker attribution within discussion text. Initials in the body stay verbatim.

## Decisions

### D1. A separate `spc_pipeline`, not more steps in `minutes_pipeline`

`minutes_pipeline` is shaped around discovering every council's plenary and MD minutes and extracting motions. Its outputs, guards and status script all assume that. The SPC flow shares only discovery-by-crawl and PDF text extraction, and needs word positions that `transform_minutes_files` does not keep.

The new pipeline reuses `find_local_authorities` by cross-pipeline reference and imports the download helper, so neither is copied. *Alternative*: add SPC as a `meeting_type` in `minutes_pipeline`. Rejected because its filters exclude SPC files on purpose, and mixing the two would change `motions` semantics.

### D2. Step sequence

| # | Step | Paid | Output |
|---|---|---|---|
| 1 | `/pipelines/minutes_pipeline/steps/find_local_authorities` | — | body list (`body_list_step`) |
| 2 | `find_spc_minutes_files` | — | one record per minutes PDF: committee, URL, link text |
| 3 | `fetch_spc_minutes` | — | sha256, size, per-page words with coordinates (cache is git-ignored) |
| 4 | `parse_meeting_header` | — | meeting ID/date, venue, times, attendance entries by category (as printed) |
| 5 | `resolve_attendees` | — | attendance records with person IDs, or the meeting's attendance withheld with errors |
| 6 | `render_spc_minutes` | — | Markdown per meeting plus item list (number, title, text), word-check result |
| 7 | `extract_spc_items` | llm | decisions and topics per item |
| 8 | `export_spc_meetings` | — | step output consumed by `scripts/transform_spc_meetings.py` |

`paid_steps: {"extract_spc_items": ["llm"]}`. Steps 4–6 depend only on step 3's words, so a register edit re-runs from `resolve_attendees` without re-fetching or re-paying.

### D3. Column-aware reading of the attendance table

Use pdfplumber word coordinates on page 1. Find the label column by locating the known label words ("Attendees", "Absent", "Apologies:", "(Officials):", "Presenters", "Presentations"). Take the x-boundary as the minimum `x0` of value-column words on those rows, and group value words into rows by the `top` of each label. Labels not in the known set, or a page-1 layout where no label column is found, raise `UnrecognisedHeaderLayout` (the meeting is not published).

Value text per category is split into entries on commas and semicolons, and also before a title token ("Cllr", "Mr.", "Ms.") that follows a complete name, which handles "Cllr Sean Drew Cllr Paddy Meade". Each entry yields: the printed name, optional initials in parentheses, role text (the remainder up to the next separator, such as "Chair" or "PPN Rep"), and markers ("online", "via Teams", "in person", "apologies").

"in person." printed after the last of several entries applies only to that entry (spec: mode only where printed). *Alternative*: `extract_tables()`. Rejected because the table has no ruling lines in these PDFs. *Alternative*: let the model read attendance. Rejected because attendance must be exact and repeatable, and the layout is regular enough.

### D4. People register

`pipelines/spc_pipeline/reference/people.json`, committed and hand-curated:

```json
{"person_id": "meath/person/joan-carroll", "canonical_name": "Joan Carroll", "kind": "official",
 "councillor_id": null, "aliases": ["Joan Carroll"], "initials": ["JC"], "public_body_id": 1511}
```

- Councillor entries take `person_id = councillor_id` from `councillors.csv`, which a test checks.
- Matching normalises whitespace, apostrophes (`’`→`'`, `O' Reilly`→`O'Reilly`), "Mc " spacing and leading titles, then requires an exact alias hit. Roles and titles printed in minutes ("Acting Senior Engineer") are per-attendance attributes, not register fields, because they change between meetings.
- Initials resolve per meeting: the header's printed `(XX)` map first, then the register's `initials`. An initialism that maps to two people at one meeting is an error.
- The register is seeded from the six MVP meetings during implementation. Every name seen is added by hand after checking, which forces a human to look at each variant once.

### D5. Rendering and the word check

Furniture is identified per committee by lines that repeat on at least 3 of N pages, plus the `Page \d+ of \d+` pattern. The committee config can pin exact furniture strings once seen.

Line rejoining runs over the de-furnished line stream. A new block starts at an item heading (`^\d+\.\d+\s`), `AOB`, a bullet, or a labelled line (`Proposed by`, `Seconded by`, `Meeting ended`). Otherwise lines join with a space, and hyphenation is kept as printed. Characters that Markdown or HTML would read as markup are backslash-escaped.

The word check tokenises on whitespace. It compares the source word sequence (header in column-aware order, then body, minus furniture) against the rendered output with front matter and Markdown markers stripped and escapes undone. It is a direct, order-sensitive equality, so any loss, insertion or reorder fails.

*Alternative*: the document_pipeline `detect_structure`/`assemble_sections` bundle path. Rejected because it is built for long policy PDFs with contents pages, and minutes need a much simpler, auditable structure.

### D6. One model call per meeting for decisions and topics

Input: the meeting's item list from step 6 (number, title, rendered text), excluding minutes-approval items, which are dropped by a title regex before the call and classified `01.1.1` + `procedural` deterministically. Also sent: the closed lists (COFOG codes and descriptions; subdomain IDs and plain labels; decision types) and the header's initials map.

Output schema: per item, `topics: {cofog: [..1–3], subdomains: [...], procedural: bool}` and `decisions: [{decision_text, decision_type, proposer, seconder}]`, where proposer and seconder are as printed.

Post-validation is deterministic, in this order:

1. JSON schema.
2. Closed lists.
3. The `04.5`/subdomain rule.
4. Verbatim check of `decision_text` against the item text (whitespace-normalised).
5. Minutes-approval discard.
6. Proposer and seconder resolution through D4.

A schema failure fails the meeting closed. A per-item violation withholds that item's topics or that decision, with an error.

The call goes through `src/lib/llm_extract.extract_json`, configured by `SPC_LLM_PROVIDER` / `SPC_LLM_MODEL` / `SPC_LLM_BASE_URL` / `SPC_LLM_API_KEY`, falling back to the `MOTIONS_LLM_*` defaults when unset.

*Alternatives*: one call per item (about 6–10× the calls for no quality gain on 1–2k-word inputs), and two calls (decisions, then topics), which doubles the cost. Both rejected.

### D7. Model selection by experiment before any production run

`pipelines/spc_pipeline/experiments/<date>-spc-model-sweep/` holds:

- a hand-labelled gold set for the six meetings (decisions with types and quotes; primary COFOG and subdomain per item);
- a runner that calls each candidate model on the six meetings;
- a report giving decision precision and recall, topic primary-code accuracy, verbatim-check failure rate, and cost per meeting.

It follows the structure of `minutes_pipeline/experiments/2026-10-07-motion-model-sweep/`. The production default model is set from the report. Every sweep run needs explicit permission per the cost rule.

### D8. Decision and item IDs

Item IDs come from the printed item number (`item-4-0`), so they are stable across re-runs. Decision IDs (`d01`…) are ordinal within a meeting and can shift if extraction changes. To keep published IDs stable, `extract_spc_items` caches its result by source sha256, model and prompt version, and does not re-extract a meeting whose inputs are unchanged. A deliberate re-extraction that changes a published decision set is a reviewed content change, recorded in `public/CHANGELOG.md`.

### D9. Taxonomy reference data

- `reference/cofog_1999.json`: generated by a small committed script from the UNSD file. It records source URL, retrieval date and sha256, and holds `code`, `level` (division/group/class), `description` and `parent`. The `(CS)`/`(IS)` collective/individual markers are kept as a field.
- `reference/transport_subdomains.json`: the subdomain table of `.claude/skills/transport-governance/vocabulary.md` (ID, term, plain label). A test parses the vocabulary's Subdomains table and asserts set equality.
- Both are published as vocabularies under `public/vocabularies/` with the namespaces `https://data.publicinformation.ie/ns/cofog#` and `…/ns/transport-subdomain#`, following the existing vocabulary CSV + CSVW pattern.

### D10. TLS for www.meath.ie

Commit the public DigiCert intermediate as `src/lib/certs/extra_intermediates.pem`, with a README giving its subject, issuer, sha256 fingerprint and source URL (`https://cacerts.digicert.com/DigiCertGlobalG2TLSRSASHA2562020CA1-1.crt`). The SPC fetch step builds its SSL context from the default trust plus this file. This only helps chain building: the certificate still has to chain to a trusted root, and verification stays on.

*Alternative*: rely on macOS truststore behaviour, which leaves CI and cloud sessions unable to run the pipeline. Rejected. Whether `minutes_pipeline` should adopt the same helper is out of scope here, and is noted in its README as a follow-up.

### D11. Publishing layout

`scripts/transform_spc_meetings.py` writes `public/v1.0.0/spc-meetings/` and mirrors it to `public/latest/spc-meetings/`:

- `meetings`, `people`, `attendance`, `items` and `decisions`, each as `.jsonld`, `.csv` and `.csv-metadata.json`;
- `minutes/<council>/<committee>/<date>.md`;
- `README.md`.

It stamps `dct:modified` via `src/lib/dataset_publish.stamp_if_changed`, following `transform_motions.py`. Minutes Markdown front matter follows the spc-minutes-rendering spec. The website handoff (`handoff-publicinformation-web.md` in this change folder) documents the consumption contract and is finalised against the real output after the first reviewed export.

## Risks / Trade-offs

- [Layout drift: a new secretary or template breaks the header parser] → Unknown labels or a missing label column raise `UnrecognisedHeaderLayout`, and the word check catches body regressions. Nothing is published silently wrong.
- [Splitting entries on title tokens mis-splits a name containing "Mr"/"Ms"] → Splitting happens only before a title token that follows a complete registered name. An unresolved fragment becomes `UnresolvedAttendee`, never a new person.
- [The model paraphrases decisions] → Verbatim check rejects them. This lowers recall, which the sweep measures, and is the intended trade-off.
- [COFOG is coarse for transport: buses, footpaths and parking are all `04.5.1`] → The subdomain refinement under `04.5` covers that.
- [The COFOG revision is adopted later] → Codes are namespaced as COFOG 1999. A new edition would be a new vocabulary and an additive (MINOR) dataset change.
- [Publishing names of officials and PPN representatives] → They are already published by the council in the same minutes, and the user confirmed inclusion. The dataset README states the source and that names are reproduced as published.
- [Withholding a whole meeting's attendance for one unknown guest] → This is deliberate, so per-person counts are never quietly incomplete. `attendance_published: false` makes it visible, and the fix is a one-line register edit.
- [Six meetings are a small gold set] → Enough to choose a model and catch systematic failure, not to estimate precision tightly. The sweep is re-run when a second committee is added.

## Migration Plan

New pipeline and dataset, so there is nothing to migrate. Rollout:

1. Implement and test with the deterministic steps only (`--to render_spc_minutes`).
2. Run the model sweep with explicit permission and choose the model.
3. Run `extract_spc_items` with explicit permission.
4. Review errors and the generated `public/` diff.
5. Finalise the web handoff, then merge.

Rollback: revert the merge commit. The dataset is new, so no consumer depends on it until the website change ships.

## Open Questions

- Whether `minutes_pipeline` should switch to the shared extra-intermediates helper for its Meath fetches (follow-up, outside this change).
- Exact gold-set thresholds for an "acceptable" model. To be set with the user from the first sweep report. This does not change the steps.
