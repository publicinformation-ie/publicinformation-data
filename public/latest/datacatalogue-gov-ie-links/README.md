# datacatalogue.gov.ie Links Dataset

**Dataset URI:** `https://data.publicinformation.ie/dataset/datacatalogue-gov-ie-links`

Links from Irish public bodies to their organisation page on [datacatalogue.gov.ie](https://datacatalogue.gov.ie/), the Public Service Data Catalogue. Each link is joined to exactly one public body via the [Public Bodies dataset](../public-bodies/README.md). Part of the PublicInformation.ie Open Data Publishing initiative.

**Base URI:** `https://data.publicinformation.ie/`

## Versioning

This directory (`v1.0.0/`) is an immutable, versioned release. `../../latest/datacatalogue-gov-ie-links/` always mirrors the newest version. Releases are also tagged in git (`datacatalogue-gov-ie-links-v1.0.0`). This dataset versions independently of the Public Bodies dataset. The source is a live CKAN API, so this dataset is refreshed by re-running `pipelines/datacatalogue_pipeline`, not by re-saving a source file.

## How this catalogue differs from data.gov.ie

Both sites are CKAN portals, and many of the same bodies appear on both, but they are not the same catalogue:

| | datacatalogue.gov.ie (this dataset) | data.gov.ie ([data.gov.ie Links](../data-gov-ie-links/README.md)) |
|---|---|---|
| Purpose | A single information point where public sector bodies list the data they hold, including 'protected data' holdings under the EU Data Governance Act, and where data reusers can make a request | Ireland's open data portal: datasets published for reuse |
| What a slide in it represents | An organisation's data holdings and request routes | An organisation's published open datasets |
| Coverage here | 76 of 85 listed organisations resolve to a public body | 137 of 175 listed organisations resolve to a public body |

They are published as two datasets on purpose: the two answer different questions, and a body's presence in one says nothing about its presence in the other.

## Data Model

Each datacatalogue.gov.ie link record contains:

| Property | Type | Description | Required |
|----------|------|--------------|----------|
| `@id` | URI | Persistent Cool URI for the link record, under `/datacatalogue-gov-ie-links/` (not the public body's own `@id` — this is an annotation record) | Yes |
| `@type` | String | Entity type (`dcl:DataCatalogueLink`) | Yes |
| `public_body` | URI | The `@id` of the public body this link belongs to, from the [Public Bodies dataset](../public-bodies/public-bodies.jsonld) | Yes |
| `datacatalogue_slug` | String | CKAN's own URL slug for the organisation (the path segment in `datacatalogue_url`) | Yes |
| `datacatalogue_name` | String | The organisation's display name on datacatalogue.gov.ie | Yes |
| `datacatalogue_url` | URI | Link to the organisation's page on datacatalogue.gov.ie | Yes |
| `datacatalogue_package_count` | Integer | Number of datasets the organisation has published on datacatalogue.gov.ie, as of the pipeline run that produced this record | Only where the source provides it |
| `datacatalogue_description` | String | The organisation's self-description on datacatalogue.gov.ie | Only where the source provides it |

## Files

- **[datacatalogue-gov-ie-links.jsonld](datacatalogue-gov-ie-links.jsonld)** — JSON-LD, single `@context` + `@graph` of all records
- **[datacatalogue-gov-ie-links.csv](datacatalogue-gov-ie-links.csv)** — CSV, one row per link
- **[datacatalogue-gov-ie-links.csv-metadata.json](datacatalogue-gov-ie-links.csv-metadata.json)** — CSV on the Web (CSVW) metadata for the CSV file
- **[../../schemas/datacatalogue-gov-ie-links.schema.json](../../schemas/datacatalogue-gov-ie-links.schema.json)** — JSON Schema
- **[../../catalog/dataset-datacatalogue-gov-ie-links.ttl](../../catalog/dataset-datacatalogue-gov-ie-links.ttl)** — DCAT-AP 3.0 dataset metadata (RDF/Turtle), related to the Public Bodies dataset via `dct:relation`

The CSV header, in order: `id`, `public_body`, `datacatalogue_slug`, `datacatalogue_name`, `datacatalogue_url`, `datacatalogue_package_count`, `datacatalogue_description`. `id` carries the record's `@id`; the last two columns are empty where the source provides no value.

## Relationship to Public Bodies

Every record's `public_body` field is the exact same URI published as `@id` in the [Public Bodies dataset](../public-bodies/public-bodies.jsonld). To join the two datasets, match `datacatalogue-gov-ie-links[].public_body` against `public-bodies[].@id`.

## Provenance

Source: datacatalogue.gov.ie's CKAN REST API (`https://datacatalogue.gov.ie/api/3/action/organization_list?all_fields=true`), called live on every pipeline run (fetched for this release on 2026-11-20). The instance returns at most 25 organisations per request whatever `limit` asks for, so the fetch step pages with `offset` until an empty page comes back; an unpaged fetch silently loses most of the list. 85 organisations were listed, all active.

Each fetched organisation is resolved to a `public_body_id` by fuzzy name matching against the Public Bodies dataset (`SequenceMatcher` ratio, threshold 0.90, via the shared `src/lib/body_matching.py` helper also used by Who Does What and the other link pipelines), with manual corrections and suppressions recorded in the pipeline's `override.json`. Of the 85 organisations, 58 matched on name alone, 18 more were resolved by a reviewed override (mostly departments that have since been renamed, and bodies listed under their Irish name), and 9 were dropped as unresolved.

## Usage

### JSON-LD Example

```json
{
  "@id": "https://data.publicinformation.ie/datacatalogue-gov-ie-links/revenue-commissioners",
  "@type": "dcl:DataCatalogueLink",
  "public_body": "https://data.publicinformation.ie/body/office-of-the-revenue-commissioners",
  "datacatalogue_slug": "revenue-commissioners",
  "datacatalogue_name": "Revenue Commissioners",
  "datacatalogue_url": "https://datacatalogue.gov.ie/organization/revenue-commissioners",
  "datacatalogue_package_count": 7
}
```

### Accessing Data

```bash
curl -L https://data.publicinformation.ie/latest/datacatalogue-gov-ie-links/datacatalogue-gov-ie-links.jsonld
curl -L https://data.publicinformation.ie/latest/datacatalogue-gov-ie-links/datacatalogue-gov-ie-links.csv
```

## Known Limitations

- **Only organisations resolving to a canonical public body are included.** Some organisations listed on datacatalogue.gov.ie have no separate entry in the Public Bodies dataset — for example offices that sit inside a parent department, such as Met Éireann, the Companies Registration Office and the Geological Survey of Ireland. They are dropped rather than attached to a guessed parent, so a link's absence means "not resolvable", not "not a public body".
- **Successor bodies are not linked.** Where the catalogue lists a body that has since been absorbed into another (the Commission for Aviation Regulation into the Irish Aviation Authority, Science Foundation Ireland into Research Ireland), the record is left unlinked rather than pointed at the successor.
- **Name matching is fuzzy and date-sensitive.** The catalogue carries the name a body had when its page was created; departments renamed since (a frequent event in Ireland) do not match on name alone and rely on an override. The override file is the auditable record of those corrections.
- **`datacatalogue_package_count` is a point-in-time snapshot.** It reflects the count as of the pipeline run that produced the current release, not a live count.
- **Descriptions are the organisation's own words**, carried verbatim from the source, including its line breaks; they are not edited or verified.

## Conformance

| Standard | Level | Notes |
|----------|-------|-------|
| 5-Star Linked Data | ★★★★ | JSON-LD with dereferenceable URIs; no SPARQL endpoint |
| DCAT-AP 3.0 | Full | Complete dataset metadata, related to Public Bodies via `dct:relation` |
| JSON Schema | Full | All properties defined; optional source fields declared |

## License

Creative Commons Attribution 4.0 International (CC-BY 4.0). See [LICENSE](../../LICENSE).

## Contact

**Publisher:** [PublicInformation.ie](https://www.publicinformation.ie/)
**Email:** dave@publicinformation.ie
**Repository:** https://github.com/publicinformation-ie/publicinformation-data
