# Who Does What Dataset

**Dataset URI:** `https://publicinformation-ie.codeberg.page/publicinformation-data/dataset/who-does-what`

Links from Irish public bodies to their page on gov.ie's "Who Does What" campaign — a plain-English description of what each body does. Each link is joined to exactly one public body via the [Public Bodies dataset](../public-bodies/README.md). Part of the PublicInformation.ie Open Data Publishing initiative.

**Base URI:** `https://publicinformation-ie.codeberg.page/publicinformation-data/`

## Versioning

This directory (`v1.0.0/`) is an immutable, versioned release. `../../latest/who-does-what/` always mirrors the newest version. Releases are also tagged in git (`who-does-what-v1.0.0`). This dataset versions independently of the Public Bodies dataset — the source campaign page changes rarely and is refreshed by hand.

## Data Model

Each Who Does What link record contains:

| Property | Type | Description | Required |
|----------|------|--------------|----------|
| `@id` | URI | Persistent Cool URI for the link record, under `/who-does-what/` (not the public body's own `@id` — this is an annotation record, leaving room for future WDW-derived fields without touching `public-bodies`) | Yes |
| `@type` | String | Entity type (`wdw:WhoDoesWhatLink`) | Yes |
| `public_body` | URI | The `@id` of the public body this link belongs to, from the [Public Bodies dataset](../public-bodies/public-bodies.jsonld) | Yes |
| `wdw_slug` | String | gov.ie's own URL slug for the body (e.g. `publicjobs`), preserved as an alias — not used to rename our canonical slug | Yes |
| `wdw_url` | URI | Link to the body's "Who Does What" page on gov.ie | Yes |

## Files

- **[who-does-what.jsonld](who-does-what.jsonld)** — JSON-LD, single `@context` + `@graph` of all records
- **[who-does-what.csv](who-does-what.csv)** — CSV, one row per link
- **[who-does-what.csv-metadata.json](who-does-what.csv-metadata.json)** — CSV on the Web (CSVW) metadata for the CSV file
- **[../../schemas/who-does-what.schema.json](../../schemas/who-does-what.schema.json)** — JSON Schema
- **[../../catalog/dataset-who-does-what.ttl](../../catalog/dataset-who-does-what.ttl)** — DCAT-AP 3.0 dataset metadata (RDF/Turtle), related to the Public Bodies dataset via `dct:relation`

## Relationship to Public Bodies

Every record's `public_body` field is the exact same URI published as `@id` in the [Public Bodies dataset](../public-bodies/public-bodies.jsonld). To join the two datasets, match `who-does-what[].public_body` against `public-bodies[].@id`.

## Provenance

Source: the gov.ie "Who Does What" campaign page (`https://www.gov.ie/en/govie-team/campaigns/who-does-what/`, reached via the `whodoeswhat.gov.ie` vanity redirect), saved 2026-07-08 and committed as a static HTML source (`pipelines/wdw_pipeline/data/who-does-what.html`) rather than fetched live — the page changes rarely, and a live fetch would add scrape-breakage risk for negligible freshness benefit. To refresh, re-save the page and re-commit the file. Each linked body's `public_body_id` is resolved by fuzzy name matching against the Public Bodies dataset (`SequenceMatcher` ratio, threshold 0.90), with two manual corrections (`publicjobs` → Public Appointments Service, `Revenue Commissioners` → Office of the Revenue Commissioners) recorded in the pipeline's `override.json`.

## Usage

### JSON-LD Example

```json
{
  "@id": "https://publicinformation-ie.codeberg.page/publicinformation-data/who-does-what/office-of-the-revenue-commissioners",
  "@type": "wdw:WhoDoesWhatLink",
  "public_body": "https://publicinformation-ie.codeberg.page/publicinformation-data/body/office-of-the-revenue-commissioners",
  "wdw_slug": "office-of-the-revenue-commissioners",
  "wdw_url": "https://www.gov.ie/en/office-of-the-revenue-commissioners/organisation-information/revenue-commissioners-who-does-what/"
}
```

### Accessing Data

```bash
curl -L https://publicinformation-ie.codeberg.page/publicinformation-data/latest/who-does-what/who-does-what.jsonld
curl -L https://publicinformation-ie.codeberg.page/publicinformation-data/latest/who-does-what/who-does-what.csv
```

## Known Limitations

- **27 of 883 public bodies only.** The "Who Does What" campaign page itself only links 27 bodies (mostly government departments, plus a handful of offices: Revenue, OPW, State Laboratory, Tailte Éireann, etc.) — this is the campaign's own scope, not a scraping gap. The same way `contact_email` is partial in `public-bodies`, this dataset is complete relative to its source, not relative to the full set of public bodies.
- **Link only, not page content.** This dataset records the link to each body's Who Does What page, not the functions/description text on that page. Publishing that content is noted as likely future work.
- **Not live-refreshed.** The source HTML is a point-in-time snapshot, re-fetched by hand rather than automatically.

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
**Repository:** https://codeberg.org/publicinformation-ie/publicinformation-data
