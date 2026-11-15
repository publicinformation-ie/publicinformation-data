# Gating round 1: body 1594, non-personal FOI requests 2017 to 2020

Cluster `1594-non-personal-2017-2020` (4 files, 567 recoverable records). See `diagnosis-input.md`.

## Hypothesis

**Fault kind: G (gate).** The four files fail only `role_contamination` under three different extractors,
with `date_received` contaminated at 0.99 to 1.0 while every row is anchored. The 2018 dump shows
`date_received` cells like `04-Jan-18` classified by `cell_kinds` as `reference`, not `date`.
`lib.value_kinds._is_date` reads numeric dd/mm/yyyy and `parse_date` deadline phrases, not `DD-Mon-YY`;
`_is_reference` then matches a single token with digits and `-`. The downstream normaliser already parses
`DD-Mon-YY` (`extract_disclosures_normalize_rows`), so the data is fine and the scorer is wrong.
This points away from an extractor fault (all extractors map column 1 correctly, only camelot_stream differs).

Side note: row 0 is a title row ("FOI Requests - 2018"), the true header is row 1; the header detector handles it.

## Competing fixes

`current`, `force:pdfplumber`, `force:pymupdf`, `force:camelot_lattice`, `force:camelot_stream`, `force:mistral_cache`,
`docling`, and `gate-dd-mon-yy` (round `fixes.py`; global scope, so it needs a full before/after over all bodies
before any shipping).
