# generate_topics

Groups canonical FOI disclosure records into keyword-defined topics and writes a public-facing topics dataset.

## What it does

Reads `topics-config.json`, which defines a list of topics — each with a `slug`, a `label`, and a list of `keywords`. For each topic, scans all canonicalised FOI request records and selects those whose `request_description` contains at least one of the topic's keywords (case-insensitive substring match).

Matched records are sorted by `decision_date` descending (records without a date come last).

The results are written to two locations:
- `output.json` — the step's standard output with metadata.
- `public/topics.json` — the public-facing file consumed by the website, containing the full matched disclosure set for each topic.

## Input

`extract_disclosures_canonicalize/output.json` (read directly, not via the `--input` argument)

## Output

`output.json` and `public/topics.json` — a list of topic objects:

| Field | Description |
|---|---|
| `slug` | URL-safe topic identifier |
| `label` | Human-readable topic name |
| `keywords` | Keywords used to match records |
| `match_count` | Number of matched disclosure records |
| `disclosures` | Full list of matched records, sorted by `decision_date` descending |

## Notable files

- `topics-config.json` — the topic definitions (slug, label, keywords). Edit this file to add or modify topics.
