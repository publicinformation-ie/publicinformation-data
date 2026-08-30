# Changelog

All notable changes to the Public Bodies dataset will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [public-bodies 1.0.0] - 2026-07-02

### Added
- Public Bodies dataset (Slice 1) with all 883 known public sector organizations
- JSON-LD (single `@context` + `@graph`) and CSV formats for Public Bodies
- CSVW metadata for the Public Bodies CSV
- JSON Schema with `enum` constraints tied to the `body-type` and `foi-scope` vocabularies
- Controlled vocabularies: `body-type` (3 terms), `foi-scope` (2 terms) — trimmed to terms actually backed by pipeline data
- DCAT-AP metadata for the Public Bodies dataset, with corrected primary source and dereferenceable Codeberg Pages URIs
- Versioned (`v1.0.0/`) and `latest/` directory structure

## [foi-request-files 1.0.0] - 2026-07-02

### Added
- FOI Request Files dataset with all 1593 known disclosure log source files (PDF/Excel)
- JSON-LD (single `@context` + `@graph`) and CSV formats for FOI Request Files
- CSVW metadata for the FOI Request Files CSV
- JSON Schema with `file_type` enum
- DCAT-AP metadata for the FOI Request Files dataset, related to the Public Bodies dataset via `dct:relation`
- Versioned (`v1.0.0/`) and `latest/` directory structure, versioned independently of Public Bodies
- Each record's `public_body` field links to the same `@id` published in the Public Bodies dataset

## [foi-disclosures 1.0.0] - 2026-07-10

### Added
- FOI Disclosures dataset with all 60,177 known individual FOI request records extracted from disclosure log files
- JSON-LD (single `@context` + `@graph`, with a root-level `version` field) and CSV formats for FOI Disclosures
- CSVW metadata for the FOI Disclosures CSV, including `|`-delimited array column documentation
- JSON Schema for FOI Disclosures
- DCAT-AP metadata for the FOI Disclosures dataset, related to the Public Bodies dataset via `dct:relation`
- `latest/`-only directory structure (no permanent `v1.0.0/` copy) — this dataset does not guarantee old versions' exact bytes remain fetchable, unlike the rest of the catalog; see the dataset README's Versioning section
- Each record's `public_body` field links to the same `@id` published in the Public Bodies dataset
- `known_issues`/`missing_columns` published per record as data-transparency confidence signals

## [data-gov-ie-links 1.0.0] - 2026-07-11

### Added
- data.gov.ie Links dataset linking public bodies to their organisation page on Ireland's open data portal (data.gov.ie)
- JSON-LD (single `@context` + `@graph`) and CSV formats for data.gov.ie Links
- CSVW metadata for the data.gov.ie Links CSV
- JSON Schema for data.gov.ie Links
- DCAT-AP metadata for the data.gov.ie Links dataset, related to the Public Bodies dataset via `dct:relation`
- Versioned (`v1.0.0/`) and `latest/` directory structure, versioned independently of Public Bodies
- Each record's `public_body` field links to the same `@id` published in the Public Bodies dataset
- Source fetched live from data.gov.ie's CKAN REST API on every pipeline run, matched against Public Bodies by fuzzy name matching (threshold 0.90) via the shared `src/lib/body_matching.py` helper

## [lobbying-ie-links 1.0.0] - 2026-07-13

### Added
- lobbying.ie Links dataset linking public bodies to their page on Ireland's Register of Lobbying (lobbying.ie), with a point-in-time count of lobbying returns filed against each body
- JSON-LD (single `@context` + `@graph`) and CSV formats for lobbying.ie Links
- CSVW metadata for the lobbying.ie Links CSV
- JSON Schema for lobbying.ie Links
- DCAT-AP metadata for the lobbying.ie Links dataset, related to the Public Bodies dataset via `dct:relation`
- Versioned (`v1.0.0/`) and `latest/` directory structure, versioned independently of Public Bodies
- Each record's `public_body` field links to the same `@id` published in the Public Bodies dataset
- Source fetched live from lobbying.ie's public JSON API on every pipeline run, matched against Public Bodies by fuzzy name matching (threshold 0.90) via the shared `src/lib/body_matching.py` helper

## [documents 1.0.0] - 2026-08-11

### Added
- Documents dataset: large public-interest PDFs (transport strategies, statutory reviews, policy reports) split into per-section Markdown plus extracted figures, one reproducible `bundle.tar.gz` per document
- `public/documents/index.json` library manifest — one record per published document with page/chapter/section/figure counts, `bundle_sha256` and `source_sha256` for provenance and skip-if-unchanged caching
- Bundle interior fixed by `docs/superpowers/specs/2026-08-10-document-bundle-contract.md`: `meta.json` (navigation tree), `llms.txt`, `full.md`, `sections/<chapter-slug>/<section-slug>.md`, `assets/<figure-id>.webp` — `llms.txt` and `full.md` also published loose alongside the bundle
- DCAT-AP metadata for the Documents dataset, related to the Public Bodies dataset via `dct:relation`
- Each document's `public_body_id` field, where set, is a real id from the Public Bodies dataset
- Curated via a hand-authored `documents.yml`; first document is the National Transport Authority's Greater Dublin Area Transport Strategy 2022–2042
- A document that fails to build (e.g. a coverage gap) is omitted from `index.json`'s `documents` array and listed under `failed`, never half-published

## [public-body-actions 1.0.0] - 2026-08-29

### Added
- Public Body Actions dataset: three tables — `actions.csv`, `action-status-observations.csv`, `action-relationships.csv` — covering the Department of Transport's Sustainable Mobility Policy corpus (the 2022-2025 plan, its four progress reports, and the 2026-2030 plan)
- One CSVW `TableGroup` covering all three tables, declaring the foreign keys between them
- JSON-LD (single `@context` + `@graph`) and a JSON Schema with a `$defs` entry per table
- Controlled vocabularies: `action-status` (5 terms, with `first_seen_in` recording when each term entered the series) and `action-relationship` (7 terms, with `family`)
- DCAT-AP metadata for the dataset

### Removed
- `public/documents/actions.json` — the flat, document-centric action list published by `extract_actions`. Superseded by the `public-body-actions` dataset, which carries `public_body_id`, stable `action_id`s, original-vs-reported deadlines and a status history per action. This is a breaking change to a published path.

### Known limitations
- `action-status-observations.csv` includes observations only from the Year One progress report. Year Two, Year Three and the Final progress report use a table format the shared `extract_pages` table-header detection does not yet parse (`UnknownReportFormat`), so their observations are correctly skipped rather than fabricated. Tracked as a follow-up.

## Template

For future entries, use this template:

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- [Feature description]

### Changed
- [Change description]

### Fixed
- [Bug fix description]

### Removed
- [Removal description]
```
