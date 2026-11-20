# Public Service Staff Numbers Dataset

**Dataset URI:** `https://data.publicinformation.ie/dataset/staff-numbers`

Full-time-equivalent (FTE) staff numbers for Irish public bodies, taken from the Department of Public Expenditure, Infrastructure, Public Service Reform and Digitalisation's public service numbers file and linked to the [Public Bodies dataset](../public-bodies/README.md). Part of the PublicInformation.ie Open Data Publishing initiative.

**Base URI:** `https://data.publicinformation.ie/`

## Versioning

This directory (`v1.0.0/`) is an immutable, versioned release. `../../latest/staff-numbers/` always mirrors the newest version. This release covers a single reporting quarter, **2025 Q4**; the source file also holds quarterly figures back to 2008, which are not published here. The dataset is refreshed by re-running `pipelines/staffnumbers_pipeline` against the live source file.

## Data Model

Each record is one row of the source file for the reporting quarter:

| Property | Type | Description | Required |
|----------|------|-------------|----------|
| `@id` | URI | Persistent URI for the record, under `/staff-numbers/<year>-q<quarter>/` plus a slug of `source_key` | Yes |
| `@type` | String | `sn:StaffNumbersRecord` | Yes |
| `public_body` | URI or null | The `@id` of the public body this row belongs to, from the [Public Bodies dataset](../public-bodies/public-bodies.jsonld). `null` when `match_status` is `unmatched` | Yes |
| `match_status` | String | How the row was tied to a public body: `exact`, `rule`, `override` or `unmatched` (see below) | Yes |
| `year` | Integer | Calendar year of the reporting quarter | Yes |
| `quarter` | Integer | Calendar quarter, 1-4 | Yes |
| `source_name` | String | The body name as written in the source | Yes |
| `source_department` | String | The source's department grouping (`Level_2`) | Yes |
| `source_category` | String | The source's category (`Level_4`), e.g. Civil Service, Local Authorities | Yes |
| `source_key` | String | Stable identity of the source row: its non-empty `Level_4`, `Level_5` and `Level_6` joined by ` \| ` | Yes |
| `fte` | Number or null | Full-time-equivalent staff in the row | Yes |

## How rows are matched to public bodies

The source names bodies at an inconsistent depth: agencies carry the name in its sixth column (`Level_6`), while civil service offices, local authorities and the education and health aggregates leave that blank and carry it in the fifth (`Level_5`). `source_name` is `Level_6` when present, otherwise `Level_5`. The names also differ from the canonical ones (`Crawford Gallery` vs `Crawford Art Gallery`; local authorities are written `County Council - Leitrim`).

| `match_status` | Meaning |
|---|---|
| `exact` | The source name and a canonical name are identical after normalising case, accents, `&`/`and`, "the", punctuation and parentheticals |
| `rule` | A local authority label (`County Council - Leitrim`) was rewritten to its canonical form (`Leitrim County Council`) and then matched exactly |
| `override` | A person reviewed the row and recorded the body, in `pipelines/staffnumbers_pipeline/steps/apply_overrides/override.json` |
| `unmatched` | No single canonical body: an aggregate (e.g. Second Level Education), a sub-unit of a body, or a row nobody has reviewed yet |

There is deliberately no fuzzy-match threshold. Near-misses are decided by a person.

## Files

- **[staff-numbers.jsonld](staff-numbers.jsonld)** — JSON-LD, single `@context` + `@graph` of all records
- **[staff-numbers.csv](staff-numbers.csv)** — CSV, one row per record
- **[staff-numbers.csv-metadata.json](staff-numbers.csv-metadata.json)** — CSV on the Web (CSVW) metadata
- **[../../schemas/staff-numbers.schema.json](../../schemas/staff-numbers.schema.json)** — JSON Schema
- **[../../catalog/dataset-staff-numbers.ttl](../../catalog/dataset-staff-numbers.ttl)** — DCAT-AP 3.0 dataset metadata (RDF/Turtle)

## Provenance

Source: [Open Data PS Numbers Source.csv](https://databank.per.gov.ie/OpenData/Open%20Data%20PS%20Numbers%20Source.csv), published by the Department of Public Expenditure, Infrastructure, Public Service Reform and Digitalisation (PER) Databank. Only the most recent quarter in the file is published. The pipeline records the SHA-256 of the source file it read in its step metadata.

This release: 220 rows for 2025 Q4, of which 173 are linked to 172 distinct public bodies (96 `exact`, 29 `rule`, 48 `override`) and 47 are `unmatched`. The published `fte` values sum to exactly the source file's total for the quarter (417,463.5).

## Known Limitations

- **FTE is not headcount.** It is full-time-equivalent staff, and may be fractional.
- **Only 44% of FTE is linked to a public body.** The largest source rows are aggregates with no single body: First Level Education (62,385 FTE), Second Level Education (43,001 and 6,724), Voluntary Hospitals (34,962), Universities and other third-level core posts, and the Defence and Garda rows. They are kept as `unmatched` rows so that totals reconcile, rather than being dropped or guessed at.
- **A body can have several rows.** For example the Commission for Regulation of Utilities has a main row and a Water Sector row. Sum `fte` per `public_body` for a body total, but note that a body's other staff (such as a department's Garda or Defence Forces personnel) may sit in separate rows that are not linked to it.
- **Department rows are the civil service staff of that department only.** Defence Forces and Garda personnel, prisons and similar are reported as separate rows.
- **Some unmatched rows are awaiting review**, not confirmed to have no body. The pipeline's `errors.json` lists them.
- **Source licence not verified.** The licence of the underlying PER file has not been confirmed by this project. Check the PER Databank's terms before reusing the figures.
- **Single quarter.** No time series is published in this release.

## Relationship to Public Bodies

Every non-null `public_body` is exactly the `@id` published in the [Public Bodies dataset](../public-bodies/public-bodies.jsonld). To join the two datasets, match `staff-numbers[].public_body` against `public-bodies[].@id`.

## Conformance

| Standard | Level | Notes |
|----------|-------|-------|
| 5-Star Linked Data | ★★★★ | JSON-LD with dereferenceable URIs; no SPARQL endpoint |
| DCAT-AP 3.0 | Full | Complete dataset metadata |
| JSON Schema | Full | All properties defined and required |

## License

Creative Commons Attribution 4.0 International (CC-BY 4.0) for the matching and structure added by this project. See the source-licence note above. See [LICENSE](../../LICENSE).

## Contact

**Publisher:** [PublicInformation.ie](https://www.publicinformation.ie/)
**Email:** dave@publicinformation.ie
**Repository:** https://github.com/publicinformation-ie/publicinformation-data
