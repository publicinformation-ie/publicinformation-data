# data.gov.ie Links Dataset

**Dataset URI:** `https://data.publicinformation.ie/dataset/data-gov-ie-links`

Links from Irish public bodies to their organisation page on [data.gov.ie](https://data.gov.ie/), Ireland's open data portal. Each link is joined to exactly one public body via the [Public Bodies dataset](../public-bodies/README.md). Part of the PublicInformation.ie Open Data Publishing initiative.

**Base URI:** `https://data.publicinformation.ie/`

## Versioning

This directory (`v1.0.0/`) is an immutable, versioned release. `../../latest/data-gov-ie-links/` always mirrors the newest version. Releases are also tagged in git (`data-gov-ie-links-v1.0.0`). This dataset versions independently of the Public Bodies dataset. Unlike Who Does What's hand-refreshed HTML snapshot, data.gov.ie exposes a live CKAN API — this dataset is refreshed by re-running `pipelines/datagovie_pipeline` against that live API, not by re-saving a source file.

## Data Model

Each data.gov.ie link record contains:

| Property | Type | Description | Required |
|----------|------|--------------|----------|
| `@id` | URI | Persistent Cool URI for the link record, under `/data-gov-ie-links/` (not the public body's own `@id` — this is an annotation record) | Yes |
| `@type` | String | Entity type (`dgi:DataGovIeLink`) | Yes |
| `public_body` | URI | The `@id` of the public body this link belongs to, from the [Public Bodies dataset](../public-bodies/public-bodies.jsonld) | Yes |
| `datagovie_slug` | String | CKAN's own URL slug for the organisation (the path segment in `datagovie_url`) | Yes |
| `datagovie_url` | URI | Link to the organisation's page on data.gov.ie | Yes |
| `datagovie_package_count` | Integer | Number of datasets the organisation has published on data.gov.ie, as of the pipeline run that produced this record | Yes |

## Files

- **[data-gov-ie-links.jsonld](data-gov-ie-links.jsonld)** — JSON-LD, single `@context` + `@graph` of all records
- **[data-gov-ie-links.csv](data-gov-ie-links.csv)** — CSV, one row per link
- **[data-gov-ie-links.csv-metadata.json](data-gov-ie-links.csv-metadata.json)** — CSV on the Web (CSVW) metadata for the CSV file
- **[../../schemas/data-gov-ie-links.schema.json](../../schemas/data-gov-ie-links.schema.json)** — JSON Schema
- **[../../catalog/dataset-data-gov-ie-links.ttl](../../catalog/dataset-data-gov-ie-links.ttl)** — DCAT-AP 3.0 dataset metadata (RDF/Turtle), related to the Public Bodies dataset via `dct:relation`

## Relationship to Public Bodies

Every record's `public_body` field is the exact same URI published as `@id` in the [Public Bodies dataset](../public-bodies/public-bodies.jsonld). To join the two datasets, match `data-gov-ie-links[].public_body` against `public-bodies[].@id`.

## Provenance

Source: data.gov.ie's CKAN REST API (`https://data.gov.ie/api/3/action/organization_list?all_fields=true`), called live on every pipeline run (fetched for this release on 2026-07-11) — unlike Who Does What's static HTML snapshot, this is a stable, documented JSON API with a single cheap GET for the whole organisation list, so no separate fetch-and-commit step is needed. Each fetched organisation is resolved to a `public_body_id` by fuzzy name matching against the Public Bodies dataset (`SequenceMatcher` ratio, threshold 0.90, via the shared `src/lib/body_matching.py` helper also used by Who Does What), with any manual corrections recorded in the pipeline's `override.json`.

## Usage

### JSON-LD Example

```json
{
  "@id": "https://data.publicinformation.ie/data-gov-ie-links/an-garda-siochana",
  "@type": "dgi:DataGovIeLink",
  "public_body": "https://data.publicinformation.ie/body/an-garda-siochana",
  "datagovie_slug": "an-garda-siochana",
  "datagovie_url": "https://data.gov.ie/organization/an-garda-siochana",
  "datagovie_package_count": 0
}
```

### Accessing Data

```bash
curl -L https://data.publicinformation.ie/latest/data-gov-ie-links/data-gov-ie-links.jsonld
curl -L https://data.publicinformation.ie/latest/data-gov-ie-links/data-gov-ie-links.csv
```

## Known Limitations

- **Only organisations matching a canonical public body by name are included.** data.gov.ie lists around 175 organisations as open-data publishers, but most are not public bodies at all — university research centres, community groups, and other non-government publishers appear alongside government departments and agencies. This dataset intentionally excludes the majority as non-matches; that majority is the expected, normal outcome of this dataset's design, not a data-quality gap to chase down.
- **Link and dataset count only, not dataset content.** This dataset records the link to each body's data.gov.ie organisation page and how many datasets it has published there, not the titles, descriptions, or content of those datasets. Publishing that richer metadata is noted as possible future work.
- **`datagovie_package_count` is a point-in-time snapshot.** It reflects the count as of the pipeline run that produced the current release, not a live count.

## Conformance

| Standard | Level | Notes |
|----------|-------|-------|
| 5-Star Linked Data | ★★★★ | JSON-LD with dereferenceable URIs; no SPARQL endpoint |
| DCAT-AP 3.0 | Full | Complete dataset metadata, related to Public Bodies via `dct:relation` |
| JSON Schema | Full | All properties defined and required |

## License

Creative Commons Attribution 4.0 International (CC-BY 4.0). See [LICENSE](../../LICENSE).

## Contact

**Publisher:** [PublicInformation.ie](https://www.publicinformation.ie/)
**Email:** dave@publicinformation.ie
**Repository:** https://github.com/publicinformation-ie/publicinformation-data
