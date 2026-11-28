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
| [datacatalogue.gov.ie Links](latest/datacatalogue-gov-ie-links/README.md) | Links from each public body to its organisation page on datacatalogue.gov.ie, the Public Service Data Catalogue of the data public sector bodies hold. |
| [lobbying.ie Links](latest/lobbying-ie-links/README.md) | Links from each public body to its page on lobbying.ie, Ireland's Register of Lobbying. |
| [Staff Numbers](latest/staff-numbers/README.md) | Full-time-equivalent staff numbers for public bodies in the latest reported quarter, from the Department of Public Expenditure's public service numbers file. |
| [Public Body Actions](latest/public-body-actions/README.md) | The published commitments ("actions") of public bodies, taken from their strategy and action-plan documents, with status updates from later progress reports. |
| [Motions](latest/motions/README.md) | Motions moved at meetings of Irish local authorities, from the authorities' published meeting minutes. |
| [SPC Meetings](latest/spc-meetings/README.md) | Strategic Policy Committee meetings of three county councils, February 2025 to May 2026: Meath County Council (Transportation and Urban Regeneration), Kildare County Council (Transport, Mobility and Open Spaces) and Westmeath County Council (Planning, Regeneration & Transportation): attendance, agenda items with COFOG 1999 topics, official decisions as verbatim quotes, and the minutes rendered verbatim as Markdown. |
| [Transport Policies](latest/transport-policies/README.md) | The 21 transport policies, strategies and codes of practice that define the transport document corpus, with links to their curated PDFs (see the Documents dataset's `index.json` for which are published). |
| [Transport RACI](latest/transport-raci/README.md) | Who is Responsible, Accountable, Consulted and Informed for local transport activities and lifecycle stages, analysed for Meath County Council. Includes the [transport stage](vocabularies/transport-stage.md), [transport activity](vocabularies/transport-activity.md), [party](vocabularies/transport-raci-party.md) and [evidence level](vocabularies/raci-evidence-level.md) vocabularies. |
| [Active Travel Allocations](latest/active-travel-allocations/README.md) | Every project the National Transport Authority allocated Active Travel Investment Grant money to between 2022 and 2026: the recipient, the project's code and name, and the amount in euro. |
| [Documents](documents/index.json) | Markdown bundles for the curated policy PDFs that convert fully; documents that do not (coverage gaps) are listed under `failed` in `index.json`. Each document is linked to its policy by `policy_id` and `policy_role`. |

## Guides

- [Get the Data](GET_THE_DATA.md) — spreadsheet-ready downloads, no technical background needed.
- [Developer Quickstart](QUICKSTART.md) — a runnable code example to fetch and use the data programmatically.
- [Data Quality](DATA_QUALITY.md) — how extraction quality is tracked, and how to report or fix an issue.

## Raw pipeline outputs

Machine-readable dumps of the pipeline's working state, for debugging and
provenance rather than everyday use:

- [pipeline-data.json](pipeline-data.json) — per-body processing status.
- [foi-disclosures.json](foi-disclosures.json) — disclosure records (built from the per-body files under `latest/foi-disclosures/bodies/`, not committed; see the [dataset README](latest/foi-disclosures/README.md)).
- [disclosure-files.json](disclosure-files.json) — source documents discovered and processed.
- [topics.json](topics.json) — generated disclosure topics.

## Technical reference

- [catalog/](catalog/) — DCAT dataset descriptions.
- [schemas/](schemas/) — JSON schemas for the datasets.
- [vocabularies/](vocabularies/) — controlled vocabularies and term URIs:
  - [COFOG 1999](vocabularies/cofog-1999.md) — the UN's Classification of the Functions of Government (1999 edition), used for SPC agenda-item topics. Published as JSON, CSV and SKOS Turtle, with terms resolvable under `https://data.publicinformation.ie/ns/cofog#<code>`.
- [CHANGELOG.md](CHANGELOG.md) — release history.
- [LICENSE](LICENSE) — licence terms.

## `latest/` vs versioned snapshots

`latest/<dataset>/` always points at the newest release — use it for a stable
URL that never breaks. A versioned path like `v2.0.0/public-bodies/` is a
pinned reference — use it when you need to guarantee you're always reading
exactly the same bytes, regardless of future releases.
