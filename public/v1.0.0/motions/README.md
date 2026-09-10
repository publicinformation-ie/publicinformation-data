# Motions at Irish Local Authority Meetings

**Dataset URI:** `https://publicinformation-ie.codeberg.page/publicinformation-data/dataset/motions`

Motions moved at meetings of Irish local authorities, extracted from the authorities' published meeting minutes. Each motion records who proposed and seconded it, the meeting date and type, and its outcome. Part of the PublicInformation.ie Open Data Publishing initiative.

**Base URI:** `https://publicinformation-ie.codeberg.page/publicinformation-data/`

## Versioning

This directory (`v1.0.0/`) is an immutable, versioned release. `../../latest/motions/` always mirrors the newest version. Releases are also tagged in git (`motions-v1.0.0`). This dataset versions independently of the Public Bodies dataset. `dct:modified` in the catalogue metadata is updated automatically only when the published payload content actually changes; `owl:versionInfo` is bumped by hand only for breaking or additive schema changes.

## Data Model

Each motion record contains:

| Property | Type | Description | Required |
|----------|------|--------------|----------|
| `@id` | URI | Persistent Cool URI for the motion, `https://data.publicinformation.ie/motion/{motion_id}` | Yes |
| `@type` | String | Entity type (`mot:Motion`) | Yes |
| `public_body` | URI | The `@id` of the public body (local authority) whose meeting this motion was moved at, from the [Public Bodies dataset](../public-bodies/public-bodies.jsonld) | Yes |
| `public_body_id` | Integer | The body's internal `public_body_id`, retained as a join key | Yes |
| `motion_id` | String | Canonical motion identifier, `<body slug>/<meeting date>/m<NNN>` | Yes |
| `municipal_district` | String | Municipal district the motion was moved in; absent for full-council meetings | No |
| `meeting_date` | Date | Date of the meeting at which the motion was moved (`YYYY-MM-DD`) | Yes |
| `meeting_type` | String | `council` or `municipal_district` | Yes |
| `source_file_url` | URI | URL of the source meeting minutes file the motion was extracted from | Yes |
| `motion_text` | String | The motion as recorded in the minutes | Yes |
| `proposer` | String | Councillor who proposed the motion; may be absent if not recorded | No |
| `seconder` | String | Councillor who seconded the motion; may be absent if not recorded | No |
| `status` | String | Outcome of the motion, one of the [motion-status vocabulary](../../vocabularies/motion-status.csv) terms | Yes |

## Files

- **[motions.jsonld](motions.jsonld)** — JSON-LD, single `@context` + `@graph` of all records
- **[motions.csv](motions.csv)** — CSV, one row per motion
- **[motions.csv-metadata.json](motions.csv-metadata.json)** — CSV on the Web (CSVW) metadata for the CSV file
- **[../../schemas/motions.schema.json](../../schemas/motions.schema.json)** — JSON Schema
- **[../../vocabularies/motion-status.csv](../../vocabularies/motion-status.csv)** — the closed `status` vocabulary
- **[../../catalog/dataset-motions.ttl](../../catalog/dataset-motions.ttl)** — DCAT-AP 3.0 dataset metadata (RDF/Turtle), related to the Public Bodies dataset via `dct:relation`

## Relationship to Public Bodies

Every record's `public_body` field is the exact same URI published as `@id` in the [Public Bodies dataset](../public-bodies/public-bodies.jsonld). The link is resolved through the same permanent slug machinery as public-bodies (seeded in `slug_seed.json`), never through the minutes pipeline's own body slug — so even if that slug drifts, the published URI always matches public-bodies. A motion whose `public_body_id` does not resolve to a known body fails publication rather than being guessed or dropped. To join the two datasets, match `motions[].public_body` against `public-bodies[].@id`, or use the retained `public_body_id`.

## Status Vocabulary

`status` is a closed set of six terms, published at [../../vocabularies/motion-status.csv](../../vocabularies/motion-status.csv) and mirrored by the JSON Schema's `status` enum:

| Notation | Meaning |
|----------|---------|
| `carried` | The motion was carried (passed) |
| `carried_as_amended` | The motion was carried with amendments |
| `not_carried` | The motion was defeated |
| `withdrawn` | The motion was withdrawn by its proposer |
| `deferred` | The motion was deferred to a later meeting |
| `not_recorded` | No outcome for the motion was recorded in the minutes |

`meeting_type` is a two-value derived flag (`council` | `municipal_district`), not a controlled list, so it is constrained only by the schema.

## Provenance

Source: the `minutes_pipeline` (`pipelines/minutes_pipeline/`), which discovers meeting-minutes PDFs published by local authorities, converts and OCRs them, extracts the motions recorded in them, and canonicalises each motion into a flat record with a stable `motion_id`. The published records are built from the step's canonical `export_motions/output.json` by `scripts/transform_motions.py`. Each motion's `public_body_id` is resolved against the Public Bodies data as described above. Motion text is published verbatim as recorded in the minutes.

## Usage

### JSON-LD Example

```json
{
  "@id": "https://data.publicinformation.ie/motion/meath/2026-05-20/m001",
  "@type": "mot:Motion",
  "public_body": "https://data.publicinformation.ie/body/meath-county-council",
  "public_body_id": 1511,
  "motion_id": "meath/2026-05-20/m001",
  "municipal_district": "Navan",
  "meeting_date": "2026-05-20",
  "meeting_type": "municipal_district",
  "source_file_url": "https://www.meath.ie/system/files/media/file-uploads/2026-06/05-2026%20Minutes%20Navan%20MD.pdf",
  "motion_text": "To ask the Executive to approve the construction of a pedestrian crossing on Abbey Road at the bus stop and car park behind the Town Hall.",
  "proposer": "Eddie Fennessy",
  "seconder": "Francis Deane",
  "status": "not_recorded"
}
```

### Accessing Data

```bash
curl -L https://publicinformation-ie.codeberg.page/publicinformation-data/latest/motions/motions.jsonld
curl -L https://publicinformation-ie.codeberg.page/publicinformation-data/latest/motions/motions.csv
```

## Known Limitations

- **One authority so far.** The dataset currently covers the minutes ingested for Meath County Council. As more authorities' minutes are added to the `minutes_pipeline`, new motions flow into this dataset.
- **As recorded, not as decided.** `motion_text` is the motion as recorded in the minutes; `status` reflects what the minutes record about the outcome. Where the minutes record no outcome, `status` is `not_recorded` — this is an absence in the source, not an implicit "carried".
- **`proposer`/`seconder` may be blank** when the minutes do not name them.
- **No parliamentary detail.** A motion's eventual implementation, or debate around it, is out of scope for this dataset.

## Conformance

| Standard | Level | Notes |
|----------|-------|-------|
| 5-Star Linked Data | ★★★★ | JSON-LD with dereferenceable URIs; no SPARQL endpoint |
| DCAT-AP 3.0 | Full | Complete dataset metadata, related to Public Bodies via `dct:relation` |
| JSON Schema | Full | All properties defined; core fields required; `status` and `meeting_type` enumerated |

## License

Creative Commons Attribution 4.0 International (CC-BY 4.0). See [LICENSE](../../LICENSE).

## Contact

**Publisher:** [PublicInformation.ie](https://www.publicinformation.ie/)
**Email:** dave@publicinformation.ie
**Repository:** https://codeberg.org/publicinformation-ie/publicinformation-data