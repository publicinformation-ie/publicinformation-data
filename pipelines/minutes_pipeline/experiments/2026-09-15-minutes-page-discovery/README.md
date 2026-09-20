# Minutes Page Discovery Experiment (2026-09-15)

Compares page-discovery approaches for the 31 local authorities (+ Meath districts) using offline PDF-yield scoring from `find_meeting_minutes_pages_search/eval/`.

## Approaches

| ID | Name | What it does |
|----|------|--------------|
| baseline | Baseline | Current `find_minutes_link` over homepage fixtures |
| one_hop | One-hop follow | Baseline, else follow best hub link once (cached hub fixtures) |
| two_hop | Two-hop BFS | Baseline, else BFS to depth 2; first PDF-yield-positive page wins |
| apify_rerank | Apify rerank | Live top-5 search candidates reranked by PDF-yield (needs `APIFY_TOKEN`) |

## Usage

Run from `minutes_pipeline/`:

```bash
uv run python experiments/2026-09-15-minutes-page-discovery/run_experiment.py --approach baseline
uv run python experiments/2026-09-15-minutes-page-discovery/run_experiment.py --approach all
uv run python experiments/2026-09-15-minutes-page-discovery/report.py
```

`apify_rerank` requires `APIFY_TOKEN` and consumes Apify credits; all other approaches are offline.

## Promote loop (manual, no auto-promote)

Winner = highest F1 without regressing the full labelled set. Promote by hand: edit `steps/find_meeting_minutes_pages_search/process.py` (or `steps/find_meeting_minutes_pages/process.py`), re-run `eval/run_matcher.py`, re-run `eval/evaluate.py`, keep on F1 gain else revert.
