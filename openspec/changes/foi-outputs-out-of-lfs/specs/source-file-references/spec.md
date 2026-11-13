# Spec Delta

## Purpose

Defines how files that originate from public bodies are held by the repository: by source URL and committed checksum rather than as committed copies, fetched into an uncommitted cache and verified before a pipeline reads them.

## ADDED Requirements

### Requirement: Public-body source files are referenced, not committed

A file obtained from a public body that a pipeline needs as input SHALL be declared by its source URL and a sha256 checksum in committed configuration, and its bytes SHALL NOT be committed. This applies to the Climate Action Plan status annexes.

#### Scenario: Annex declared by reference

- **WHEN** a progress report declares a status annex
- **THEN** its entry carries the annex URL and the expected sha256, and no annex file is tracked by git

### Requirement: Source files are fetched into an uncommitted cache

The pipeline SHALL fetch a referenced file into a git-ignored cache when it is absent there, and SHALL reuse a cached copy whose checksum matches without refetching.

#### Scenario: Cold cache

- **WHEN** the step runs with an empty cache and the source URL is reachable
- **THEN** it downloads the file, verifies its checksum and the downstream step reads the cached copy

#### Scenario: Warm cache

- **WHEN** a cached copy with the declared checksum exists
- **THEN** no network request is made for that file

### Requirement: Checksum mismatch is surfaced, not absorbed

A fetched or cached file whose sha256 differs from the declared checksum SHALL NOT be read as that source. The run SHALL record an error naming the file, the declared checksum and the observed one.

#### Scenario: Publisher replaced the file

- **WHEN** the downloaded bytes' sha256 differs from the declared one
- **THEN** the step records a checksum-mismatch error for that document and emits no status observations from it

#### Scenario: Source unreachable

- **WHEN** the file is not cached and the URL cannot be fetched
- **THEN** the step records a fetch error for that document rather than crashing the run
