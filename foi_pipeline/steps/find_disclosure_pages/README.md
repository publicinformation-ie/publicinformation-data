# find_disclosure_pages

Locates the FOI disclosure log page for each public body — the page that lists what FOI requests have been released.

## What it does

For each body, tries two strategies in order:

1. **Domain-specific logic** (`domains.py`) — hardcoded rules for known site structures (e.g. gov.ie path patterns). Returns a URL directly without an HTTP request if the domain is recognised.
2. **Crawl fallback** — fetches the FOI page, tokenizes every link's href and anchor text, and scores each candidate against a tiered vocabulary. Returns the highest-scoring link above a threshold (score ≥ 40). Tier scores: `disclosure`+`log` → 100, `foi`+`log` → 90, `foi`+`decision` → 80, `published`+`foi` → 70, `disclosure` alone → 40. Token-splitting (not substring matching) prevents false positives: `log` in `login`, `blog`, `logo`, `technology`, `geology` is never triggered. Negative tokens (`protected`, `scheme`, `form`, `login`, `guide`, `how`, `make`, etc.) immediately disqualify a link regardless of other tokens.

If neither strategy finds a distinct disclosure page, the FOI page URL itself is used as the disclosure page (common when a body publishes its log directly on the FOI page).

Supports **incremental resumption** and propagates upstream `dirty_ids` to invalidate stale downstream results when a body's FOI page changes.

## Input

`get_foi_emails/output.json`

## Output

`output.json` — `{ metadata, results: [...] }`. Each record:

| Field | Description |
|---|---|
| `public_body_id` | Body identifier |
| `name` | Body name |
| `foi_page_url` | The body's FOI page |
| `disclosure_page_url` | The discovered disclosure log page |

## Notable files

- `domains.py` — domain-specific URL resolution rules.
- `override.json` — manually verified disclosure page URLs.
- `errors.json` — network or validation errors.
- `output_schema.json` — JSON Schema for the output format.

## Evaluation

The crawl matcher is measured offline against a labelled eval set, so changes
to scoring can be validated without hitting the network.

- `eval/labels.csv` — ground-truth labels (`distinct_log` / `use_foi_page` /
  `no_log_exists`) per body. Regenerate the scaffold with
  `eval/gen_labels_scaffold.py`, then label from page **content** (not slugs)
  via an LLM labeler anchored to the frozen gold subset, with a spot-check.
- `eval/fixtures/{id}.html` — cached FOI-page HTML (`eval/capture_fixtures.py`).
- `eval/run_matcher.py` — runs the matcher over fixtures → `matcher_output.json`.
- `eval/evaluate.py` — prints precision / recall / F1 + FP/FN lists.

Baseline (scored matcher, 2026-05-28): precision=0.500 recall=0.674 f1=0.574
(TP=29 FP=29 FN=14 TN=50, 122 labelled bodies evaluated)

Iteration loop:

    edit process.py -> run_matcher.py -> evaluate.py -> compare to last run -> keep or revert

Tune `_score_link`, `NEGATIVE_TOKENS`, and `ACCEPT_THRESHOLD` one change at a
time, re-running evaluate.py to confirm precision rises without collapsing recall.
