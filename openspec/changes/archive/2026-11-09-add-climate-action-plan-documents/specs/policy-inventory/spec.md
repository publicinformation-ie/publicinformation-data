# Spec Delta

## Purpose

Defines the curated policy inventory contract: the hand-authored inventory files that are the single source of truth for `policy_id` validation in `documents.yml` and `input_plans_*.md`, extended from a single transport file to a set of per-domain files merged into one validation namespace.

## ADDED Requirements

### Requirement: Multiple domain inventory files

The inventory SHALL be built from every domain file matching `pipelines/document_pipeline/input_plans_<domain>.md`, and the set of valid `policy_id` values for `documents.yml` entries SHALL be the union of the policies defined across those files. Existing domain files (transport) SHALL remain unchanged by another domain's records.

#### Scenario: Climate policy resolves validation

- **WHEN** a `documents.yml` entry declares a `policy_id` defined in a climate inventory file
- **THEN** validation accepts it exactly as it would accept a transport inventory policy

#### Scenario: Transport inventory is untouched

- **WHEN** a climate inventory file is added
- **THEN** every previously recorded transport `policy_id`, its policy number, and its identity continue to resolve to the same values

#### Scenario: Unknown policy_id is still fatal

- **WHEN** a `documents.yml` entry declares a `policy_id` present in no inventory file
- **THEN** validation raises a process-fatal error naming the entry

### Requirement: Per-file structural self-consistency

Each inventory file SHALL be independently structurally valid — a well-formed master table, per-policy URL table numbering that exactly matches the master row count, and any domain-specific row rules (such as code-of-practice numbering) verified within that file — and a malformed row in any domain file SHALL stop the run process-fatally rather than publish.

#### Scenario: Malformed row in a domain file

- **WHEN** any domain inventory file contains a malformed or ambiguous table row
- **THEN** the run stops with an error citing the file, line, and violation

### Requirement: policy_id uniqueness across the merged namespace

The `policy_id` namespace SHALL be global across all domain inventory files: if two files derive the same `policy_id`, validation SHALL fail process-fatally instead of silently merging or reshadowing either policy's identity.

#### Scenario: Cross-domain slug collision

- **WHEN** two domain inventory files produce the same `policy_id`
- **THEN** validation fails, naming both colliding policies and their files

### Requirement: Each policy records its domain

Every policy record SHALL carry the domain of the inventory file it was parsed from, so a consumer can select the policies of one domain without inspecting file paths. A policy's position within its own file SHALL remain file-scoped and SHALL NOT be treated as an identifier across the merged namespace.

#### Scenario: Domain is available on every record

- **WHEN** the merged inventory is loaded
- **THEN** each policy carries the domain of its source file

#### Scenario: Positions are not globally unique

- **WHEN** two domain files each define a policy at the same position in their own master table
- **THEN** both load successfully, and neither position is treated as identifying a policy

### Requirement: Inventory-derived datasets are scoped to one domain

A published dataset built from the inventory SHALL include only the policies of the domain it publishes. Adding a new domain inventory file SHALL NOT change the contents of an existing domain's published dataset.

#### Scenario: New domain does not alter an existing dataset

- **WHEN** a new domain inventory file is added and an existing single-domain dataset is republished
- **THEN** its published rows are unchanged and its content-freshness stamp is untouched

#### Scenario: Out-of-domain policy is excluded

- **WHEN** the inventory contains a policy from another domain
- **THEN** that policy does not appear in the published dataset of the domain being published
