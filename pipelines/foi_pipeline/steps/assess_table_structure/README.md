# assess_table_structure

Pass-through gate placed directly after `transform_disclosure_files`. Scores each
record's `rows` with `lib.table_structure.score_table` and adds
`table_structure` (the score as a dict).

Fail closed: a `file_type == "pdf"` record that fails `DEFAULT_THRESHOLDS` gets
`rows: []` and `table_structure_unreliable: true`, so downstream steps emit no
data rows for it. xlsx/xls records are scored but never emptied. Records with
`rows: null` or `rows: []` pass through untouched and unscored.

## What gates and what only records

Only **structural** checks reject a file (`failed_checks`): `min_rows`,
`width_uniformity`, `fragment_share`, `column_type_purity` and
`split_word_rate`. The last one measures `cross_cell_split_rate`: a word broken
by a column boundary, counted only when one side is a word stub of 3 letters or
fewer that is not a common word (`S` | `ummary` counts; `Journalist` | `all
records` does not). `split_word_rate` on a score is a deprecated alias for it.

Two signals are recorded in every score but never reject:

- `run_together_rate`: run-together tokens inside a cell (`informaQon`,
  `andThe`). A text defect; repair belongs in `normalize_disclosure_cells`. Use it
  to find accepted files with poor text.
- `repeated_header_share`: share of rows equal to the header (header repeated on
  each page), measured before those rows are removed. They are removed before the
  structural checks run, as `extract_disclosures_canonicalize` does anyway.
  `Thresholds.max_repeated_header_share` is kept so stored threshold reports parse
  but `failed_checks` ignores it.

Both still feed `composite`, so candidate selection prefers cleaner text. Files
with a manual column mapping are exempt from the gate.

`errors.json` holds exactly one `TableStructureUnreliable` entry per excluded
file (context: `public_body_id`, `file_url`, `pdf_extractor`, `failed_checks`,
`score`). It is rebuilt from the final `output.json` on every run, so reruns,
resumes and scoped runs cannot duplicate entries.
