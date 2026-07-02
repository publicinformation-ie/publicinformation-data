# Public Bodies Dataset (Slice 1)

**Dataset URI:** `https://publicinformation-ie.codeberg.page/publicinformation-data/dataset/public-bodies`

A list of all 883 public sector bodies in Ireland known to PublicInformation.ie, with their Freedom of Information (FOI) status. Part of the PublicInformation.ie Open Data Publishing initiative.

**Base URI:** `https://publicinformation-ie.codeberg.page/publicinformation-data/`

## Versioning

This directory (`v1.0.0/`) is an immutable, versioned release. `../../latest/public-bodies/` always mirrors the newest version and is what most consumers should link to; use a versioned path like this one when you need a stable, unchanging reference. Releases are also tagged in git (`public-bodies-v1.0.0`) for source-repo provenance — the versioned directory is what provides a stable **download URL**, since Codeberg Pages serves the tip of a branch, not arbitrary git tags.

## Data Model

Each public body record contains:

| Property | Type | Description | Required |
|----------|------|--------------|----------|
| `@id` | URI | Persistent Cool URI for the public body | Yes |
| `@type` | String | Entity type (`foi:PublicBody`) | Yes |
| `name` | String | Official name of the public body | Yes |
| `type` | String | Type of public body, from the [body-type vocabulary](#vocabularies) | Yes |
| `website` | URI | Official website URL | No — present for 385 of 883 bodies |
| `foi_subject` | Boolean | Whether the body is subject to FOI legislation | Yes |
| `foi_scope` | URI | FOI scope, from the [foi-scope vocabulary](#vocabularies) | Yes |
| `contact_email` | String | FOI contact email, only present where successfully crawled | No |

Fields intentionally **not** published in this Slice: `short_name`, `description`, `sector`, `geographic_coverage`, `parent_body`, `governing_legislation`, `contact_phone` — none of these have data backing them in the current pipeline. See "Known Limitations" below.

## Files

- **[public-bodies.jsonld](public-bodies.jsonld)** — JSON-LD, single `@context` + `@graph` of all 883 records
- **[public-bodies.csv](public-bodies.csv)** — CSV, one row per body
- **[public-bodies.csv-metadata.json](public-bodies.csv-metadata.json)** — CSV on the Web (CSVW) metadata for the CSV file
- **[../../schemas/public-bodies.schema.json](../../schemas/public-bodies.schema.json)** — JSON Schema, with `enum` constraints matching the vocabularies below
- **[../../catalog/dataset-public-bodies.ttl](../../catalog/dataset-public-bodies.ttl)** — DCAT-AP 3.0 dataset metadata (RDF/Turtle)

## Vocabularies

### body-type ([CSV](../../vocabularies/body-type.csv))

| notation | name |
|---|---|
| `department` | Government Department |
| `local_authority` | Local Authority |
| `public_body` | Public Body |

### foi-scope ([CSV](../../vocabularies/foi-scope.csv))

| notation | name |
|---|---|
| `FullScope` | Full FOI Applicability |
| `NoScope` | No FOI Applicability |

## Provenance

1. **Immediate source:** [gov.ie Departments listing](https://www.gov.ie/en/departments/), scraped by the `find_public_bodies` pipeline step.
2. **FOI-subject determination:** a curated 229-body allowlist (`find_public_bodies_subject_to_foi`), not a crawler heuristic.
3. **Contact emails:** crawled from each body's published FOI page where that crawl succeeded (229 of 883 bodies were crawled; not all crawls succeed).

Ireland's [CSO.ie Register of Public Sector Bodies](https://www.cso.ie/) is understood to be a more authoritative source for this list, and a separate internal pipeline (`cso_pipeline`) already ingests it — including fields like `sector` and parent/child relationships not yet retained here. Reconciling `find_public_bodies` against `cso_pipeline`'s output is tracked as future work, not part of this release.

## Usage

### JSON-LD Example

```json
{
  "@id": "https://publicinformation-ie.codeberg.page/publicinformation-data/body/an-coimisiun-pleanala",
  "@type": "foi:PublicBody",
  "name": "An Coimisiún Pleanála",
  "type": "public_body",
  "website": "https://www.pleanala.ie/",
  "foi_subject": true,
  "foi_scope": "https://publicinformation-ie.codeberg.page/publicinformation-data/ns/foi#FullScope",
  "contact_email": "foi@pleanala.ie"
}
```

### Accessing Data

```bash
curl -L https://publicinformation-ie.codeberg.page/publicinformation-data/latest/public-bodies/public-bodies.jsonld
curl -L https://publicinformation-ie.codeberg.page/publicinformation-data/latest/public-bodies/public-bodies.csv
```

## Known Limitations

- `sector` and parent/child body relationships exist in `cso_pipeline`'s output but aren't yet retained by `find_public_bodies` — future work.
- `foi_scope` is currently binary (`FullScope`/`NoScope`); finer-grained scopes (partial applicability, commercial/security exclusions) require a data source that doesn't exist yet.
- One known upstream data quality issue: a corrupted FOI email address for one body, tracked separately as a `get_foi_emails` pipeline bug.

## Conformance

| Standard | Level | Notes |
|----------|-------|-------|
| 5-Star Linked Data | ★★★★ | JSON-LD with dereferenceable URIs; no SPARQL endpoint |
| DCAT-AP 3.0 | Full | Complete dataset metadata |
| JSON Schema | Full | All properties defined, vocabulary-backed `enum` constraints |

## License

Creative Commons Attribution 4.0 International (CC-BY 4.0). See [LICENSE](../../LICENSE).

## Contact

**Publisher:** [PublicInformation.ie](https://www.publicinformation.ie/)
**Email:** dave@publicinformation.ie
**Repository:** https://codeberg.org/publicinformation-ie/publicinformation-data
