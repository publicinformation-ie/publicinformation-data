# FOI Disclosures Dataset

**Dataset URI:** `https://publicinformation-ie.codeberg.page/publicinformation-data/dataset/foi-disclosures`

Individual Freedom of Information request records extracted from disclosure log files published by Irish public bodies. Each record is linked to exactly one public body via the [Public Bodies dataset](../public-bodies/README.md). Part of the PublicInformation.ie Open Data Publishing initiative.

**Base URI:** `https://publicinformation-ie.codeberg.page/publicinformation-data/`

## Versioning

**This dataset does not keep a permanent versioned directory the way `public-bodies` and `foi-request-files` do.** Only `foi-disclosures.jsonld`/`foi-disclosures.csv` in this `latest/` directory ever exist in git — there is no `v1.0.0/foi-disclosures/` counterpart, and superseded versions' exact byte content is **not** guaranteed to remain fetchable once a new version overwrites this directory. This is a deliberate divergence, made because this dataset's files are an order of magnitude larger than the rest of the catalog (tens of megabytes), and Codeberg's git storage quota is shared across every repository in the `publicinformation-ie` organization.

The version number is still real and citable without needing the bytes: releases are tagged in git (`foi-disclosures-v1.0.0`), the JSON-LD document's root `"version"` field states which version `latest/` currently holds, and `../../CHANGELOG.md` records what changed and when. If you need an old version's exact content, request it — it may still exist in git history at the time you ask, but that is not a promise this dataset makes going forward.

## Data Model

Each FOI disclosure record contains:

| Property | Type | Description | Required |
|----------|------|--------------|----------|
| `@id` | URI | Persistent URI for the disclosure record, derived from a hash of `file_url` and the record's position within that file | Yes |
| `@type` | String | Entity type (`foi:FoiDisclosure`) | Yes |
| `public_body` | URI | The `@id` of the public body this disclosure belongs to, from the [Public Bodies dataset](../public-bodies/public-bodies.jsonld) | Yes |
| `name` | String | Public body name as it appears in the source disclosure log | Yes |
| `file_url` | URI | URL of the source disclosure log file this row was extracted from | Yes |
| `file_type` | String | `pdf`, `xlsx`, or `xls` | Yes |
| `foi_reference_id` | String | The public body's own reference number for this request, if published | No |
| `decision_date` | Date | Date the FOI decision was made | No |
| `date_received` | Date | Date the FOI request was received | No |
| `requester_type` | String | Category of requester, as published by the body | No |
| `decision_status` | String | Outcome of the request, as published by the body | No |
| `review_status` | String | Internal or Information Commissioner review outcome, if any | No |
| `related_request` | String | Reference to a related FOI request, if published | No |
| `request_description` | String | Free-text description of what was requested | No |
| `known_issues` | Array of String | Per-record extraction confidence signals; empty array means none were flagged | Yes |
| `missing_columns` | Array of String | Names of fields the source file did not provide a value for at all | Yes |

Optional fields are omitted entirely (not `null`) when absent in JSON-LD; the CSV emits an empty string cell for the same case. `known_issues`/`missing_columns` flatten to `|`-delimited strings in CSV.

## Files

- **[foi-disclosures.jsonld](foi-disclosures.jsonld)** — JSON-LD, single `@context` + `@graph` of all records, plus a root-level `version` field
- **[foi-disclosures.csv](foi-disclosures.csv)** — CSV, one row per disclosure
- **[foi-disclosures.csv-metadata.json](foi-disclosures.csv-metadata.json)** — CSV on the Web (CSVW) metadata for the CSV file
- **[../../schemas/foi-disclosures.schema.json](../../schemas/foi-disclosures.schema.json)** — JSON Schema
- **[../../catalog/dataset-foi-disclosures.ttl](../../catalog/dataset-foi-disclosures.ttl)** — DCAT-AP 3.0 dataset metadata (RDF/Turtle), related to the Public Bodies dataset via `dct:relation`

## Relationship to Public Bodies

Every record's `public_body` field is the exact same URI published as `@id` in the [Public Bodies dataset](../public-bodies/public-bodies.jsonld). To join the two datasets, match `foi-disclosures[].public_body` against `public-bodies[].@id`.

## Provenance

Disclosure log files are discovered via the [FOI Request Files dataset](../foi-request-files/README.md)'s crawl, then processed through OCR/extraction, canonicalization, and deduplication pipeline steps to produce one row per individual FOI request found inside each file.

## Usage

### JSON-LD Example

```json
{
  "@id": "https://publicinformation-ie.codeberg.page/publicinformation-data/foi-disclosure/f292642e7af3",
  "@type": "foi:FoiDisclosure",
  "public_body": "https://publicinformation-ie.codeberg.page/publicinformation-data/body/bord-bia",
  "name": "Bord Bia",
  "file_url": "https://www.bordbia.ie/globalassets/bordbia.ie/about/governance/foi-disclosure-log/foi-disclosure-log-2019.pdf",
  "file_type": "pdf",
  "decision_date": "2019-01-15",
  "date_received": "2019-01-02",
  "requester_type": "Journalist",
  "decision_status": "Granted",
  "request_description": "Total amount spent on bottled water in 2017 and 2018.",
  "known_issues": [],
  "missing_columns": ["foi_reference_id", "related_request", "review_status"]
}
```

### Accessing Data

```bash
curl -L https://publicinformation-ie.codeberg.page/publicinformation-data/latest/foi-disclosures/foi-disclosures.jsonld
curl -L https://publicinformation-ie.codeberg.page/publicinformation-data/latest/foi-disclosures/foi-disclosures.csv
```

No `git-lfs` client is needed for either command — both files are ordinary git-tracked content, served directly by Codeberg Pages.

## Known Limitations

- `known_issues` and `missing_columns` are per-record extraction confidence signals, not a global dataset quality score — a record with entries in either array is not necessarily wrong, only less certain in the specific way flagged.
- Superseded versions of this dataset's large files are not guaranteed to remain fetchable by exact bytes — see Versioning above.

## Conformance

| Standard | Level | Notes |
|----------|-------|-------|
| 5-Star Linked Data | ★★★★ | JSON-LD with dereferenceable URIs; no SPARQL endpoint |
| DCAT-AP 3.0 | Full | Complete dataset metadata, related to Public Bodies via `dct:relation` |
| JSON Schema | Full | All properties defined |

## License

Creative Commons Attribution 4.0 International (CC-BY 4.0). See [LICENSE](../../LICENSE).

## Contact

**Publisher:** [PublicInformation.ie](https://www.publicinformation.ie/)
**Email:** dave@publicinformation.ie
**Repository:** https://codeberg.org/publicinformation-ie/publicinformation-data
