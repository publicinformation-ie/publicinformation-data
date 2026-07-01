# Public Bodies Dataset

A comprehensive list of all public bodies in Ireland, including their Freedom of Information (FOI) status and contact information.

## Overview

This dataset contains **229 public bodies** that are subject to FOI legislation in Ireland. It is published as both JSON-LD and CSV formats, following W3C Data on the Web Best Practices.

**Base URI:** `https://codeberg.org/publicinformation-ie/publicinformation-data/`

## Dataset Information

| Property | Value |
|----------|-------|
| **Title** | Public Bodies in Ireland |
| **Description** | Comprehensive list of Irish public bodies with FOI status and scope |
| **License** | [CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| **Publisher** | [PublicInformation.ie](https://www.publicinformation.ie/) |
| **Contact** | dave@publicinformation.ie |
| **Issued** | 2026-07-01 |
| **Update Frequency** | Daily |
| **Format** | JSON-LD, CSV |
| **Records** | 229 |

## Files

| File | Format | Description |
|------|--------|-------------|
| [`public-bodies.jsonld`](public-bodies.jsonld) | JSON-LD | Primary format with full Linked Data context |
| [`public-bodies.csv`](public-bodies.csv) | CSV | Tabular format with proper escaping |
| [`public-bodies.schema.json`](public-bodies.schema.json) | JSON Schema | Machine-readable schema definition |
| [`dataset-public-bodies.ttl`](dataset-public-bodies.ttl) | RDF/Turtle | DCAT-AP dataset metadata |
| `vocabularies/` | CSV | Controlled vocabularies |

## Data Model

### Entity: Public Body

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| `@id` | URI | Persistent identifier | Yes |
| `@type` | String | Entity type (`foi:PublicBody`) | Yes |
| `name` | String | Official name | Yes |
| `short_name` | String | Short name/acronym | No |
| `description` | String | Description | No |
| `type` | String (URI) | Body type (from vocabulary) | Yes |
| `website` | URI | Official website | No |
| `foi_subject` | Boolean | Subject to FOI legislation | Yes |
| `foi_scope` | URI | FOI scope (from vocabulary) | Yes |
| `sector` | String | Government sector | No |
| `parent_body` | URI | Parent body URI | No |
| `governing_legislation` | URI[] | Legislation URIs | No |
| `geographic_coverage` | String | ISO 3166-2 code | Yes |
| `contact_email` | String | FOI contact email | No |
| `contact_phone` | String | FOI contact phone | No |

## Vocabularies

| Vocabulary | File | Values |
|------------|------|--------|
| Body Type | [`body-type.csv`](vocabularies/body-type.csv) | department, agency, local_authority, public_body, other |
| FOI Scope | [`foi-scope.csv`](vocabularies/foi-scope.csv) | full, none, partial, partial-exclusion, commercial, security |
| Sector | [`sector.csv`](vocabularies/sector.csv) | government, health, education, justice, environment, transport, local_government, other |
| Geographic Coverage | [`geographic-coverage.csv`](vocabularies/geographic-coverage.csv) | IE |

## Provenance

This dataset is derived from:
1. **Primary Source:** [CSO.ie Public Sector Bodies Register](https://www.cso.ie/en/media/csoie/releasespublications/documents/ep/registerofpublicsectorbodies/2025h1/PRPBI2025H1TBL1.1csv.csv)
2. **Intermediate:** [`pipeline-data.json`](pipeline-data.json) from PublicInformation.ie pipeline
3. **Transformation:** This Slice 1 transformation to Linked Data format

## Usage

### JSON-LD Example

```json
{
  "@id": "https://codeberg.org/publicinformation-ie/publicinformation-data/body/an-coimisium-pleanala",
  "@type": "foi:PublicBody",
  "name": "An Coimisiun Pleanalala",
  "type": "public_body",
  "website": "https://www.pleanala.ie/",
  "foi_subject": true,
  "foi_scope": "https://codeberg.org/publicinformation-ie/publicinformation-data/ns/foi#FullScope",
  "geographic_coverage": "IE",
  "contact_email": "foi@pleanala.ie"
}
```

### Accessing Data

```bash
curl -L https://codeberg.org/publicinformation-ie/publicinformation-data/public/public-bodies.jsonld
curl -L https://codeberg.org/publicinformation-ie/publicinformation-data/public/public-bodies.csv
```

## Conformance

| Standard | Level | Notes |
|----------|-------|-------|
| **5-Star Linked Data** | ★★★★ | JSON-LD with URIs, no SPARQL endpoint yet |
| **DCAT-AP 3.0** | Full | Complete dataset metadata |
| **JSON Schema** | Full | All properties defined |
| **FAIR Principles** | High | Findable, Accessible, Interoperable, Reusable |

## Versioning

This dataset uses semantic versioning via Git tags.

## License

This dataset is licensed under **Creative Commons Attribution 4.0 International (CC-BY 4.0)**.

## Feedback

Issues and contributions are welcome via the [Codeberg repository](https://codeberg.org/publicinformation-ie/publicinformation-data).

## References

- [W3C Data on the Web Best Practices](https://www.w3.org/TR/dwbp/)
- [DCAT-AP 3.0](https://data.europa.eu/m8g)
- [JSON-LD 1.1](https://www.w3.org/TR/json-ld11/)
- [PROV-O](https://www.w3.org/TR/prov-o/)
- [FAIR Principles](https://www.go-fair.org/fair-principles/)
