# Disclosure Page Discovery Experiment (2026-06-09)

Measures two fixes to the disclosure-page scorer against 13 county councils
that the algorithm currently misses.

## Background

Fourteen councils have discoverable FOI disclosure log pages the current
algorithm misses. Failures fall into two modes:
- **Scoring (A):** `publication` in NEGATIVE_TOKENS zeroes valid URLs
- **Navigation (C1/C2):** Log lives one hop behind the FOI section page

Note: Carlow County Council (body_id TBD) is not yet in the pipeline and
is excluded from this experiment.

## Approaches

| ID | Name | What it does |
|----|------|--------------|
| baseline | Baseline | Current `find_disclosure_link` unmodified |
| a | Scoring fix | Narrowed `publication` suppression + `responses`/`released` tokens |
| c1 | Two-hop crawl | Second pass following FOI section links on miss |
| c2 | Apify depth-2 | `apify~cheerio-scraper` maxCrawlDepth=2 starting from FOI page |
| ac1 | A + C1 | Scoring fix with two-hop fallback |
| ac2 | A + C2 | Scoring fix with Apify depth fallback |

## Usage

Run from `foi_pipeline/`:

```bash
uv run python experiments/2026-06-09-disclosure-page-discovery/run_experiment.py --approach all
uv run python experiments/2026-06-09-disclosure-page-discovery/run_experiment.py --approach a
uv run python experiments/2026-06-09-disclosure-page-discovery/run_experiment.py --approach c1
uv run python experiments/2026-06-09-disclosure-page-discovery/run_experiment.py --approach c2
uv run python experiments/2026-06-09-disclosure-page-discovery/run_experiment.py --approach ac1
uv run python experiments/2026-06-09-disclosure-page-discovery/run_experiment.py --approach ac2
uv run python experiments/2026-06-09-disclosure-page-discovery/run_experiment.py \
    --approach ac1 --bodies 1129,1132,1133,1134,1135,1141,1143,1145,1149,1153,1155,1156,1157

uv run python experiments/2026-06-09-disclosure-page-discovery/report.py
```

C2 requires `APIFY_TOKEN` env var and consumes Apify credits.
