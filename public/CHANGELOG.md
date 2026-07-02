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
