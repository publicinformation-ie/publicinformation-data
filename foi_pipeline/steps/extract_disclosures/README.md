# extract_disclosures

> **Status: stub — not yet implemented.**

This step is reserved for future extraction of FOI disclosure records from PDF files. Currently it acts as a pass-through that writes an empty result set.

## Intended purpose

Once implemented, this step will parse PDF disclosure log files (those with `rows: null` from `transform_disclosure_files`) and extract structured FOI request records from them, feeding into the same canonicalisation pipeline as the spreadsheet-based records.

## Input

`transform_disclosure_files/output.json`

## Output

`output.json` — `{ metadata, results: [] }` (always empty in the current stub implementation).
