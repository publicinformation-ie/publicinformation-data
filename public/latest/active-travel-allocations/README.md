# Active Travel Investment Grant Allocations

**Dataset URI:** `https://data.publicinformation.ie/dataset/active-travel-allocations`

Project-level allocations from the National Transport Authority's annual Active Travel Investment Grant programme, 2022 to 2026. Each record is one project's allocation in one funding stream in one authority's table, read from the published PDF. Part of the PublicInformation.ie Open Data Publishing initiative.

**Base URI:** `https://data.publicinformation.ie/`

## Versioning

This directory (`v1.0.0/`) is an immutable, versioned release. `../../latest/active-travel-allocations/` always mirrors the newest version. This dataset versions independently of the Public Bodies dataset. `dct:modified` in the catalogue metadata is updated automatically only when the published payload content actually changes; `owl:versionInfo` is bumped by hand only for breaking or additive schema changes.

A reissued PDF replaces the figures on the next run: this dataset carries no revision history.

## Data Model

Each record is one project allocation row: a project listed under one recipient in one funding stream in one annual document.

| Property | Type | Description | Required |
|----------|------|--------------|----------|
| `@id` | URI | Persistent URI, `https://data.publicinformation.ie/allocation/{recipient}/{year}/{stream}/{key}` | Yes |
| `@type` | String | Entity type (`Allocation`) | Yes |
| `year` | Integer | Allocation year, from the committed publication list | Yes |
| `public_body` | URI | The `@id` of the recipient local authority in the [Public Bodies dataset](../public-bodies/public-bodies.jsonld); absent for a non-local-authority recipient | No |
| `public_body_id` | Integer | The body's internal `public_body_id`, retained as a join key; absent for a non-local-authority recipient | No |
| `recipient_name` | String | Recipient as printed in the source document | Yes |
| `funding_stream` | String | `active_travel` or `other_nta_streams` | Yes |
| `project_code` | String | Project code as printed, which may be a provisional placeholder (`WCC/26/XXXX`) | Yes |
| `project_code_provisional` | Boolean | True when the printed code is a placeholder and therefore does not identify the project | Yes |
| `project_name` | String | Project name as printed | Yes |
| `allocation_eur` | Integer | Allocation in whole euro | Yes |
| `source_document_url` | URI | URL of the source allocation document | Yes |
| `source_document_sha256` | String | SHA-256 of the source document bytes this record was read from | Yes |
| `source_page` | Integer | 1-based page the record was read from | Yes |

## Files

- **[active-travel-allocations.jsonld](active-travel-allocations.jsonld)** — JSON-LD, single `@context` + `@graph` of all records
- **[active-travel-allocations.csv](active-travel-allocations.csv)** — CSV, one row per allocation
- **[active-travel-allocations.csv-metadata.json](active-travel-allocations.csv-metadata.json)** — CSV on the Web (CSVW) metadata for the CSV file
- **[../../schemas/active-travel-allocations.schema.json](../../schemas/active-travel-allocations.schema.json)** — JSON Schema
- **[../../catalog/dataset-active-travel-allocations.ttl](../../catalog/dataset-active-travel-allocations.ttl)** — DCAT-AP 3.0 dataset metadata (RDF/Turtle), related to the Public Bodies dataset via `dct:relation`

## Funding streams

`funding_stream` is a closed two-term vocabulary, mirrored by the JSON Schema enum:

| Term | Meaning |
|------|---------|
| `active_travel` | The recipient's Active Travel Investment Grant allocation. In a local authority's table this is the first block of rows; in the non-local-authority table (`Campuses, Hospitals, Educational Institutions and Others`) it is the whole table, which the document itself frames as active travel investment. |
| `other_nta_streams` | An allocation through the separate blocks that later editions head *Allocations Through Other NTA Funding Streams* (bus priority, bus-stop enhancement and similar works funded outside the active travel grant). |

The stream is decided by the document's money anchors, not by page position: each block ends in a printed subtotal or total, and the block order decides the stream. A block that opens without its divider heading is still assigned correctly because its closing anchors bracket it.

## Identity

`@id` is `https://data.publicinformation.ie/allocation/{recipient}/{year}/{stream}/{key}`:

- `recipient` is the recipient's permanent slug (the local authority's public-bodies slug, or the slugified printed name for the non-local-authority block).
- `key` is the lowercased project code, punctuation collapsed to `-` (`CW/21/0001` → `cw-21-0001`) when the document prints a real code.
- When the code is a placeholder, `key` is the slugified project name instead: a provisional code is explicitly "to be assigned" and repeats within a section, so it never identifies a record.
- Keys that repeat within one recipient, year and stream are suffixed `-2`, `-3` in document order. Document order is deterministic, so identity is stable across re-runs of unchanged documents.

Only real project codes should be used to follow a project across years; provisional codes must not be.

## Relationship to Public Bodies

For a local-authority recipient, `public_body` is the exact same URI published as `@id` in the [Public Bodies dataset](../public-bodies/public-bodies.jsonld), resolved through the same permanent slug machinery (seeded in `slug_seed.json`). A local authority that does not resolve to a known body fails publication rather than being guessed or dropped. The non-local-authority block (`Campuses, Hospitals, Educational Institutions and Others`) is published by its printed name with no `public_body`, because those recipients are not public bodies in that dataset.

To join, match `active-travel-allocations[].public_body` against `public-bodies[].@id`, or use the retained `public_body_id`.

## Provenance and completeness

Source: the `activetravel_pipeline` (`pipelines/activetravel_pipeline/`), which fetches the committed publication list, extracts the three-column tables, classifies every row, reads every printed amount as whole euro, attributes each row to a recipient and funding stream, and reconciles the result against the document's own arithmetic before `scripts/transform_active_travel_allocations.py` publishes it.

**Anything published is complete for its recipient, year and stream, and adds up.** A recipient's stream is published only when its rows equal the total the document declares for it — a section total, a block subtotal, and (for 2025 and 2026) the per-recipient summary in the document's front matter. A stream that does not reconcile is withheld entirely and appears in the pipeline's run errors, naming the recipient, the stream, both sums and the difference. One euro is a difference.

So the dataset is smaller than the PDFs in places, on purpose:

| Year | Records | Allocations (€) | Withheld |
|------|---------|-----------------|----------|
| 2022 | 990 | 365,165,751 | South Dublin (a project row printed with no name), Wexford (rows one euro over the declared total) |
| 2023 | 1,156 | 332,221,899 | — |
| 2024 | 833 | 321,625,311 | Fingal (two rows with no printed amount, one printed `€ -`), the non-local-authority block (one euro over) |
| 2025 | 913 | 337,188,134 | Kerry, Longford and Wexford other-NTA-streams blocks (the document declares money for rows it does not print) |
| 2026 | 983 | 305,174,826 | Dublin City, Cork County, Wicklow other-NTA-streams blocks (same); Waterford active travel (one euro under) |

Project rows printed with `N/A*` (2025) are not published: the document states the scheme will be designed under a different project code and prints no allocation. Amounts are published as whole euro; a printed figure with non-zero cents would not be.

## Usage

### JSON-LD Example

```json
{
  "@id": "https://data.publicinformation.ie/allocation/wicklow-county-council/2026/active_travel/wcc-25-0003",
  "@type": "Allocation",
  "year": 2026,
  "public_body": "https://data.publicinformation.ie/body/wicklow-county-council",
  "public_body_id": 1876,
  "recipient_name": "Wicklow County Council",
  "funding_stream": "active_travel",
  "project_code": "WCC/25/0003",
  "project_code_provisional": false,
  "project_name": "Vale Road Pedestrian Improvement Scheme, Arklow",
  "allocation_eur": 350000,
  "source_document_url": "https://www.nationaltransport.ie/wp-content/uploads/2026/01/Active-Travel-Investment-Grants-2026-Allocations.pdf",
  "source_document_sha256": "…",
  "source_page": 22
}
```

### Accessing Data

```bash
curl -L https://data.publicinformation.ie/latest/active-travel-allocations/active-travel-allocations.jsonld
curl -L https://data.publicinformation.ie/latest/active-travel-allocations/active-travel-allocations.csv
```

## Known Limitations

- **One row per project per year, not one project.** The same project appears once for each year it was allocated funding; only a real project code joins the records across years.
- **Provisional codes do not identify projects.** Roughly 1,369 records carry a placeholder code. They are real allocations, but the code cannot be used as a project key, and their identity is derived from the printed project name.
- **Withheld streams are absent, not zero.** Where a stream failed reconciliation it does not appear at all; check the pipeline's run errors for the figures involved.
- **The 2022 Annex 1 is not used as a check.** It is a programme budget view (€289.0m across A3.1–A3.4 by GDA/regional/rural split) with no per-recipient counterpart in the project tables, so it is not comparable with them and is not published here.
- **No sub-euro precision.** Allocations are published as whole euro, as printed.
- **No revision history.** A reissued PDF replaces the figures on the next run; `source_document_sha256` identifies which issue a record came from.

## Conformance

| Standard | Level | Notes |
|----------|-------|-------|
| 5-Star Linked Data | ★★★★ | JSON-LD with dereferenceable URIs; no SPARQL endpoint |
| DCAT-AP 3.0 | Full | Complete dataset metadata, related to Public Bodies via `dct:relation` |
| JSON Schema | Full | All properties defined; core fields required; `funding_stream` and `@type` enumerated |

## License

Creative Commons Attribution 4.0 International (CC-BY 4.0). See [LICENSE](../../LICENSE).

## Contact

**Publisher:** [PublicInformation.ie](https://www.publicinformation.ie/)
**Email:** dave@publicinformation.ie
**Repository:** https://github.com/publicinformation-ie/publicinformation-data
