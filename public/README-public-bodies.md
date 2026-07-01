# Public Bodies Dataset (Slice 1)

**Dataset URI:** [https://codeberg.org/publicinformation-ie/publicinformation-data/dataset/public-bodies](https://codeberg.org/publicinformation-ie/publicinformation-data/dataset/public-bodies)

A comprehensive list of all public bodies in Ireland, including their Freedom of Information (FOI) status and scope. This dataset is part of the PublicInformation.ie Open Data Publishing initiative.

---

## Data Model Overview

Each public body record contains the following properties:

| Property | Type | Description | Required |
|----------|------|-------------|----------|
| `@id` | URI | Persistent Cool URI for the public body | Yes |
| `@type` | String | Entity type (`foi:PublicBody`) | Yes |
| `name` | String | Official name of the public body | Yes |
| `short_name` | String | Short name or acronym (if different from name) | No |
| `description` | String | Description of the body's function | No |
| `type` | String | Type of public body (from [body-type vocabulary](#vocabularies)) | No |
| `website` | URI | Official website URL | No |
| `foi_subject` | Boolean | Whether the body is subject to FOI legislation | Yes |
| `foi_scope` | URI | FOI scope (from [foi-scope vocabulary](#vocabularies)) | Yes |
| `sector` | String | Government sector (from [sector vocabulary](#vocabularies)) | No |
| `geographic_coverage` | String | ISO 3166-2:IE region code (from [geographic-coverage vocabulary](#vocabularies)) | No |
| `contact_email` | String | FOI contact email address | No |
| `dct:source` | URI | Source reference (foi.gov.ie) | No |

---

## File Listings

### Data Files

- **[public-bodies.jsonld](public-bodies.jsonld)** - JSON-LD formatted data with Schema.org + custom FOI vocabulary context
- **[public-bodies.csv](public-bodies.csv)** - Comma-separated values format
- **[public-bodies.csv-metadata.json](public-bodies.csv-metadata.json)** - CSV on the Web (CSVW) metadata for the CSV file

### Metadata and Schemas

- **[schemas/public-bodies.schema.json](schemas/public-bodies.schema.json)** - JSON Schema for validation
- **[catalog/dataset-public-bodies.ttl](catalog/dataset-public-bodies.ttl)** - DCAT-AP 3.0 compliant metadata (RDF/Turtle format)

### Controlled Vocabularies

All vocabularies are available in the `vocabularies/` directory with both CSV and CSVW metadata files:

- **[vocabularies/body-type.csv](vocabularies/body-type.csv)** - Types of public bodies
- **[vocabularies/foi-scope.csv](vocabularies/foi-scope.csv)** - FOI applicability scopes
- **[vocabularies/sector.csv](vocabularies/sector.csv)** - Government sectors
- **[vocabularies/geographic-coverage.csv](vocabularies/geographic-coverage.csv)** - ISO 3166-2:IE geographic regions

Each vocabulary has a corresponding `*-metadata.json` file providing CSVW metadata.

---

## Vocabulary References

### Body Type Vocabulary

| URI | Notation | Name | Description |
|-----|----------|------|-------------|
| `https://codeberg.org/publicinformation-ie/publicinformation-data/ns/body-type#department` | `department` | Government Department | A department of the Irish Government |
| `https://codeberg.org/publicinformation-ie/publicinformation-data/ns/body-type#agency` | `agency` | State Agency | A state agency or body |
| `https://codeberg.org/publicinformation-ie/publicinformation-data/ns/body-type#local_authority` | `local_authority` | Local Authority | A local government body |
| `https://codeberg.org/publicinformation-ie/publicinformation-data/ns/body-type#state_body` | `state_body` | State Body | A state-sponsored body |
| `https://codeberg.org/publicinformation-ie/publicinformation-data/ns/body-type#other` | `other` | Other | Other public body type |

### FOI Scope Vocabulary

| URI | Notation | Name | Description |
|-----|----------|------|-------------|
| `https://codeberg.org/publicinformation-ie/publicinformation-data/ns/foi#FullScope` | `FullScope` | Full FOI Applicability | Body is fully subject to FOI Act 2014 |
| `https://codeberg.org/publicinformation-ie/publicinformation-data/ns/foi#NoScope` | `NoScope` | No FOI Applicability | Body is not subject to FOI Act at all |
| `https://codeberg.org/publicinformation-ie/publicinformation-data/ns/foi#PartialScope` | `PartialScope` | Partial FOI Applicability | Body has partial FOI applicability |
| `https://codeberg.org/publicinformation-ie/publicinformation-data/ns/foi#PartialExclusion` | `PartialExclusion` | Partial Exclusion | Body is subject but with specific exclusions |
| `https://codeberg.org/publicinformation-ie/publicinformation-data/ns/foi#CommercialExclusion` | `CommercialExclusion` | Commercial Exclusion | Only commercial FOI requests excluded |
| `https://codeberg.org/publicinformation-ie/publicinformation-data/ns/foi#SecurityExclusion` | `SecurityExclusion` | Security Exclusion | Security/defence matters excluded |

### Sector Vocabulary

| URI | Notation | Name | Description |
|-----|----------|------|-------------|
| `https://codeberg.org/publicinformation-ie/publicinformation-data/ns/sector#Government` | `Government` | Government | Central and local government |
| `https://codeberg.org/publicinformation-ie/publicinformation-data/ns/sector#Health` | `Health` | Health | Health services |
| `https://codeberg.org/publicinformation-ie/publicinformation-data/ns/sector#Education` | `Education` | Education | Education services |
| `https://codeberg.org/publicinformation-ie/publicinformation-data/ns/sector#Justice` | `Justice` | Justice | Justice and legal services |
| `https://codeberg.org/publicinformation-ie/publicinformation-data/ns/sector#Transport` | `Transport` | Transport | Transport services |

### Geographic Coverage Vocabulary

ISO 3166-2:IE region codes for Ireland. Includes nationwide (IE) and all counties.

---

## Provenance Information

**Primary Source:** [https://foi.gov.ie/all-foi-bodies](https://foi.gov.ie/all-foi-bodies)

**Transformation Process:** Data is extracted from the FOI.gov.ie master list, transformed through the PublicInformation.ie pipeline, and published in multiple open data formats.

**Pipeline:** [https://codeberg.org/publicinformation-ie/publicinformation-data](https://codeberg.org/publicinformation-ie/publicinformation-data)

---

## License

This dataset is licensed under **Creative Commons Attribution 4.0 International (CC-BY 4.0)**.

You are free to:
- Share — copy and redistribute the material in any medium or format
- Adapt — remix, transform, and build upon the material for any purpose, even commercially

Under the following terms:
- **Attribution** — You must give appropriate credit, provide a link to the license, and indicate if changes were made.

Full license text: [https://creativecommons.org/licenses/by/4.0/](https://creativecommons.org/licenses/by/4.0/)

---

## Contact Information

**Publisher:** [PublicInformation.ie](https://www.publicinformation.ie/)

**Email:** [dave@publicinformation.ie](mailto:dave@publicinformation.ie)

**Repository:** [https://codeberg.org/publicinformation-ie/publicinformation-data](https://codeberg.org/publicinformation-ie/publicinformation-data)
