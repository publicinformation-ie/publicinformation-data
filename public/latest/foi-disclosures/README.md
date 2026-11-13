# FOI Disclosures Dataset

**Dataset URI:** `https://data.publicinformation.ie/dataset/foi-disclosures`

Individual Freedom of Information request records extracted from disclosure log files published by Irish public bodies. Each record is linked to exactly one public body via the [Public Bodies dataset](../public-bodies/README.md). Part of the PublicInformation.ie Open Data Publishing initiative.

**Base URI:** `https://data.publicinformation.ie/`

## Versioning

**The version number is the schema version; each release adds a build.** `1.0.0` (`owl:versionInfo`, the root `"version"` of the JSON-LD) changes only when field names, types or vocabularies change. Data refreshes within a schema version are published as **builds**, identified by the UTC release date.

- **Latest:** `https://data.publicinformation.ie/latest/foi-disclosures/` always serves the current build. These URLs are unchanged.
- **Immutable releases:** `https://releases.publicinformation.ie/foi-disclosures/v<schema>/<build>/` (for example `.../v1.0.0/20261113/`) holds `foi-disclosures.json`, `.csv`, `.jsonld`, `.xlsx`, `manifest.json` and `SHA256SUMS`. A release folder is never overwritten. Releases are tagged `foi-disclosures-v<schema>+<YYYYMMDD>` in git. (The earlier `foi-disclosures-v1.0.0` tag predates this scheme and has no release folder.)
- Other datasets keep in-repo `public/vX.Y.Z/` snapshots; this one does not, because its files are tens of megabytes.

## Storage layout

The source of truth in git is one canonical NDJSON file per public body, `bodies/<public_body_id>.ndjson` (one JSON object per line, sorted by `row_id`). The combined JSON, CSV, JSON-LD, XLSX and `bodies/manifest.json` are **built from those files and not committed**; the live site serves the built copies. `bodies/manifest.json` lists every body's name, file URL, row count, date range and `sha256`: start there to find one body without downloading the whole dataset.

After cloning, run `pip install -r scripts/requirements-build.txt && python scripts/build_foi_combined.py` to produce the combined files locally.

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
- **foi-disclosures.xlsx** — the same rows and columns as the CSV, as a workbook
- **[bodies/](bodies/)** — one NDJSON file per public body, plus `manifest.json`
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
  "@id": "https://data.publicinformation.ie/foi-disclosure/f292642e7af3",
  "@type": "foi:FoiDisclosure",
  "public_body": "https://data.publicinformation.ie/body/bord-bia",
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
curl -L https://data.publicinformation.ie/latest/foi-disclosures/foi-disclosures.jsonld
curl -L https://data.publicinformation.ie/latest/foi-disclosures/foi-disclosures.csv
```

No `git-lfs` client is needed for either command — both files are ordinary git-tracked content, served directly as static files.

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
**Repository:** https://github.com/publicinformation-ie/publicinformation-data
