# find_foi_email_pages

Recovers a contact email for bodies where `get_foi_emails` reached the FOI page but found no email on it (`email_status: "not_found"`) — the email lives on a linked contact/FOI-officer page instead.

## What it does

For each `not_found` record:

1. Fetches the FOI page and tokenizes every link's href + anchor text (shared `_tokenize` from `find_disclosure_pages`).
2. Scores each link: `foi`/`freedom` + `contact`/`officer`/`unit`/`team` → 100; `contact` + `officer`/`unit`/`team` → 80; `contact`/`contacts` alone → 50; `officer`/`unit`/`team`/`staff`/`directory` alone → 40; any negative token (`login`, `blog`, `scheme`, `guidance`, etc.) → 0. Rejects same-page anchors, document links (`.pdf`/`.docx`/`.xlsx`/`.xls`/`.odt`/`.doc`), and unsafe URLs.
3. Tries up to 3 candidates, highest-scoring first, running `get_foi_emails`'s own `extract_emails()`/`pick_foi_email()` against each. Stops at the first one that yields a found email.
4. If nothing is found, the record is written back exactly as `get_foi_emails` produced it — this step never downgrades a result.

Every other record (`found`, `multiple_found`, `invalid`) passes through unchanged.

Crawl-only in this version — no Apify fallback (candidate follow-up work, same shape as `find_disclosure_pages/domains.py`).

Supports incremental resumption and propagates upstream `dirty_ids` to invalidate stale results when a body's `get_foi_emails` record changes.

## Input

`get_foi_emails/output.json`

## Output

`output.json` — `{ metadata, results: [...] }`. Each record:

| Field | Description |
|---|---|
| `public_body_id` | Body identifier |
| `name` | Body name |
| `foi_page_url` | The body's FOI page |
| `foi_email` | Extracted email, or `null` |
| `email_status` | `found` / `not_found` / `multiple_found` / `invalid` |
| `confidence` | `high` / `medium` / `none` — present only on records this step upgraded |
| `source_page_url` | The contact/FOI-officer page the email was found on — present only alongside `confidence` |

`confidence` tiers:

- **`high`** — winning candidate link scored on `foi`/`freedom` tokens (100) and the found email itself contains `foi`/`freedom`.
- **`medium`** — winning link scored 100 but the email is a generic inbox.
- **`none`** — winning link only matched generic `contact`/`officer` tokens (40-80). Still written (not discarded) so it's visible for correction via `override.json`.

## Notable files

- `override.json` — manually verified email overrides for bodies this step gets wrong or can't reach.
- `errors.json` — network errors, cleared at the start of each run.
- `output_schema.json` — JSON Schema for the output format.

## Evaluation

- `eval/labels.csv` — ground-truth labels (`found` / `wrong_match` / `no_email_exists` / `should_have_found`) per body.
- `eval/gen_labels_scaffold.py` — seeds `labels.csv` from `output.json` + known verified experiment results.
- `eval/capture_fixtures.py` — caches FOI-page + winning-candidate HTML (`eval/fixtures/{id}.html`, `eval/fixtures/{id}_candidate.html`).
- `eval/run_matcher.py` — runs the scorer/extractor over cached fixtures → `matcher_output.json`. No network calls.
- `eval/evaluate.py` — prints precision/recall/F1 against `labels.csv`.

Iteration loop:

    edit process.py -> run_matcher.py -> evaluate.py -> compare to last run -> keep or revert

Baseline (scored matcher, 2026-07-24): precision=0.500 recall=0.778 f1=0.609
(TP=7 FP=7 FN=2 TN=31, 47 labelled bodies evaluated)

Note: `get_foi_emails.process.pick_foi_email()` picks the first FOI-keyword-matching
email from a Python `set()`, whose iteration order depends on per-process hash
randomization. When a candidate page has multiple FOI-keyword emails (e.g. body 1736,
which has both `foi@sivuh.ie` and `foi.officer@sivuh.ie`), `matcher_output.json` can
drift by a body or two on re-runs with no code changes. This is a pre-existing issue in
`get_foi_emails` (reused as-is here), out of scope for this plan — candidate for a
future fix-issue pass.
