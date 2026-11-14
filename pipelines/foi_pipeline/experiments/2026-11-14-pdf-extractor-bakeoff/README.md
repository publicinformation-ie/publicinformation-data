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

## Task 4: stratified sample

`sample.py` draws 36 PDFs (seed 20261114, at most 3 per body) into `sample.json`: width_shift 7, fragments 6, split_words 6, header_repeat 5, clean_with_errors 6, clean_no_errors 6 (pdfplumber controls with zero canonicalize errors). Always included: RTE Q4 2018, RTE Q4 2019, Fingal 2016, Fingal 2024. 24 files have a Mistral cache hit and 5 are camelot_stream.

- Scoring is offline from transform `output.json` rows (all PDFs, same scorer as Task 3), not from `mistral_replay.json`, so clean controls could be scored too. Mechanism priority when several checks fail: width, fragments, split words, header repeat. Files failing only `column_type_purity` are excluded.
- header_repeat has only 5 eligible files under the per-body cap; width_shift got a 7th and one extra top-up file (Irish Rail, 2019 Procurement.pdf) was added to reach 36.
- `sha256` is the hash of the file bytes. The cache filename is sha256 of the URL.
- Cache seeding: 1 of the 36 files (the Irish Rail one) was copied read-only from the main checkout's cache; the other 35 were downloaded sequentially, 2 s apart, via `DisclosureFileCache.get_file_path`.
- Failed downloads: none (36/36 on disk).
