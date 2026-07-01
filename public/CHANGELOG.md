# Changelog

All notable changes to the Public Bodies dataset will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.0.0] - 2026-07-01

### Added
- Initial release of Public Bodies dataset as Slice 1 of open data best practices implementation
- JSON-LD format with Schema.org + custom vocabulary context
- CSV format with proper escaping
- JSON Schema for validation
- DCAT-AP 3.0 compliant metadata (RDF/Turtle)
- Controlled vocabularies: body-type, foi-scope, sector, geographic-coverage
- Full provenance chain from CSO.ie source through pipeline
- Comprehensive documentation
- CC-BY 4.0 license

### Changed
- Transformed from internal pipeline-data.json format to public Linked Data format
- Field names standardized to snake_case
- URIs use slugs instead of numeric IDs

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
