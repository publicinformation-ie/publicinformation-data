# Transport Policies Dataset

**Dataset URI:** `https://data.publicinformation.ie/dataset/transport-policies`

The 21 transport policies, strategies and codes of practice that define the scope of the PublicInformation.ie transport document corpus: who issued each one, the period it covers, its scope, its statutory linkages, its official source pages, and the PDF documents curated for it. Part of the PublicInformation.ie Open Data Publishing initiative.

**Base URI:** `https://data.publicinformation.ie/`

## Versioning

This directory (`v1.0.0/`) is an immutable, versioned release. `../../latest/transport-policies/` always mirrors the newest version. Releases are also tagged in git (`transport-policies-v1.0.0`). The inventory is curated by hand, and `has_document` / `doc_slugs` are updated as more documents are curated.

## Data Model

Each row of `transport-policies.csv` is one policy:

| Column | Type | Description | Required |
|--------|------|-------------|----------|
| `policy_id` | String | Permanent public identifier: the slugified policy title (primary key) | Yes |
| `title` | String | Policy, strategy or code of practice title | Yes |
| `kind` | String | `policy` or `code-of-practice` | Yes |
| `issuing_authority` | String | Primary issuing body | Yes |
| `horizon` | String | Period the policy covers, as published | Yes |
| `scope` | String | Scope and strategic pillar | Yes |
| `linkages` | String | Core statutory and framework linkages | Yes |
| `source_urls` | URI list | Official landing page(s) for the policy, separated by `\|` | Yes |
| `has_document` | Boolean | `true` when at least one PDF is curated for this policy in the documents pipeline (not necessarily published; see the documents dataset `index.json`) | Yes |
| `doc_slugs` | String list | `doc_slug` of each curated PDF for this policy, separated by `\|` (empty when `has_document` is `false`); see the documents dataset `index.json` for whether each slug is published or listed under `failed` | No |

## Files

- **[transport-policies.csv](transport-policies.csv)** — CSV, one row per policy
- **[transport-policies.csv-metadata.json](transport-policies.csv-metadata.json)** — CSV on the Web (CSVW) metadata for the CSV file
- **[../../schemas/transport-policies.schema.json](../../schemas/transport-policies.schema.json)** — JSON Schema for a row after CSVW parsing
- **[../../catalog/dataset-transport-policies.ttl](../../catalog/dataset-transport-policies.ttl)** — DCAT-AP 3.0 dataset metadata (RDF/Turtle)

This is a CSV-only dataset; there is no JSON-LD file.

## Provenance

Source: the curated transport policy inventory (`input_plans_transport.md`) and the curated document list (`documents.yml`) in the document pipeline. The CSV is built by `scripts/transform_transport_policies.py`, which joins each policy to the documents curated for it.

## Usage

### Python Example

```python
import csv

with open("transport-policies.csv", newline="", encoding="utf-8") as fh:
    for row in csv.DictReader(fh):
        source_urls = [u for u in row["source_urls"].split("|") if u]
        doc_slugs = [s for s in row["doc_slugs"].split("|") if s]
        print(row["policy_id"], row["has_document"] == "true", doc_slugs)
```

### Accessing Data

```bash
curl -L https://data.publicinformation.ie/latest/transport-policies/transport-policies.csv
```

## Known Limitations

- **#17 Local Transport Plans** has no national publication.
- **#19 Maritime Safety Strategy** has no verified standalone document.
- `has_document=false` means no PDF is curated, not that none exists.

## Conformance

| Standard | Level | Notes |
|----------|-------|-------|
| CSVW | Full | Column metadata, `\|` list separators and primary key in the CSVW descriptor |
| DCAT-AP 3.0 | Full | Complete dataset metadata |
| JSON Schema | Full | All columns defined and required (applies after CSVW parsing) |

## License

Creative Commons Attribution 4.0 International (CC-BY 4.0). See [LICENSE](../../LICENSE).

## Contact

**Publisher:** [PublicInformation.ie](https://www.publicinformation.ie/)
**Email:** dave@publicinformation.ie
**Repository:** https://github.com/publicinformation-ie/publicinformation-data
