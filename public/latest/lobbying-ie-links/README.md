# lobbying.ie Links Dataset

**Dataset URI:** `https://publicinformation-ie.codeberg.page/publicinformation-data/dataset/lobbying-ie-links`

Links from Irish public bodies to their page on [lobbying.ie](https://www.lobbying.ie/), Ireland's Register of Lobbying, plus a point-in-time count of lobbying returns filed against each body. Each link is joined to exactly one public body via the [Public Bodies dataset](../public-bodies/README.md). Part of the PublicInformation.ie Open Data Publishing initiative.

**Base URI:** `https://publicinformation-ie.codeberg.page/publicinformation-data/`

## Versioning

This directory (`v1.0.0/`) is an immutable, versioned release. `../../latest/lobbying-ie-links/` always mirrors the newest version. Releases are also tagged in git (`lobbying-ie-links-v1.0.0`). This dataset versions independently of the Public Bodies dataset. lobbying.ie exposes a live JSON API — this dataset is refreshed by re-running `pipelines/lobbying_pipeline` against that live API, not by re-saving a source file.

## Data Model

Each lobbying.ie link record contains:

| Property | Type | Description | Required |
|----------|------|--------------|----------|
| `@id` | URI | Persistent Cool URI for the link record, under `/lobbying-ie-links/` (not the public body's own `@id` — this is an annotation record); path segment is lobbying.ie's own numeric ID, since lobbying.ie has no org slug | Yes |
| `@type` | String | Entity type (`lil:LobbyingIeLink`) | Yes |
| `public_body` | URI | The `@id` of the public body this link belongs to, from the [Public Bodies dataset](../public-bodies/public-bodies.jsonld) | Yes |
| `lobbyingie_id` | Integer | lobbying.ie's own numeric ID for the public body | Yes |
| `lobbyingie_url` | URI | Link to the body's filtered search results on lobbying.ie | Yes |
| `lobbyingie_returns_count` | Integer or null | Number of lobbying returns naming this body, as of the pipeline run that produced this record; `null` if that body's Search call failed | Yes |

## Files

- **[lobbying-ie-links.jsonld](lobbying-ie-links.jsonld)** — JSON-LD, single `@context` + `@graph` of all records
- **[lobbying-ie-links.csv](lobbying-ie-links.csv)** — CSV, one row per link
- **[lobbying-ie-links.csv-metadata.json](lobbying-ie-links.csv-metadata.json)** — CSV on the Web (CSVW) metadata for the CSV file
- **[../../schemas/lobbying-ie-links.schema.json](../../schemas/lobbying-ie-links.schema.json)** — JSON Schema
- **[../../catalog/dataset-lobbying-ie-links.ttl](../../catalog/dataset-lobbying-ie-links.ttl)** — DCAT-AP 3.0 dataset metadata (RDF/Turtle), related to the Public Bodies dataset via `dct:relation`

## Relationship to Public Bodies

Every record's `public_body` field is the exact same URI published as `@id` in the [Public Bodies dataset](../public-bodies/public-bodies.jsonld). To join the two datasets, match `lobbying-ie-links[].public_body` against `public-bodies[].@id`.

## Provenance

Source: lobbying.ie's public JSON API (`https://api.lobbying.ie/api/PublicBody` for the body list, `https://api.lobbying.ie/api/Search` for each body's lobbying-returns count), called live on every pipeline run (fetched for this release on 2026-07-13). Each fetched public body is resolved to a `public_body_id` by fuzzy name matching against the Public Bodies dataset (`SequenceMatcher` ratio, threshold 0.90, via the shared `src/lib/body_matching.py` helper also used by Who Does What and data.gov.ie Links), with any manual corrections recorded in the pipeline's `override.json`.

This release matched 121 of 170 lobbying.ie public body records (12 resolved via manual override for divergent naming — e.g. "The" prefixes, bilingual/Irish-language formatting, and word-order variants of the same current body — 49 dropped as unresolved, mostly historical/superseded department and agency names still visible in the register).

## Usage

### JSON-LD Example

```json
{
  "@id": "https://publicinformation-ie.codeberg.page/publicinformation-data/lobbying-ie-links/1571",
  "@type": "lil:LobbyingIeLink",
  "public_body": "https://publicinformation-ie.codeberg.page/publicinformation-data/body/some-public-body",
  "lobbyingie_id": 1571,
  "lobbyingie_url": "https://www.lobbying.ie/app/home/search?publicBodys=1571",
  "lobbyingie_returns_count": 1777
}
```

### Accessing Data

```bash
curl -L https://publicinformation-ie.codeberg.page/publicinformation-data/latest/lobbying-ie-links/lobbying-ie-links.jsonld
curl -L https://publicinformation-ie.codeberg.page/publicinformation-data/latest/lobbying-ie-links/lobbying-ie-links.csv
```

## Known Limitations

- **Only register entries matching a canonical public body by name are included.** lobbying.ie's register names sometimes diverge from canonical public body names (abbreviations, alternate forms), so a handful of register entries do not resolve to a canonical body and are intentionally excluded rather than guessed at.
- **`lobbyingie_returns_count` is a point-in-time snapshot, not a live count.** It reflects the count as of the pipeline run that produced the current release.
- **Link and return-count only — no return content.** This dataset records the link to each body's lobbying.ie search results and how many returns name it, not the subject matter, lobbyist, client, or dates of those returns. Publishing that richer, individual-return-level dataset is noted as possible future work.

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
