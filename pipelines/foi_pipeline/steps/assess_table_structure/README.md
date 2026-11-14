# assess_table_structure

Pass-through gate placed directly after `transform_disclosure_files`. Scores each
record's `rows` with `lib.table_structure.score_table` and adds
`table_structure` (the score as a dict).

Fail closed: a `file_type == "pdf"` record that fails `DEFAULT_THRESHOLDS` gets
`rows: []` and `table_structure_unreliable: true`, so downstream steps emit no
data rows for it. xlsx/xls records are scored but never emptied. Records with
`rows: null` or `rows: []` pass through untouched and unscored.

`errors.json` holds exactly one `TableStructureUnreliable` entry per excluded
file (context: `public_body_id`, `file_url`, `pdf_extractor`, `failed_checks`,
`score`). It is rebuilt from the final `output.json` on every run, so reruns,
resumes and scoped runs cannot duplicate entries.
