# extract_motions

Extracts the motions from each minutes document via LLM structured extraction, using the shared `lib.llm_extract.extract_json` client.

## What it does

1. For each transformed record (with `text`) from `transform_minutes_files`, sends one LLM request with a fixed system prompt (motion definition + JSON contract + closed-set `status_label`) and a user prompt built from the record's district/date and full text.
2. Parses the returned JSON `{"meeting_date": <ISO date|null>, "motions": [{motion_text, proposer, seconder, status_label}, …]}`.
3. **Resolves the meeting date**: a link-derived `meeting_date` is trusted as-is; otherwise the LLM's `meeting_date` is accepted only when it parses to a full calendar day (ISO or day-month-year). Month-only values are rejected — the date stays `null` and `canonicalize_motions` fails closed.
4. Emits one record per document: all input fields plus a `motions` list — or `motions: null` when the LLM response is unparseable/empty.

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
| `motions` | List of `{motion_text, proposer, seconder, status_label}`, or `null` on a failed extraction |

## Notable files

- `errors.json` — per-document extraction failures.
- Uses `src/lib/llm_extract.py` (env-configurable provider/model/key; sends `x-opencode-session` for the `opencode` provider).
