# FOI Request Files Dataset

**Dataset URI:** `https://data.publicinformation.ie/dataset/foi-request-files`

Source disclosure log files (PDF and Excel) published by Irish public bodies under Freedom of Information legislation. Each file is linked to exactly one public body via the [Public Bodies dataset](../public-bodies/README.md). Part of the PublicInformation.ie Open Data Publishing initiative.

**Base URI:** `https://data.publicinformation.ie/`

## Versioning

This directory (`v1.0.0/`) is an immutable, versioned release. `../../latest/foi-request-files/` always mirrors the newest version. Releases are also tagged in git (`foi-request-files-v1.0.0`). This dataset versions independently of the Public Bodies dataset — FOI request files are added far more often than new public bodies are recognized.

## Data Model

Each FOI request file record contains:

| Property | Type | Description | Required |
|----------|------|--------------|----------|
| `@id` | URI | Persistent Cool URI for the file, derived from a hash of `document_url` | Yes |
| `@type` | String | Entity type (`foi:FoiRequestFile`) | Yes |
| `public_body` | URI | The `@id` of the public body this file belongs to, from the [Public Bodies dataset](../public-bodies/public-bodies.jsonld) | Yes |
| `document_url` | URI | Direct URL to the source PDF/Excel file | Yes |
| `source_page_url` | URI | URL of the page the file link was found on | Yes |
| `file_type` | String | `pdf`, `xlsx`, or `xls` | Yes |

Fields intentionally **not** published in this Slice: `date_added` — not populated by any upstream crawl for any current record.

## Files

- **[foi-request-files.jsonld](foi-request-files.jsonld)** — JSON-LD, single `@context` + `@graph` of all records
- **[foi-request-files.csv](foi-request-files.csv)** — CSV, one row per file
- **[foi-request-files.csv-metadata.json](foi-request-files.csv-metadata.json)** — CSV on the Web (CSVW) metadata for the CSV file
- **[../../schemas/foi-request-files.schema.json](../../schemas/foi-request-files.schema.json)** — JSON Schema
- **[../../catalog/dataset-foi-request-files.ttl](../../catalog/dataset-foi-request-files.ttl)** — DCAT-AP 3.0 dataset metadata (RDF/Turtle), related to the Public Bodies dataset via `dct:relation`

## Relationship to Public Bodies

Every record's `public_body` field is the exact same URI published as `@id` in the [Public Bodies dataset](../public-bodies/public-bodies.jsonld). To join the two datasets, match `foi-request-files[].public_body` against `public-bodies[].@id`.

## Provenance

Files are discovered by crawling each public body's disclosure log page (`find_disclosure_pages` / `find_disclosure_files` pipeline steps) and following one level of year-indexed sub-pages. `source_page_url` records exactly which page a given file link was found on.

## Usage

### JSON-LD Example

```json
{
  "@id": "https://data.publicinformation.ie/foi-request-file/8f3a1c9d2e01",
  "@type": "foi:FoiRequestFile",
  "public_body": "https://data.publicinformation.ie/body/central-bank-of-ireland",
  "document_url": "https://www.centralbank.ie/docs/default-source/foi-disclosure-log-q1-2026.pdf",
  "source_page_url": "https://www.centralbank.ie/about/freedom-of-information/foi-disclosure-log",
  "file_type": "pdf"
}
```

### Accessing Data

```bash
curl -L https://data.publicinformation.ie/latest/foi-request-files/foi-request-files.jsonld
curl -L https://data.publicinformation.ie/latest/foi-request-files/foi-request-files.csv
```

## Known Limitations

- `date_added` exists as a field in the underlying pipeline output but is null for every current record — omitted from this Slice; would be reintroduced if a future pipeline step starts populating it.
- This dataset lists the source **files** found on each body's disclosure log page. It does not include the individual FOI request records extracted from inside those files (`decision_status`, `requester_type`, etc.) — that is a separate, larger dataset not covered by this release.

## Conformance

| Standard | Level | Notes |
|----------|-------|-------|
| 5-Star Linked Data | ★★★★ | JSON-LD with dereferenceable URIs; no SPARQL endpoint |
| DCAT-AP 3.0 | Full | Complete dataset metadata, related to Public Bodies via `dct:relation` |
| JSON Schema | Full | All properties defined, `file_type` vocabulary-backed `enum` |

## License

Creative Commons Attribution 4.0 International (CC-BY 4.0). See [LICENSE](../../LICENSE).

## Contact

**Publisher:** [PublicInformation.ie](https://www.publicinformation.ie/)
**Email:** dave@publicinformation.ie
**Repository:** https://github.com/publicinformation-ie/publicinformation-data
