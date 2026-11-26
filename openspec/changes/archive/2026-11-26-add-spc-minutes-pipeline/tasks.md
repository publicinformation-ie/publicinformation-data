# Tasks

## 1. Pipeline scaffold, TLS and committed inputs

- [x] 1.1 Create `pipelines/spc_pipeline/` with `pipeline.json`: the eight steps from design.md D2, `body_list_step` pointing at the `minutes_pipeline` `find_local_authorities` reference, and `paid_steps: {"extract_spc_items": ["llm"]}`. Add `process.py` delegating to `src/lib/pipeline_runner.py`. Verify `uv run python pipelines/spc_pipeline/process.py pipelines/spc_pipeline --to find_local_authorities --force --stop-on-error` runs, and `uv run python scripts/pipeline_status.py --pipeline spc_pipeline` lists `extract_spc_items` as paid.
- [x] 1.2 Commit `src/lib/certs/extra_intermediates.pem` (DigiCert Global G2 TLS RSA SHA256 2020 CA1) with a README recording subject, issuer, sha256 fingerprint and source URL. Add a helper that builds a verifying SSL context from default trust plus that file (design.md D10). Verify a test asserts the PEM's fingerprint, and an online smoke check (skipped offline) fetches the Meath SPC page with verification on.
- [x] 1.3 Author `steps/find_spc_minutes_files/committees.json` with the Meath Transportation and Urban Regeneration SPC entry (`meath/transportation-urban-regeneration`, `public_body_id` 1511, page URL, minutes-link pattern). Verify a test asserts unique committee IDs and that each `public_body_id` is in the local-authority list. An unknown ID is fatal.
- [x] 1.4 Add the git-ignored PDF cache path to `.gitignore` and verify `git check-ignore` matches it.
- [x] 1.5 Write `pipelines/spc_pipeline/README.md` covering purpose, step table, committed inputs, how to run bounded with `--to render_spc_minutes`, the cost rule and the fail-closed rules. Verify every command in it runs as written, apart from paid commands, which are labelled as needing permission.

## 2. Discovery and fetch

- [x] 2.1 Implement `find_spc_minutes_files`: collect minutes PDF links only, de-duplicated, with absolute URL and link text. Verify tests on a saved fixture of the Meath page find exactly the 6 minutes links and 0 agenda links.
- [x] 2.2 Implement `fetch_spc_minutes`: cached download, then record sha256, size and retrieval time, and per-page words with coordinates via pdfplumber. Emit `NoTextLayer` for text-free PDFs and a download error with no record on failure. Verify tests cover cold cache, warm cache (no HTTP), a text-free PDF and a certificate failure that is not bypassed.
- [x] 2.3 Write step READMEs for both steps (output fields, errors, cache) and verify the documented error types match those raised in tests.

## 3. Header parsing and meeting identity

- [x] 3.1 Implement `parse_meeting_header`. Read date, venue and start time from the header line, and end time from "Meeting ended". Cross-check month and year against the link text (`MeetingDateMismatch`). Build the meeting ID and detect `DuplicateMeeting`. Verify tests on all six real meetings give the expected dates, `2025-02-20` … `2026-05-21`, and a synthetic mismatch case.
- [x] 3.2 Implement column-aware attendance-table reading (design.md D3). Produce entries per category with printed name, initials, role text and markers. Raise `UnrecognisedHeaderLayout` on unknown labels. Verify tests on all six meetings, including the interleaved "Cllr Sean Drew Cllr Paddy Meade" row, the stray "Cllr,", the presenters row containing "apologies", and the combined "Absent Apologies:" row.
- [x] 3.3 Write the step README with the label set and entry-splitting rules. Verify it lists every label the tests use.

## 4. People register and attendance resolution

- [x] 4.1 Create `reference/people.json` by hand from the six meetings: committee councillors and guest councillors using `councillors.csv` IDs, the three PPN representatives, officials and presenters, each with aliases and initials. Verify a test asserts unique person IDs, unique aliases across people, valid kinds, and that every `councillor` entry's ID exists in `pipelines/minutes_pipeline/reference/councillors.csv`.
- [x] 4.2 Implement `resolve_attendees`: exact normalised alias matching, status (`present`/`apologies`), mode only where printed, per-meeting initials map. Raise `UnresolvedAttendee` and `ContradictoryAttendance` with the whole meeting's attendance withheld. Verify tests show all six real meetings resolve with zero errors, and that a synthetic unknown guest withholds that meeting's attendance while other meetings are unaffected.
- [x] 4.3 Write the step README covering normalisation rules and how to add a person or alias. Verify the documented register entry example validates under the 4.1 test.

## 5. Verbatim rendering

- [x] 5.1 Implement `render_spc_minutes` per design.md D5: furniture removal with counts, line rejoining across pages, item headings with `item-N-N` anchors, `AOB` headings, bullets, the attendance block as category lists, front matter, and escaping of markup characters. Verify snapshot tests of all six meetings are reviewed by eye on a phone-width Markdown preview and committed.
- [x] 5.2 Implement the word-preservation check (`RenderMismatch` with first differing position). Verify all six meetings pass, and that a test which deletes, inserts or swaps one word fails it.
- [x] 5.3 Emit the per-meeting item list (number, title, rendered text, `is_minutes_approval`) for the paid step. Verify item numbers for all six meetings match the source, including `0.0` in May 2025.
- [x] 5.4 Write the step README covering furniture rules, block boundaries and the word check. Verify it describes every error type the tests raise.

## 6. Taxonomy reference data

- [x] 6.1 Add a committed script that builds `reference/cofog_1999.json` from the UNSD structure file, recording source URL, retrieval date and sha256. Verify a test asserts 10 divisions and the presence and descriptions of `04.5`, `04.5.1`, `05.4.0` and `06.4.0`, and that every code's parent exists.
- [x] 6.2 Create `reference/transport_subdomains.json` from the transport-governance vocabulary's Subdomains table. Verify a test parses `.claude/skills/transport-governance/vocabulary.md` and asserts set equality of IDs.
- [x] 6.3 Document both files and their provenance in the pipeline README. Verify the recorded sha256 in the README matches the file's metadata.

## 7. Decisions and topics extraction (paid)

- [x] 7.1 Write the prompt and response schema for `extract_spc_items` (design.md D6), passing items without minutes-approval items, the closed lists and the initials map. Verify a unit test renders the prompt for one real meeting with no model call.
- [x] 7.2 Implement deterministic post-validation in design.md D6 order: schema, closed lists, `04.5`/subdomain rule, verbatim quote, minutes-approval discard, proposer and seconder resolution. Classify minutes-approval items deterministically as `01.1.1` + procedural. Verify tests with canned model responses cover each rejection path (`ExtractionFailed`, `UnknownCofogCode`, subdomain without `04.5`, `DecisionNotInSource`, unknown decision type, unresolved initials) and a fully valid response.
- [x] 7.3 Add the result cache keyed by source sha256, model and prompt version (design.md D8), plus `SPC_LLM_*` configuration with `MOTIONS_LLM_*` fallback. Verify a test shows a second run with unchanged inputs makes no model call.
- [x] 7.4 Extend the `CLAUDE.md` cost rule to name `extract_spc_items` (direct runs, full runs, and `--from`/`--to` windows reaching it), and add the step to the generated docs. Verify `uv run python scripts/generate_pipeline_docs.py` leaves no diff after commit, and that `CLAUDE.md` names the step.
- [x] 7.5 Write the step README covering the prompt version, response schema, validation order, cache, configuration and cost. Verify the documented env vars match the code.

## 8. Model sweep (needs explicit permission to run)

- [x] 8.1 Hand-label the gold set for the six meetings (decisions with type and quote, primary COFOG and subdomain per item) in `experiments/<date>-spc-model-sweep/gold.json`. Verify every gold quote passes the verbatim check against the rendered items.
- [x] 8.2 Write the sweep runner and report: decision precision and recall, topic primary accuracy, verbatim failure rate, cost per meeting. Verify it runs end to end against canned responses with no paid calls.
- [x] 8.3 With explicit user permission, run the sweep over the candidate models and write `REPORT.md`. Set the production default model from it after the user agrees. Verify the chosen model and thresholds are recorded in the step README.

## 9. Export and published dataset

- [x] 9.1 Implement `export_spc_meetings`: assemble meetings (with `attendance_published`), people, attendance, items and decisions. Withhold parts as each capability defines, and report counts by error type. Verify tests cover a clean meeting, withheld attendance, withheld topics and a render failure (nothing published).
- [x] 9.2 Write the JSON Schema `public/schemas/spc-meetings.schema.json` and the vocabularies (attendance status, mode, category, decision type, COFOG 1999, transport subdomain) under `public/vocabularies/`. Verify a test validates every exported record and that a record with status `late` fails.
- [x] 9.3 Implement `scripts/transform_spc_meetings.py` writing `public/v1.0.0/spc-meetings/` and `public/latest/spc-meetings/` (JSON-LD, CSV, CSVW, `minutes/…/<date>.md`, README), with `@id`s, the `public_body` URI, `councillor_id` and `stamp_if_changed`. Verify root tests assert `latest` and `v1.0.0` are byte-identical, every `public_body` resolves in Public Bodies, and an unchanged re-run leaves `dct:modified` alone.
- [x] 9.4 Add `public/catalog/dataset-spc-meetings.ttl`, the `public/CHANGELOG.md` entry, `DATA_SOURCES.md` attribution (Meath County Council minutes; UNSD COFOG 1999), and links from `public/get-the-data.html` and `public/index.html#reference`. **Deviation: `public/index.html` is a 12-line redirect with no `#reference` list, so no link was added there; discovery links are in `public/README.md`, `GET_THE_DATA.md` and `get-the-data.html`.** Verify the catalogue parses as Turtle and the discovery-link tests pass.
- [x] 9.5 Add `pipelines/spc_pipeline/status.py` (per-meeting funnel: fetched → header → attendance → rendered → extracted → exported, errors per step, dry-step verdict) and document it in the README and `AGENTS.md` status table. Verify it exits 0 on a completed run and names the first dry step on a truncated output.

## 10. Web handoff

- [x] 10.1 Finalise `openspec/changes/add-spc-minutes-pipeline/handoff-publicinformation-web.md` against the real exported files: file URLs, field lists, a sample record of each kind, the Markdown front matter and rendering trust boundary, and the attendance-counting rule with `attendance_published`. Verify every URL and field name in it exists in the generated `public/latest/spc-meetings/`.

## 11. Integration

- [x] 11.1 Run the deterministic window `uv run python pipelines/spc_pipeline/process.py pipelines/spc_pipeline --to render_spc_minutes --force --stop-on-error`. Then, with explicit permission, run `--from extract_spc_items --force --stop-on-error` and the transform. Verify all four suites (`uv run pytest tests/ -q`, `uv run pytest pipelines/spc_pipeline/tests -q`, the existing pipeline suites) and `uv run pyright` pass, and that the error counts and `public/` diff are written up for human review before merge.

## Workflow follow-up

- Review the generated `public/spc-meetings/` diff and error report before merging to `main` (merging publishes).
- Hand `handoff-publicinformation-web.md` to an agent in `publicinformation-web`.
- Archive the change after review, and sync its specs to `openspec/specs/`.
