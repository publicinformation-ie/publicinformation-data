# extract_motions

Extracts the motions from each minutes document via LLM structured extraction, using the shared `lib.llm_extract.extract_json` client.

## What it does

1. For each transformed record (with `text`) from `transform_minutes_files`, sends one LLM request per chunk. Documents at or below 80,000 characters are one chunk and keep the original prompt. The request uses a fixed system prompt (motion definition + JSON contract + closed-set `status_label`) and a user prompt built from the record's district/date and chunk text.
2. Parses the returned JSON `{"meeting_date": <ISO date|null>, "motions": [{motion_text, proposer, seconder, status_label}, …]}`.
3. **Resolves the meeting date**: a link-derived `meeting_date` is trusted as-is; otherwise the LLM's `meeting_date` is accepted only when it parses to a full calendar day (ISO or day-month-year). Month-only values are rejected — the date stays `null` and `canonicalize_motions` fails closed.
4. Emits one record per document: all input fields plus a `motions` list — or `motions: null` when the LLM response is unparseable/empty, or when a document guard quarantines it.

## Chunking

Documents longer than 80,000 characters are split by `chunking.split_text`:

- maximum 80,000 characters per chunk, 4,000-character overlap;
- split on a paragraph break, then a newline, in the second half of the
  window, else hard cut;
- the prompt asks for **complete motions fully contained in the part**, so a
  motion crossing a boundary is not extracted twice or truncated;
- results merge in chunk order; exact duplicate motion texts across chunks are
  dropped; within-chunk repeats are kept;
- `stated_date` is the first non-null date reported by any chunk.

If any chunk fails, the whole document yields `motions: null`; `errors.json`
records the failed chunk numbers and total chunk count. Partial motion lists
are never emitted.

**Cost note:** chunking does not reduce token spend. It adds overlap and a
repeated system prompt (roughly +1–2% for the current pending corpus) and is
for context-window reliability. Use the cheapest acceptable model from
`experiments/2026-10-07-motion-model-sweep/README.md` for cost.

## Two-stage guard

Some development-plan documents are not ordinary minutes: they are schedules
where every material alteration is recorded as an "Item Resolved" and the same
proposal/seconder pair is repeated hundreds of times. Extracting those as
motions produces a procedural dump (the Kildare 9 December 2022 CDP schedule
produced 879 rows, 96.7% proposed by one councillor and 96.9% seconded by
another). Two deterministic guards quarantine that pattern without excluding
ordinary special or planning meetings.

1. **Pre-LLM CE-schedule filter.** Skip the document before any model call when
   the text contains at least 500 `Proposed Material Alteration No.` mentions,
   200 `accept the Chief Executive` mentions, and 200 `On the proposal by`
   mentions. This is an extreme threshold; the next-highest document in the
   corpus has 122 numbered alterations. The record gets `motions: null`,
   `skip_reason: "ce_recommendation_schedule"`, and `guard_evidence` counts.
2. **Post-extraction procedural-dump quarantine.** After extraction, quarantine
   the document when it has at least 100 motions and:
   - at least 80% contain "accept the Chief Executive";
   - at least 80% mention a PMA, material alteration, or consequential
     amendment; and
   - at least 80% share one proposer and at least 80% share one seconder.

   The record gets `motions: null`,
   `skip_reason: "procedural_acceptance_dump"`, `chunk_count`, and
   `guard_evidence` counts/ratios.

Both guards write a `MotionExtractionSkipped` entry to `errors.json` with the
`skip_reason` and `guard_evidence`. `canonicalize_motions` turns the record into
a `SkippedDocument` error, so no motions reach the published dataset. The
pre-filter avoids the LLM call entirely; the post-filter is the safety net for
similar documents that use different wording or fewer PMAs.

The thresholds live in `guards.py`. They are intentionally conservative: the
guards preserve the Kildare 24 February 2022 CE report (11 motions, 9
substantive), the 25 March 2024 meeting (115 motions), the 12 September 2022
meeting (113), and the 15 December 2025 meeting (97). Review the
`MotionExtractionSkipped` entries before changing a threshold; a confirmed
false positive needs a human decision, not a lower threshold.

## Fail-closed policy

A failed or unparseable LLM response produces `motions: null` **and** a per-document `errors.json` entry (`MotionExtractionError`). The whole document is treated as no-motions rather than guessing a partial record.

**Resume behaviour:** a document that yields `motions: null` is still marked
processed (keyed on `file_url`), so a resumed run does *not* retry it. To
re-attempt failed documents, re-run the step with `--force`.

## Input

- `ocr_minutes_files/output.json` (generated upstream)

## Output

`output.json` — `{ metadata, results: [...] }`, one record per document with the input fields plus:

| Field | Description |
|---|---|
| `motions` | List of `{motion_text, proposer, seconder, status_label}`, or `null` on a failed extraction or guard quarantine |
| `skip_reason` | `ce_recommendation_schedule` or `procedural_acceptance_dump` when a guard quarantined the document; absent otherwise |
| `guard_evidence` | Counts/ratios supporting a guard quarantine; absent otherwise |

## Notable files

- `errors.json` — per-document extraction failures and guard skips.
- `guards.py` — deterministic pre-LLM and post-extraction guard thresholds.
- Uses `src/lib/llm_extract.py` (env-configurable provider/model/key; sends `x-opencode-session` for the `opencode` provider).
