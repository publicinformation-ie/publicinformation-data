# Data Quality & Contributing

This data is extracted automatically from thousands of PDFs and spreadsheets
published by hundreds of individual public bodies, each with their own
formatting. Extraction errors are expected. Rather than hide them, this
pipeline publishes exactly what it could and could not process, so problems
are inspectable instead of silent.

## The two levels of quality signal

### Dataset-level: did a body produce data at all?

[`pipeline-data.json`](pipeline-data.json) records,
per public body, whether each processing stage succeeded or failed:
finding its website, its FOI page, its FOI contact email, its disclosures
page, its disclosure files, and its FOI requests. This tells you
*coverage* — which bodies produced data and where extraction
stopped for the ones that didn't.

[`disclosure-files.json`](disclosure-files.json)
lists the source documents the pipeline discovered and attempted to
process, so you can see exactly what went in.

### Per-record: how confident is this one row?

Individual records in the FOI Disclosures dataset carry
`known_issues` and `missing_columns` fields. These
are **per-record extraction-confidence signals, not a global
quality score** — a flagged record is not necessarily wrong, only
less certain in the specific way flagged. See the
[FOI Disclosures README](latest/foi-disclosures/README.md)'s
Known Limitations section for the authoritative explanation.

These two levels answer different questions and should never be combined
into one number: knowing a body's disclosure files failed to process tells
you nothing about the confidence of any individual record, and vice versa.

## Report a problem or contribute an improvement

Spotted a wrong record, a missing body, or anything else that looks off?
Report it or suggest a fix at
[www.publicinformation.ie](https://www.publicinformation.ie) —
no technical knowledge or git required.

Want to change how the pipeline itself works? The source code is at the
[GitHub repository](https://github.com/publicinformation-ie/publicinformation-data).
