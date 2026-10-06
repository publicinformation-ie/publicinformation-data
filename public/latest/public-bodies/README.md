# Public Bodies Dataset (Slice 1)

**Dataset URI:** `https://data.publicinformation.ie/dataset/public-bodies`

A list of all 883 public sector bodies in Ireland known to PublicInformation.ie, with their Freedom of Information (FOI) status, CSO sector/NACE classification, and parent/department relationships. Part of the PublicInformation.ie Open Data Publishing initiative.

**Base URI:** `https://data.publicinformation.ie/`

## Versioning

This directory (`v2.0.0/`) is an immutable, versioned release. `../../latest/public-bodies/` always mirrors the newest version and is what most consumers should link to; use a versioned path like this one when you need a stable, unchanging reference. Releases are also tagged in git (`public-bodies-v2.0.0`) for source-repo provenance — the versioned directory is what provides a stable **download URL**, since static hosts serve the tip of a branch, not arbitrary git tags.

### Previous Versions

| Version | Tag | Notes |
|---|---|---|
| [v1.0.0](../../v1.0.0/public-bodies/) | `public-bodies-v1.0.0` | Original 7-field release: `@id`, `name`, `type`, `website`, `foi_subject`, `foi_scope`, `contact_email`. `@id` was derived from a fresh `slugify(name)` call each run (not permanent). |
| v2.0.0 (this version) | `public-bodies-v2.0.0` | Widened with CSO sector/NACE/parent-department data and crawl-status detail (see Data Model below). `@id` now derived from a permanent slug (see Known Limitations). |

## Data Model

Each public body record contains:

| Property | Type | Description | Required |
|----------|------|--------------|----------|
| `@id` | URI | Persistent Cool URI for the public body, built from a permanent slug | Yes |
| `@type` | String | Entity type (`foi:PublicBody`) | Yes |
| `name` | String | Official name of the public body | Yes |
| `type` | String | Type of public body, from the [body-type vocabulary](#vocabularies) | Yes |
| `website` | URI | Official website URL | No — present for 376 of 883 bodies |
| `foi_subject` | Boolean | Whether the body is subject to FOI legislation | Yes |
| `foi_scope` | URI | FOI scope, from the [foi-scope vocabulary](#vocabularies) | Yes |
| `contact_email` | String | FOI contact email, only present where successfully crawled | No |
| `slug` | String | The permanent slug component of `@id`, exposed explicitly | Yes |
| `parent_id` | URI | Reference to the parent body's record in this dataset | No — only where CSO data identifies a parent that resolves to a known body |
| `parent_name` | String | Parent body's name, from CSO data | No |
| `government_department_id` | URI | Reference to the parent government department's record in this dataset | No — only where CSO data identifies one that resolves to a known body |
| `government_department` | String | Parent government department's name, from CSO data | No |
| `sector` | String | CSO institutional sector code (e.g. `S13`) | No |
| `legal_status` | String | Legal status, from CSO Register of Public Sector Bodies | No |
| `nace_code` | String | Full NACE economic activity classification code | No |
| `nace_section` | String | NACE section letter | No |
| `nace_section_name` | String | NACE section name | No |
| `nace_division` | String | NACE division code | No |
| `nace_group` | String | NACE group code | No |
| `nace_class` | String | NACE class code | No |
| `nace_class_name` | String | NACE class name | No |
| `cro` | String | Companies Registration Office number, where applicable | No |
| `data_vintage` | Integer | Year the CSO source data was last refreshed for this body | No |
| `is_commercial` | Boolean | Whether classified as commercial by the CSO | No |
| `is_financial` | Boolean | Whether classified as a financial institution by the CSO | No |
| `aegis` | String | Which government entity the body operates under the aegis of | No |
| `legal_entity_type` | String | CSO legal entity type classification | No |
| `website_url` | Object | `{url, status, verified?}` — crawl-status detail for the website URL | No — present only for the 229 crawled bodies |
| `foi_page` | Object | `{url, status, verified?}` — crawl-status detail for the FOI information page | No — present only for crawled bodies |
| `foi_email` | Object | `{email, status, verified?}` — crawl-status detail for the FOI contact email | No — present only for crawled bodies |
| `disclosures_page` | Object | `{url, status, verified?}` — crawl-status detail for the disclosure log page | No — present only for crawled bodies |
| `disclosure_files` | Object | `{total, valid, failed, status}` — disclosure file crawl summary | No — present only for crawled bodies |
| `foi_requests` | Object | `{valid, errors, status}` — individual FOI request record crawl summary | No — present only for crawled bodies |

`verified` (inside the four crawl-status objects above) is itself optional
within those objects — present only where a human reviewer verified that
specific crawl result; its absence means "not reviewed," never "reviewed
and found false."

Fields intentionally **not** published in this Slice: `short_name`,
`description`, `geographic_coverage`, `governing_legislation`,
`contact_phone` — none of these have data backing them in the current
pipeline, including the newly-joined CSO data. (As of v2.0.0, `sector` and
parent/child body relationships **are** published — see the table above;
they were the two fields the v1.0.0 README listed as future work, now
delivered via the CSO join.)

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
3. **Contact emails and crawl-status objects:** crawled from each body's published FOI page where that crawl succeeded (229 of 883 bodies were crawled; not all crawls succeed — `disclosure_files`/`foi_requests`/etc. are present only for these 229 bodies).
4. **Sector, NACE classification, and parent/department relationships:** joined from Ireland's [CSO.ie Register of Public Sector Bodies](https://www.cso.ie/) via the `cso_pipeline`'s `resolve_website_urls` step, matched 1:1 by `public_body_id` against all 883 bodies (no orphans).

## Usage

### JSON-LD Example

```json
{
  "@id": "https://data.publicinformation.ie/body/ability-west",
  "@type": "foi:PublicBody",
  "name": "Ability West",
  "type": "public_body",
  "foi_subject": true,
  "foi_scope": "https://data.publicinformation.ie/ns/foi#FullScope",
  "slug": "ability-west",
  "website": "https://www.abilitywest.ie/",
  "sector": "S13",
  "legal_status": "Non-Commercial Agency under the aegis of Department",
  "government_department": "Department of Children, Disability and Equality",
  "nace_code": "Q8810",
  "nace_section": "Q",
  "nace_section_name": "Human health and social work activities",
  "nace_division": "88",
  "nace_group": "881",
  "nace_class": "8810",
  "nace_class_name": "Social work activities without accommodation for the elderly and disabled",
  "data_vintage": 2025,
  "is_commercial": false,
  "aegis": "Department",
  "legal_entity_type": "Agency",
  "government_department_id": "https://data.publicinformation.ie/body/department-of-children-disability-and-equality",
  "website_url": {
    "url": "https://www.abilitywest.ie/",
    "status": "success"
  },
  "foi_page": {
    "status": "failed"
  },
  "foi_email": {
    "status": "failed"
  },
  "disclosures_page": {
    "status": "failed"
  },
  "disclosure_files": {
    "total": 0,
    "valid": 0,
    "failed": 0,
    "status": "failed"
  },
  "foi_requests": {
    "valid": 0,
    "errors": 0,
    "status": "failed"
  }
}
```

### Accessing Data

```bash
curl -L https://data.publicinformation.ie/latest/public-bodies/public-bodies.jsonld
curl -L https://data.publicinformation.ie/latest/public-bodies/public-bodies.csv
```

## Known Limitations

- **`@id` changed for some bodies in this release.** v1.0.0's `@id` was
  derived from a fresh `slugify(name)` call every run; v2.0.0 uses a
  permanent slug (`resolve_slug()` + `slug_seed.json`, the same source the
  production database uses, frozen once assigned per body). Comparing all
  883 records between v1.0.0 and v2.0.0: **82 of 883 `@id`
  values changed.** Examples:

  | Name | v1.0.0 `@id` | v2.0.0 `@id` |
  |---|---|---|
  | Údarás na Gaeltachta | `.../body/údarás-na-gaeltachta` | `.../body/udaras-na-gaeltachta` |
  | Bord na Móna New Business Ltd | `.../body/bord-na-móna-new-business-ltd` | `.../body/bord-na-mona-new-business-ltd` |
  | Vhi Health & Wellbeing DAC | `.../body/vhi-health-wellbeing-dac` | `.../body/vhi-health-and-wellbeing-dac` |

  Consumers pinning to v1.0.0 `@id` values should re-fetch v2.0.0 and match
  by `name` (unchanged) or `slug` (the new explicit field) rather than
  assuming URI stability across this major version bump.
- `foi_scope` is currently binary (`FullScope`/`NoScope`); finer-grained scopes (partial applicability, commercial/security exclusions) require a data source that doesn't exist yet.
- One known upstream data quality issue: a corrupted FOI email address for one body, tracked separately as a `get_foi_emails` pipeline bug.
- `parent_id`/`government_department_id` are omitted (not published as broken URIs) for any body whose CSO-sourced reference id has no matching `public_body_id` in this dataset. As of this release, 0 such cases were found across all 883 bodies (see the transform script's own run-time warning output for future regenerations, printed by `scripts/transform_public_bodies.py`'s `main()`).
- Crawl-status objects (`website_url`, `foi_page`, `foi_email`, `disclosures_page`, `disclosure_files`, `foi_requests`) are present only for the 229 of 883 bodies that have been crawled at least once — the remaining 654 bodies have none of these six keys at all, not empty/default versions of them.

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
**Repository:** https://github.com/publicinformation-ie/publicinformation-data
