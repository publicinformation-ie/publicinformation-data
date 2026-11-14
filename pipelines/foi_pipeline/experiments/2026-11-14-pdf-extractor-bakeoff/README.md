# PDF extractor bake-off: replay cached Mistral OCR

## Hypothesis

Mistral OCR extracts the PDFs that currently produce `extract_disclosures_canonicalize_rows` errors more cleanly than pdfplumber/camelot. Cleanliness is measured label-free by `lib.table_structure.score_table` / `passes` (provisional thresholds), not by downstream errors.

## User decisions

- The last run was not meant to use Mistral, so the error PDFs were not a configuration regression.
- Mistral stays cache-only (`--allow-paid-ocr` required for paid calls); this experiment makes no network calls and needs no PDF bytes.

## Result (`replay_mistral_cache.py`)

Error PDFs: 327 (354 distinct error URLs; 26 non-PDF, 1 without a transform record). Cache hits: 208, matching the handoff figures.

Among the 208 cached PDFs, passing the structure scorer:

| clean via | count |
|---|---|
| Mistral | 74 |
| current extractor | 78 |
| both | 52 |
| neither | 108 |
| Mistral only | 22 |
| current only | 26 |

Mistral is not better than the current extractors on this set: it rescues 22 files but loses 26, and 108 of 208 stay unclean either way. The two extractors fail differently (current: width_uniformity, fragment_share, split_word_rate; Mistral: repeated_header_share is far more common, 56 vs 6, which suggests page-header stripping is a cheap Mistral fix). Per-body breakdown is in `results/mistral_replay.md`; per-file data in `results/mistral_replay.json`.

## Calibration notes

- Fingal County Council (552 errors) has 5 error PDFs, all cached, all fail both ways. Clean Fingal 2019-21 logs score width_uniformity 0.93-0.949, just under the provisional 0.95 threshold, so some "neither" results may be threshold-sensitive rather than truly broken.
- 119 of the 327 error PDFs have no cache hit and are unscored for Mistral; the top error body (RTE, 565 errors) has none cached.
- Many errors are mapping errors (e.g. UnrecognizedRequesterType), not extraction failures, so structure-clean files can still error.
