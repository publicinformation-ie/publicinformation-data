# Document Pipeline — Experiments

Experiments live in dated subdirectories (`YYYY-MM-DD-<slug>/`). Each has its
own `README.md` with hypothesis, results, and conclusion. Results files live
under `experiments/<date-slug>/results/` and are gitignored (regenerable).

## Index

| Date | Experiment | Outcome |
|------|-----------|---------|
| 2026-10-17 | [toc-splitting-comparison](2026-10-17-toc-splitting-comparison/) | TOC-name strategy viable: number-tolerant matching, numbering-only supplement, first-contiguous-TOC-block; `gda-cycle-network-plan-2022` 201→21 nodes |

## Adding a new experiment

1. Create `experiments/YYYY-MM-DD-<slug>/`.
2. Add `README.md` with hypothesis, method, actionability criteria, and
   reproduce instructions.
3. Write a read-only `run.py` that reads cached pipeline output
   (`steps/extract_pages/output.json` + its page sidecars), never writing to
   any step's `output.json`/`errors.json` — only its own `results/`.
4. After running, fill in the Results and Conclusion sections.
5. Add a row to the index table above.
