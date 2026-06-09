# PDF Extraction Comparison — 2026-06-09

Empirically compare camelot (lattice + stream) against pdfplumber for handling
multi-line PDF table rows. Uses a 30-file labeled ground truth.

## Setup

Ghostscript is already installed manually.

```bash
uv add camelot-py[cv]
```

## Phase 1: Generate sample

```bash
uv run python sample.py
```

This creates `pending_labels.jsonl` with one JSON object per sampled file. Each
object has a `rows` array pre-populated from pdfplumber extraction.

## Phase 2: Label

Open `pending_labels.jsonl` and fill in `merge_groups` for each file:

```json
{
  "file_url": "...",
  "merge_groups": [[3, 4], [7, 8, 9]]
}
```

- `[[3, 4]]` — rows 3 and 4 are fragments of one logical record; merge them
- `[[0, 1], [5, 6]]` — two separate merges
- `[]` — no merges needed (file is already correct)

A continuation row typically has most cells null and a few cells with text that
continues the row above. Only mark as continuation if you're certain. When in
doubt, leave as-is.

When done labeling, copy to `labels.jsonl`:

```bash
cp pending_labels.jsonl labels.jsonl
```

## Phase 3: Run comparison

```bash
uv run python run.py
```

Outputs `results.json` and prints a summary table.

## Phase 4: Corpus-wide proxy (optional)

```bash
uv run python run.py --all-pdfs lattice   # or: stream
```

Runs the chosen camelot flavor across all 1035 cached PDFs and reports the
reduction in null-heavy rows (rows where >50% of cells are null). Takes ~30 min.

## Decision threshold

Camelot is adopted if it beats pdfplumber by ≥5 files on row-count match,
with no regression on tier 3. A narrower win triggers the hybrid detection
approach (try lattice → check row count plausibility → fall back to pdfplumber).
