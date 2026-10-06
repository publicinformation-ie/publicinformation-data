# PublicInformation.ie Open Data

Open data on Irish public bodies and how they handle Freedom of Information
requests, extracted from thousands of public bodies' own published records.

The same files are served programmatically at
`https://data.publicinformation.ie/…` — every relative link below resolves
there exactly as it does when browsed here on GitHub.

## Datasets

| Dataset | Contents |
|---|---|
| [Public Bodies](latest/public-bodies/README.md) | Every public body in Ireland: its name, whether it handles FOI requests, and its FOI contact email. |
| [FOI Disclosures](latest/foi-disclosures/README.md) | Records of information already released under FOI: what was asked, who asked, when, and the outcome. |
| [FOI Request Files](latest/foi-request-files/README.md) | The original source documents each disclosure record came from. |
| [Who Does What](latest/who-does-what/README.md) | Links from each public body to its page on the Government's "Who Does What" directory. |
| [data.gov.ie Links](latest/data-gov-ie-links/README.md) | Links from each public body to its organisation page on data.gov.ie, Ireland's open data portal. |
| [lobbying.ie Links](latest/lobbying-ie-links/README.md) | Links from each public body to its page on lobbying.ie, Ireland's Register of Lobbying. |
| [Public Body Actions](latest/public-body-actions/README.md) | The published commitments ("actions") of public bodies, taken from their strategy and action-plan documents, with status updates from later progress reports. |
| [Motions](latest/motions/README.md) | Motions moved at meetings of Irish local authorities, from the authorities' published meeting minutes. |

## Guides

- [Get the Data](GET_THE_DATA.md) — spreadsheet-ready downloads, no technical background needed.
- [Developer Quickstart](QUICKSTART.md) — a runnable code example to fetch and use the data programmatically.
- [Data Quality](DATA_QUALITY.md) — how extraction quality is tracked, and how to report or fix an issue.

## Raw pipeline outputs

Machine-readable dumps of the pipeline's working state, for debugging and
provenance rather than everyday use:

- [pipeline-data.json](pipeline-data.json) — per-body processing status.
- [foi-disclosures.json](foi-disclosures.json) — disclosure records.
- [disclosure-files.json](disclosure-files.json) — source documents discovered and processed.
- [topics.json](topics.json) — generated disclosure topics.

## Technical reference

- [catalog/](catalog/) — DCAT dataset descriptions.
- [schemas/](schemas/) — JSON schemas for the datasets.
- [vocabularies/](vocabularies/) — controlled vocabularies and term URIs.
- [CHANGELOG.md](CHANGELOG.md) — release history.
- [LICENSE](LICENSE) — licence terms.

## `latest/` vs versioned snapshots

`latest/<dataset>/` always points at the newest release — use it for a stable
URL that never breaks. A versioned path like `v2.0.0/public-bodies/` is a
pinned reference — use it when you need to guarantee you're always reading
exactly the same bytes, regardless of future releases.
