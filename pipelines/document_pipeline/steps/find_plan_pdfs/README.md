# find_plan_pdfs

Searches for each plan/strategy listed in `input_plans.md` and resolves it to a gov.ie source PDF URL, using a single batched Apify run. First step in `document_pipeline`.

## What it does

1. **Parse** — reads `input_plans.md` via `plans.load_plans()`: one record per `(department, title)` table row.
2. **doc_slug generation** — `f"{slugify(department)}-{slugify(title)}"`. A plan whose `doc_slug` already exists in `documents.yml` is skipped (not emitted) — `documents.yml` always wins. A second plan that lands on an already-generated `doc_slug` is logged as `DuplicateDocSlug` and skipped.
3. **Batch search** — for each remaining plan, builds the query `site:gov.ie "<title>" filetype:pdf` and submits all queries in a single Apify `google-search-scraper` Actor run.
4. **URL filtering** — picks the first search result whose URL is a safe URL, on a gov.ie (sub)domain, and ends in `.pdf` (case-insensitive). No match → `errors.json` entry (`PlanPdfNotFound`).

Supports **incremental resumption**, **`--force`**, and **`--doc`** (scoped re-run of one generated `doc_slug`).

## Environment

`APIFY_TOKEN` — required. Set to your Apify API token. Raises clearly if missing (only when at least one plan needs searching).

## Input

`input_plans.md` (repo root of `document_pipeline`), via `plans.load_plans()`.
`documents.yml`, via `documents.load_documents()` — used only to compute already-curated `doc_slug`s to skip.

## Output

`output.json` — `{ metadata, results: [...] }`. Each record:

| Field | Description |
|---|---|
| `doc_slug` | Generated per above; permanent once a document downstream of it is published |
| `title` | Plan title, verbatim from `input_plans.md` |
| `department` | Department name, verbatim from `input_plans.md` |
| `url` | Discovered PDF URL |
| `publisher` | `null` — no body lookup performed |
| `public_body_id` | `null` — no body lookup performed |
| `published_date` | `null` — not derivable from search results |
| `source_method` | `"apify"`, or `"manual"` for an `override.json` entry |

## Notable files

- `errors.json` — one entry per skipped plan. `error_type` is `PlanPdfNotFound` (no gov.ie PDF result) or `DuplicateDocSlug` (doc_slug collision between two plans). Truncated to `[]` at the start of every run.
- `override.json` — manually verified plan PDF URLs that take precedence over automated results. Keyed by `doc_slug`; each record must include `"source_method": "manual"`.
- `output_schema.json` — JSON Schema for the output format; validates `override.json` records on load.

## Relationship to `fetch_pdfs`

`fetch_pdfs` merges this step's `output.json` with `documents.yml`, with `documents.yml` winning on `doc_slug` collision. See `fetch_pdfs/README.md`.
