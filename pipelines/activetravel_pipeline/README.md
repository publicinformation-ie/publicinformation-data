# activetravel_pipeline

Turns the National Transport Authority's annual Active Travel Investment Grant
allocation PDFs into a verified, project-level dataset published as
`public/latest/active-travel-allocations/`.

Every published record is arithmetically confirmed by the document it came from.
That is the whole design: the PDFs declare a total for each authority (and, from
2025, a per-recipient summary in the front matter), so extraction can be checked
against the source's own sums instead of trusted. **Anything published is
complete for its recipient, year and funding stream, and adds up.** Whatever
fails that test is withheld and reported with both sums and the difference.

## Steps

| # | Step | What it does |
|---:|---|---|
| 1 | `fetch_grant_documents` | Reads the committed publication list and caches each PDF; records its SHA-256 |
| 2 | `extract_grant_tables` | `pdfplumber` per page, gated structurally; separates project tables from the front-matter summary |
| 3 | `classify_grant_rows` | Gives every row exactly one kind (title, header, heading, divider, project, anchor, footnote, blank) |
| 4 | `normalize_grant_amounts` | Reads every printed amount as whole euro; applies committed repairs; withholds what it cannot read |
| 5 | `segment_funding_streams` | Groups project rows into recipient sections and anchor-bounded blocks, and assigns each block a funding stream |
| 6 | `resolve_recipients` | Attributes each row from the section heading *and* the project-code prefix; links local authorities to public bodies |
| 7 | `reconcile_sections` | Publishes a stream only when its rows equal the declared total (and each printed subtotal) |
| 8 | `reconcile_summary` | Compares the 2025/2026 per-recipient summary with the extracted active-travel totals |
| 9 | `canonicalize_allocations` | Builds the stable `@id`, flags provisional codes, drops exact duplicate rows |
| 10 | `export_allocations` | Emits the fixed record shape the publisher reads |

## Committed inputs

| File | Why it is committed |
|---|---|
| `steps/fetch_grant_documents/publications.json` | The only ingestion source. Adding a year is an edit here, never a code change. |
| `steps/resolve_recipients/recipient_aliases.json` | Canonical recipient names plus the spelling variants the documents print. A canonical local-authority name must match the public-bodies register. |
| `steps/resolve_recipients/code_prefixes.json` | Project-code prefix → recipient(s). `LCC` is the only genuine collision (Limerick's prefix, also printed on Louth's provisional 2022 codes). |
| `steps/reconcile_sections/row_repairs.json` | Manually confirmed corrections, keyed by document, page and row. `set_amount` is applied by step 4, `drop_row` by step 7. |

## Running

The runner defaults to the current directory, so either pass the pipeline
directory or run from inside it:

```bash
# From the repo root:
uv run python pipelines/activetravel_pipeline/process.py pipelines/activetravel_pipeline --force --stop-on-error

# From the pipeline directory:
cd pipelines/activetravel_pipeline && uv run python process.py --force --stop-on-error

# One edition only (the natural unit here — one document per year):
uv run python pipelines/activetravel_pipeline/process.py pipelines/activetravel_pipeline --force --stop-on-error --doc nta-active-travel-2026

# From a step onwards:
uv run python pipelines/activetravel_pipeline/process.py pipelines/activetravel_pipeline --from reconcile_sections --force --stop-on-error
```

`--doc` takes a `document_id` from `publications.json`. Always pass
`--force` with `--doc`: the runner's staleness check is mtime-based and does not
know about per-document freshness.

Triage with the status script before reading any step's JSON:

```bash
uv run python pipelines/activetravel_pipeline/status.py --all
uv run python pipelines/activetravel_pipeline/status.py --document 2026
```

It prints one row per document (extract → classify → amounts → streams →
recipients → reconcile → summary → canonical → export), that document's errors
per step, and a dry-step verdict. Exit code 1 means a document ran dry.

## Fetching and the cache

`fetch_grant_documents` writes each PDF to `pipelines/activetravel_pipeline/cache/`
(git-ignored), keyed by the document URL, and reuses it without a network call
on later runs. The observed digest is recorded in the step output and on every
published record rather than pinned in configuration: a reissued PDF then shows
up as a digest change for review instead of blocking the annual run.

The published dataset is built by `scripts/transform_active_travel_allocations.py`,
which reads `steps/export_allocations/output.json`. Merging the resulting
`public/` change is what publishes it.

## What is deliberately not published

- **A stream that does not reconcile.** Later editions declare money for
  other-NTA-funding-streams blocks whose project rows they do not print (Cork
  County 2026, Dublin City 2026, Wicklow 2026, Kerry 2025, Longford 2025,
  Wexford 2025). Those blocks are withheld; the authority's active-travel block
  still publishes.
- **Rows whose amount cannot be read.** A project row printed `N/A*`, `€ -`, with
  a blank amount, or with a project name overflowing into the amount column is
  withheld. Nine 2022/2026 overflow cells are recovered by `row_repairs.json`,
  each confirmed by the section's declared total.
- **A table with no declared total.** The 2024 Galway County table prints no
  total at all, so nothing in it can be confirmed.
- **The 2022 Annex 1.** It is a *programme* budget view (€289.0m across A3.1–A3.4
  by GDA/regional/rural split). The 2022 project tables total €387.8m, so the
  annex is a different view of the money, not a control on it. It is cached for
  provenance, declared `programme_summary`, never extracted as project rows and
  never compared. Building that comparison would produce a permanent false
  failure.

## Tests

```bash
uv run pytest pipelines/activetravel_pipeline/tests -q
```

The extraction, classification, segmentation and reconciliation tests run from
`tests/fixtures/real_pages.json` (verbatim rows from a few pages of each
document), so they need no downloaded PDF. The end-to-end test runs the whole
chain over the cached documents and is skipped where the cache has not been
fetched — see `tests/README.md`.
