# Follow-ups from the post-merge review of `add-spc-minutes-pipeline`

**Date:** 2026-11-26
**Reviewed range:** `df6dc5ce..0ba8f792` (149 files, ~13.2k insertions)
**Method:** four parallel reviewers over partitioned slices (ingestion+rendering; attendance+extraction+sweep; publication+dataset; scaffolding+tests+docs), then every published-data claim re-verified by hand against the live files and the code.

This is a **handoff doc, not an OpenSpec change.** The review findings below are the raw material for a proper change (`openspec propose`) covering the remaining P2–P4 work.

---

## 0. Where the next session starts

**The correction release (§6 step 1) is pushed and live** — verified 2026-11-26.

- `main` and `origin/main` are level at `653933d6`. CI `verify` (45897958316) and Deploy Pages (45897958422) both passed on push. The live site serves 17 decisions, the restored role text and no `2025-11-20/d01`; all three checks were confirmed against `data.publicinformation.ie` after deploy.
- Working tree clean; the only untracked entries are the three foreign ones in §1 — leave them alone.
- **Next action:** §6 step 2 (fail-closed sweep). It needs no API spend. The only paid step is step 5; read the cost rule first.

What the correction release already changed — do not redo it:

| Item | Where it now lives |
|---|---|
| P1.1 role text kept | `parse_meeting_header/header.py` `_append_fragment`; tests `test_role_fragment_attaches_to_the_name_before_it`, `test_role_printed_before_the_name_is_kept_in_the_printed_text` |
| P2.1 word check rebuilt | `render_spc_minutes/rendering.py` `source_body_words`, `markdown_words`, `check_attendance`; `detect_furniture` now requires a page edge; snapshot regenerated |
| P1.2 `d01` removed | `extract_spc_items/override.json` drops it; `d02`–`d04` keep their IDs. The prompt is **not** fixed — step 5 still owes that |
| P1.3 two items corrected | `ProceduralNotProceduralCode` validation + the same `override.json`. `item-2-0` was deliberately left alone (see the P1.3 note) |

Evidence from the release: 115 SPC tests and 562 root tests pass, `pyright` clean, 195 records validate against the schema (196 minus `d01`), `latest/` and `v1.0.0/` identical, and the 6 cached model responses were reused with unchanged mtimes (zero spend).

---

## 1. State and ground rules

- Branch `main`, level with `origin/main` at `653933d6`, tracked tree clean. Earlier commits: `f0f02971` (correction release), `0ba8f792` (CI rdflib pin), `9f7acd95` (merge), `f7f97f1f` (spec sync + archive), `320861fc` (implementation + publication).
- The change is archived at `openspec/changes/archive/2026-11-26-add-spc-minutes-pipeline/`; six capability specs are live in `openspec/specs/spc-*/`; `openspec validate --specs` passes 17/17.
- **The published dataset** holds 6 meetings, 28 people, 98 attendance rows, 46 items, **17 decisions** (was 18 before `d01` was removed) and 6 minutes files, and `latest/` and `v1.0.0/` are identical.
- Untracked and **not ours — leave alone**: `openspec/changes/improve-chapter-split-accuracy/`, `pipelines/foi_pipeline/experiments/gating/populate_docling_cache.py`, `pipelines/foi_pipeline/steps/transform_disclosure_files/docling_cache/`, and `stash@{0}`.

### Cost rule — read before running anything

`extract_spc_items` spends real money. **Never** run it, a full pipeline, or any `--from`/`--to` window that reaches it without explicit per-run permission from the user (also recorded in `CLAUDE.md`). The bounded safe command is:

```bash
uv run python pipelines/spc_pipeline/process.py pipelines/spc_pipeline --force --stop-on-error --to render_spc_minutes
```

Responses are cached in `pipelines/spc_pipeline/cache/llm/` (git-ignored), keyed by `source_sha256 + model + PROMPT_VERSION`. While the source PDFs, model and `spc-items-v1` are unchanged, extraction and export replay from cache at **zero** cost. **Bumping `PROMPT_VERSION` or editing a source PDF makes the step paid again (6 calls, ~$0.0011/meeting).** A sweep re-run is 18 calls. Editing `override.json`, the validation rules or the renderer does **not** invalidate the cache: extraction replays and re-applies the overrides for free. The correction release was produced with `--from extract_spc_items --to export_spc_meetings --force --stop-on-error`; a render-only change can use `--from render_spc_minutes --to render_spc_minutes`.

### Verdict

At review time, no reviewer found cause for a takedown: identifiers are stable and correctly namespaced, all 196 records validated against the schema, `v1.0.0/` and `latest/` were byte-identical, and the TTL parsed (134 triples). Three defects were nevertheless **wrong in the live data**, and two of the checks that should have caught them could not fail. Those three are fixed in `f0f02971`; the word check is rebuilt, and furniture removal is now position-limited (with the residual under P2.3). What remains below is fail-open paths, unverified edges and documentation — not live wrong data.

---

## 2. P1 — wrong in the live dataset (fixed and live in `f0f02971`)

### P1.1 Verbatim minutes drop printed attendance role text

**Fixed.** `parse_entries` now appends the role fragment to `raw` (and prefixes a role printed before the name), so the renderer's `entry["raw"]` includes it. The render step now fails a meeting if a parsed role word is absent from `raw`. Re-rendering restored all 24 entries; the only Markdown diff in the six files was those 24 lines.

The original diagnosis, kept for context: 24 instances across all six published files.

- pre-fix line numbers: `pipelines/spc_pipeline/steps/parse_meeting_header/header.py:431-433` appended a non-person fragment to the previous entry's `role`, but `raw` (set at `:450`) was never extended.
- `pipelines/spc_pipeline/steps/render_spc_minutes/rendering.py:317` renders `entry.get("raw")`, so text missing from `raw` never reaches the Markdown.

Evidence:

```
# public/latest/.../2026-02-19.md  — PDF prints "Martin Murray (MM), DOS"
- Martin Murray (MM)                       # and "DOS" appears nowhere in the file

# public/latest/.../2025-05-27.md:49 — visibly truncated mid-phrase
- Caroline Corrigan - Senior Engineer – Footpath Extension Programme \&
```

Reproduce the full list:

```bash
cd pipelines/spc_pipeline && uv run python -I -c "
import json, pathlib
d = json.loads(pathlib.Path('steps/parse_meeting_header/output.json').read_text())
for rec in d['results']:
    for e in rec['attendance']:
        for part in [s.strip() for s in (e.get('role') or '').split(',') if s.strip()]:
            if part not in (e.get('raw') or ''):
                print(rec['meeting_id'], e['printed_name'], '|', part, '|', e['raw'])
"
```

Violates `openspec/specs/spc-minutes-rendering/spec.md` ("keeping each name's text as printed") and the repo's never-silently-drop principle. The role text **does** survive in `attendance.jsonld` (`"role": "DOS"`), so nothing is lost from the dataset — only from the artifact that advertises itself as verbatim. Fix: extend `raw` when appending, and log an error whenever the parser attaches a fragment by heuristic (`_looks_like_person`, `header.py:260`). Then re-render, re-export, republish.

### P1.2 Another body's decision published as an SPC decision

**Partly fixed — the data is corrected and live, the generator is not.** `d01` is no longer published: a committed `extract_spc_items/override.json` drops it, `d02`–`d04` keep their IDs, and `public/CHANGELOG.md` records it. The prompt still does not say "decisions of *this committee*", so a re-extraction with a bumped `PROMPT_VERSION` will produce it again until step 5. When the prompt is fixed, remove the override entry (a stale drop target fails the run closed).

Original finding, verified live at the time: `https://data.publicinformation.ie/spc-meetings/decision/meath/transportation-urban-regeneration/2025-11-20/d01`

```
decision_type: "adopted"
decision_text: "Meath County Council Traffic Calming Policy was adopted by the
                Plenary Council on 3rd November 2025 and is available online…"
```

The source is an information note under "Matters Arising" — not an SPC decision. All three swept models produced it; the hand-labelled gold set correctly omits it. Why nothing caught it: the verbatim check (`extraction.py:389`) proves the text exists, not that the SPC decided it; the prompt never says "decisions of *this committee*"; `decision_type` is never checked against the quote; and the sweep gate has no precision term.

Fix: tighten the prompt (and bump `PROMPT_VERSION` → paid re-extraction), remove `d01` from the published set now, and record it in `public/CHANGELOG.md`.

### P1.3 Topic rules the spec fixes are breached in published items

**Fixed and live for the two real breaches; one row below was a misreading.** `validate_response` now withholds an item flagged `procedural: true` whose primary code is not `01.1.1` (`ProceduralNotProceduralCode`), and the committed override sets 2025-05-27 items 7.0 and 9.0 to `01.1.1` with no subdomains. `2025-02-20 item-2-0` is **unchanged on purpose**: the spec says purely procedural items SHALL be `01.1.1`, not that every `01.1.1` item is procedural, so the second table row was an over-reading of `spc-topic-classification/spec.md:58-65`. Enforcing the converse would have been a wrong correction.

Not addressed here: class-vs-group COFOG level (see step 2), and the extractor still emits the two model violations every run, so `extract_spc_items/errors.json` will show 2 `ProceduralNotProceduralCode` entries until the prompt is fixed.

Original finding, verified against `public/latest/spc-meetings/items.jsonld`:

| Rule (`openspec/specs/spc-topic-classification/spec.md:58-65`) | Breaches |
|---|---|
| `procedural: true` ⇒ primary COFOG `01.1.1` | 2 items (2025-05-27 items 7 and 9, "No update", are `04.5.1` with subdomains) |
| ~~primary `01.1.1` ⇒ `procedural: true`~~ | not a spec rule; `2025-02-20 item-2-0` is valid as published |
| `04.5*` ⇒ at least one subdomain | 0 (this one *is* enforced, `extraction.py:361-367`) |

8 items carry more than one COFOG code; class-vs-group level is not enforced at all. The original fix note said "validate all three rules"; only the first and third are real rules. The class-vs-group check remains open under step 2.

---

## 3. P2 — fail-open paths (P2.1 fixed, P2.3 partly fixed; the rest open)

### P2.1 The word-preservation check cannot catch its own failure modes

**Fixed.** `render_meeting` now compares `source_body_words(record)` — read straight from the PDF pages — against `markdown_words(render_body(blocks))`, with `escape_inline` undone, and `check_attendance(record)` checks the attendance block (every parsed role word must appear in `raw`, and the rendered list must equal the concatenated entries). `detect_furniture` now requires a page-edge position, so a repeated body line cannot be folded into the furniture set. Three synthetic tests cover the failure modes without the git-ignored caches: a repeated `Noted.`, a role outside `raw`, and a role glued to a bracket.

Original diagnosis: `rendering.py:348` called `check_words(source_words(body_lines), rendered_words(blocks))` where `blocks = segment_blocks(body_lines)`. **Both sides derived from the same post-furniture-removal lines.** It verified block segmentation only — not furniture removal, not the page-1 header cut, not escaping (`escape_inline` at `:264`), and not attendance at all.

`spec.md:78` requires the rendered body's words to equal the source's **minus furniture**, and `export_spc_meetings/exporting.py:99` gates publication on `word_check == "passed"` (`rendering.py:367`). So the gate was far narrower than it claimed, and the original run's "zero errors" was reported from a check that could not fail. **This was the root cause of P1.1.**

### P2.2 Register initials fallback overrides the meeting's own printed map

`steps/resolve_attendees/resolving.py:81-92`. When the meeting prints `(XX)` for a name absent from the register, `alias_index.get` misses and control falls through to `initials_index[XX]`, returning a registered person **with no error** — despite the docstring saying the meeting's print wins and it "never guesses".

Not triggered by today's data. It fires the first time a new councillor, official or guest shares initials with someone registered. Attendance would then be withheld by `UnresolvedAttendee`, but **decisions still publish with the wrong proposer or seconder**. Fix: if `printed` exists and does not resolve, return an error; use the register fallback only when the meeting prints nothing for that key. Add a test.

### P2.3 Furniture removal can delete body lines

**Partly fixed.** `detect_furniture` now removes a repeated line only when every occurrence sits in the top 2% or bottom 5% of its page, so a mid-page `Noted.`/`Agreed.` survives; the synthetic `test_furniture_rule_keeps_a_body_line_that_repeats_on_three_pages` locks it in. Still open: the edge bands are tuned to this publisher's template, a genuine line at the very bottom repeated on three pages would still be removed, a 1–2 page PDF never reaches the frequency threshold (its footer stays in the body), and no error is logged for a removed line that is not a recognised pattern. Step 2 should decide whether to add the pattern log and a per-page height, or to leave the bands as the recognisable definition of furniture.

Original diagnosis: `rendering.py:50-62` removed any normalised line appearing on ≥3 pages. A genuine body line ("Noted.", "Agreed.") repeating on three pages was deleted; only a count survived in `furniture_removed`, and the old word check could not see it.

### P2.4 Stale output files are never deleted

`scripts/transform_spc_meetings.py:255-272` only ever writes; `stamp_if_changed` ignores files present on disk but absent from `generated`, and `mirror_to_latest` (`:275`) copies the already-polluted tree. If a meeting later fails render or the word check, **its `minutes/*.md` stays public in both directories**, which the dataset spec forbids. Fix: delete files under `OUTPUT_DIR` that are not in `generated`, and count that as a change.

### P2.5 Dangling person references are published

`exporting.py:139-142` counts `UnknownPerson` and carries on; the attendance/decision rows still publish a `person_id`/`proposer`/`seconder` with no `people` row. Also `exporting.py:31` defaults `attendance_published` to `True` when absent, and the export never asserts that a meeting marked `False` has zero attendance rows. Fix: withhold the affected meeting's attendance or decisions, or raise.

### P2.6 Fetch cache is unverified and a bad download sticks forever

`steps/fetch_spc_minutes/fetching.py:96-121`: bytes are written (`:105`) with no `%PDF`/content-type check, so a 200 carrying an HTML error page is cached; the sidecar `sha256` (`:107`) is written but never compared on read, so a corrupt cache silently redefines `source_sha256`; the write is not atomic; and the catch-all at `:143` reports the resulting parse failure as `DownloadFailed`, so it never re-downloads. A changed PDF at the same URL is never re-fetched. Fix: validate on download, temp-file + rename, verify the sidecar on every read and re-download on mismatch, and separate parse errors from download errors.

### P2.7 LLM cache key is incomplete and failures are cached permanently

`steps/extract_spc_items/extraction.py:206-208` keys on `source_sha256 + model + PROMPT_VERSION` (`:39`). Editing the prompt text, `reference/cofog_1999.json`, the subdomain list or the render logic without remembering to bump the version **silently serves stale classifications**. Worse, `:474` writes the raw response *before* validation, so a response failing the schema or echo check is cached and that meeting stays `extraction_failed` until someone deletes the file by hand (undocumented). Fix: hash the full `system + user` prompt into the key, write only after validation (or store failures separately), write atomically.

### P2.8 1.0.0 contract drift

**Verified:**

```
items.jsonld     has item_id   — absent from items.csv, the schema and the CSVW
decisions.jsonld has item_key  — absent from decisions.csv and the schema
public/schemas/spc-meetings.schema.json — "additionalProperties" occurs 0 times
```

Undeclared, unversioned fields become part of the 1.0.0 contract the moment anyone relies on them. Separately, `decisions.csv` can only join to its item via `item_number`, which `FIELD_SPECS` itself documents as non-unique (2026-05-21 already prints two `6.0` items) — add `item_key` to the decisions columns. Fix all three together and treat it as a documented 1.0.0 correction or a 1.1.0 bump.

---

## 4. P3 — verification you cannot currently rely on

### P3.1 CI never runs the SPC suite

`.github/workflows/ci.yml:38-43` runs the FOI, document and root suites only. The pipeline's **115 tests are unguarded on a branch where pushing publishes**. The `rdflib` miss in `0ba8f792` came from the same gap, and the correction release did not touch CI. Fix: add `uv run pytest pipelines/spc_pipeline/tests -q`, add the suite to the `AGENTS.md` "Tests" table, and correct "CI currently enforces the three test suites".

### P3.2 The strongest tests skip without git-ignored caches

Nine skip guards exist in the suite; six gate the tests that matter most on files that exist only after a local run — `test_fetch_spc_minutes.py:121`, `test_parse_meeting_header.py:225` and `:233`, `test_resolve_attendees.py:177`, `test_render_spc_minutes.py:24` (a module fixture, so it skips the word check on all six meetings, the snapshot, and the furniture and anchor tests), `test_model_sweep.py:20`. Note that four of these are `@pytest.mark.skipif` decorators, not `pytest.skip` calls, so a `grep` for the latter under-counts them. The remaining three guard absent reference inputs (`test_find_spc_minutes_files.py:82`, `test_resolve_attendees.py:55`, `test_reference_data.py:65`). Locally they read outputs left by an earlier run, so a stale `output.json` can mask a broken step. Fix: commit small fixtures (per-page words, or six sha-pinned PDFs under LFS) so the lossless-render guarantee is actually enforced.

### P3.3 The render "snapshot" is only a hash

`tests/test_render_spc_minutes.py:105-108` + `fixtures/render_sha256.json` commit one sha256 per meeting. Task 5.1 promised snapshots "reviewed by eye … committed". A hash cannot be reviewed and gives an opaque diff. Commit the Markdown or a diff-friendly excerpt.

### P3.4 The model choice rests on a buggy scorer and an incomplete gold set

- **Scorer bug:** `experiments/2026-11-26-spc-model-sweep/sweep.py:55` pads with spaces (`f" {shorter} " in f" {longer} "`), so a correct prefix followed by punctuation scores as a miss. Recomputed, deepseek's recall is 1.0 (reported 0.945) and its 2025-11-20 precision 0.75 (reported 0.5). It hurt the chosen model — but the scorer cannot be trusted at the 3–5 point margins the decision used.
- **Gold is incomplete and inconsistent:** plain agreements in 2026-05-21 ("Members agreed that glyphosate is a harmful product…") are unlabelled while an equivalent in 2025-11-20 is labelled. 15 gold decisions over 46 items, macro-averaged over meetings with 2–3 decisions, one run per model, no variance estimate. Precision is therefore not meaningful and recall measures a floor.
- **Topic scoring flatters:** withheld/missing items are skipped rather than counted as misses (`sweep.py:97`); agreement accepts any of three codes or any ancestor relation (a division code would "agree" with every child); `type_accuracy` is vacuously 1.0 when nothing pairs (`:74`).
- **The decision is under-justified:** `glm-5.3-flash` also passes the gate with **higher precision (0.903 vs 0.833) and higher recall (1.0 vs 0.945) at the same cost**; deepseek wins on one decision type and 0.028 of topic agreement. The gate omits precision, the README comparison table omits the precision column, and `REPORT.md` gives no rationale for the choice.

Fix: token-sequence containment, complete double-labelled gold, a precision floor and per-field gates, micro **and** macro figures, a written rationale — then one paid sweep re-run before reconfirming or changing the model.

### P3.5 Subdomains are published with no accuracy evidence

Against gold on the production output (measured before the correction release; the two 2025-05-27 items have since lost four subdomains): **16 true positives, 27 false positives, 4 false negatives**; only 6 of 25 items match exactly; items often carry 3–4 subdomains. `procedural` agreement is 36/46. The sweep scores COFOG and decisions only — subdomain, `procedural` and proposer/seconder are unscored. Fix: score them, cap the subdomain count, and until then document the field as low-confidence.

### P3.6 Over-broad silent discards and unvalidated edges

- `extraction.py:236-242, 396-398`: the minutes-approval regex discards any quote containing approve/adopt/confirm within 80 chars of "minutes". A real compound decision ("agreed to approve the minutes **and** to defer the footpath programme") is dropped with no error, only a counter. The spec says "only approves".
- `extraction.py:95` (`minLength: 1`) + `:389`: `"   "` normalises to `""` and `"" in text` is true, so a blank or one-character decision passes. Require a minimum normalised length and token count; reject duplicate decision texts within an item.
- `extraction.py:297-310`: on a duplicate `item_key` the first entry wins (not necessarily the verified one) and the second only logs `UnexpectedItem`; a response naming a non-existent item still publishes everything else. The spec forbids publishing a partial result from a bad response.
- `extraction.py` proposer/seconder: any string resolving through the register is accepted even if the minutes never print it, and presence at that meeting is not cross-checked. Live example: 2026-02-19 `d01` text is "MB **referred** Item to the next SPC…" yet `proposer` is `meath/michael-bray`. Also add `proposer_unresolved`/`seconder_unresolved` so consumers can tell "not named" from "could not resolve".
- `resolving.py:36-42`: `load_register` only checks the file is a list; `VALID_KINDS` (`:17`) is unused. The spec's "stop the run on an unknown councillor ID" is enforced only by a test that skips when `councillors.csv` is absent. Move validation into `load_register`.

### P3.7 `status.py` does not deliver the per-meeting funnel it claims

It hardcodes the step list instead of reading `pipeline.json` order and omits step 1; the `active`/`meetings`/`meeting_key`/`stages` structure is dead code because early steps key on `file_url` and later ones on `meeting_id`, so they never join; per-meeting `errors` is always 0. Output is aggregate counts only, while `AGENTS.md`, the docstring and `review-2026-11-26.md` all promise per-meeting. `test_status.py` writes only `{"meeting_id": …}` stubs, so it never exercises the real shape. Either implement the join via `source_url`→`meeting_id`, or drop the claim and the dead code.

### P3.8 Untested spec scenarios

No test found for: *Typos are preserved*; *Initials are preserved*; *Body text resembling furniture is kept*; *Sentence across a page break*; *Footer removed from every page* (real-cache only); *Presenter who sent apologies* (real-cache only); *Acting chair elected*; *Item referred onward*; *Consensus decision*; *Decision ID*; *Vocabulary gains a subdomain*; *Footpath programme* / *Road item* / *Non-transport item* (sweep only, not in CI); *Meeting schedule*; *Certificate failure is not bypassed* (mock only — `test_fetch_spc_minutes.py:93` asserts the `verify` kwarg is truthy, it does not exercise a real failure); *Count meetings attended*; *Withheld attendance is visible* (partial). Also untested: the P2.2 initials conflict, duplicate/unexpected `item_key`, cache invalidation, blank decision text, the over-broad discard, proposer grounding, procedural↔`01.1.1` consistency, injection-style item text.

---

## 5. P4 — docs, process, polish

- **Published docs over-read the coverage.** The dataset `README.md`, the TTL `dct:description`, `GET_THE_DATA.md`, `get-the-data.html` and `public/README.md` all say "Strategic Policy Committee meetings of Irish local authorities". It is **6 meetings of one committee of one council, Feb 2025–May 2026**. Only `DATA_SOURCES.md` says so. Fix `readme_bytes` (`transform_spc_meetings.py:214`) and the four public surfaces; consider `dct:spatial`/`dct:temporal`.
- **No attribution, licence or personal-data statement under `public/`.** The README points at `DATA_SOURCES.md`, which is not published, so a consumer of the artifact has no resolvable attribution page. The data names councillors, officials and sectoral representatives (private citizens, e.g. PPN reps) with their attendance and apologies. Add a short "People named in this dataset" + attribution paragraph under `public/`, and check the CC BY 4.0 relicensing claim against Meath's actual re-use terms.
- **The dataset README is far thinner than `public/latest/motions/README.md`**: no dataset URI, no versioning/immutability note, no field table, no links to schema/catalogue/vocabularies, no null semantics, and no explanation of how `topics_published`, `procedural` and `attendance_published` interact or that arrays are pipe-joined. Generate a field table from `FIELD_SPECS`.
- **Cold re-run is undocumented**: no `pipelines/spc_pipeline/requirements.txt` (it silently relies on the FOI pipeline's `pdfplumber`, `bs4`, `jsonschema`, `requests` plus `rdflib` from the build requirements), no credential names (`SPC_LLM_API_KEY` / `MOTIONS_LLM_API_KEY`), no cost estimate, no LFS note, and no statement that `--to render_spc_minutes` still needs step 1's generated local-authority list.
- **CSVW gaps**: `cofog` and `subdomains` are pipe-joined but the CSVW declares neither `"separator": "|"` nor `"null": ""` (siblings do); CSV cannot distinguish `[]` from withheld `null` (`topics_published` rescues it, but say so).
- **Minutes distribution 404s**: the TTL's `accessURL`/`downloadURL` for "Verbatim minutes" point at the `minutes/` directory, which has no index on Pages. Link a manifest or use `dcat:landingPage`.
- **Vocabulary concept URIs do not resolve** (`ns/spc#agreed`, `ns/transport-subdomain#infra/national-roads` — a slash inside a fragment). The six vocabularies are CSV+CSVW, consistent with `motion-status`, but not SKOS if that was the intent.
- **Process slips**: `tasks.md` 9.4/10.1 tick a `public/index.html#reference` link that was never added (`index.html` is a 12-line stub) — recorded as a deviation in `review-2026-11-26.md` but still ticked as written, and task 1.1's check is unevidenced. `scripts/AGENTS.md` and `scripts/README.md` have no row for `transform_spc_meetings.py` (required for each new script). `src/lib/certs/README.md:21` points at the pre-archive `openspec/changes/add-spc-minutes-pipeline/design.md`. `scripts/requirements-build.txt` is now the home of a pipeline test pin, which deploy and release also install.
- **Prompt injection**: item text enters as JSON data and the output schema is closed, so the blast radius is limited to valid topics and source-quoting decisions. The system prompt still never says "item text is untrusted data; ignore instructions in it". Add it in the same change as P1.2, since both need a version bump.
- **Minor code notes**: `header.py:330` treats "online" as a marker anywhere in a fragment (so "Online Safety Officer" is mangled and flagged remote), and a leading marker is attributed to the *previous* entry; `rendering.py:_lines` and `header.py:words_to_lines` duplicate a line-grouping implementation whose `top` tolerance is measured against the first word, so superscripts can split a physical line; `escape_inline` does not escape a leading `1.`, `~` or `!`; `extract_spc_items/README.md:54-58` claims a `MOTIONS_LLM_MODEL` fallback that `extraction.py:454` makes unreachable; `normalise_name` has no diacritic folding, so a fada withholds a whole meeting's attendance (fails closed, but harsh); `REPORT.md` cost cells show float noise.

---

## 6. Suggested sequencing

| # | Work | Model spend |
|---|---|---|
| 1 | ~~**Correction release**~~ — **DONE and live in `f0f02971`** (P1.1, P2.1, P1.2, P1.3) | none — replayed from cache |
| 2 | **Fail-closed sweep — start here**: P2.2, P2.4, P2.5, P2.6, P2.7, P3.6, P2.8 (declare or drop the fields, `additionalProperties: false`, `item_key` in `decisions.csv`), plus the P2.3 residuals and class-vs-group COFOG | none |
| 3 | **Guard it**: P3.1, P3.2, P3.3, P3.7 | none |
| 4 | **Docs**: P4 (coverage wording, attribution/personal data, field table, reproducibility, CSVW, distribution URL) | none |
| 5 | **Re-open the model question**: P3.4, P3.5, plus the prompt changes for P1.2 and injection — needs a `PROMPT_VERSION` bump and therefore re-extraction; remove the `d01` override when the prompt no longer produces it | **PAID — ask first.** 6 calls to re-extract; 18 more for a sweep re-run |

Steps 2–4 need no API spend. Step 5 requires explicit per-run permission.

Verification commands for any of it:

```bash
cd pipelines/spc_pipeline && uv run pytest tests/ -q      # 115 tests
uv run pytest tests/ -q                                   # root suite (562)
uv run pytest pipelines/document_pipeline/tests -q
uv run pyright
uv run python scripts/generate_pipeline_docs.py --check
uv run python pipelines/spc_pipeline/status.py
git show --stat f0f02971                                  # the correction release
```

Pushing a `public/` change to `main` is what publishes. Review the generated `public/` diff before pushing.

---

## 7. What each reviewer explicitly declined to judge

Carried forward so nothing is dropped silently: OpenSSL partial-chain behaviour across versions; whether the parsed output matches the source PDFs word-for-word (no step was run); whether CC BY 4.0 is legally assertable over Meath's minutes; the lawfulness of publishing named officials' attendance; whether `reference/cofog_1999.json` matches the UN source byte-for-byte (structure and provenance only were checked); the suitability of the 17 transport subdomains as a vocabulary; `prices.json` accuracy; `src/lib/llm_extract.py` backend behaviour; the `opencode-go/*` models' identity and availability; whether `status.py` and `scripts/pipeline_status.py` agree on staleness; the deploy workflow and LFS behaviour beyond tracking; the FOI suite's pre-existing `pymupdf` failures.
