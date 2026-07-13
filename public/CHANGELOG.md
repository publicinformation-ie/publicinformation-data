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
