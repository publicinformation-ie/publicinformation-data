## Purpose

Publishes the UN Classification of the Functions of Government (COFOG) 1999 as a stable, machine-readable vocabulary, so data on the site can be classified with it and linked to its terms.

## Requirements

### Requirement: Source and provenance are pinned

The published vocabulary SHALL be derived from the committed COFOG 1999 reference data, and its scheme metadata SHALL repeat the source URL, retrieval date, sha256 and classification version that the reference records. A reference file missing any of those fields SHALL fail generation rather than produce a vocabulary with incomplete provenance.

#### Scenario: Provenance reaches the published JSON

- **WHEN** the vocabulary is generated from the committed reference
- **THEN** its scheme metadata carries the UNSD source URL, the retrieval date, the source sha256 and version `1999`

#### Scenario: Incomplete provenance fails

- **WHEN** the reference data has no sha256 or no source URL
- **THEN** generation fails and no distribution is written

### Requirement: The full COFOG 1999 hierarchy is published

The vocabulary SHALL contain the committed source's 10 divisions, 69 groups and 109 classes, 188 concepts in total. Every concept SHALL carry a code, a label, a level and its parent code. Every group's parent SHALL be a division and every class's parent SHALL be a group in the same scheme.

#### Scenario: Counts match the source

- **WHEN** the vocabulary is generated
- **THEN** it contains 10 divisions, 69 groups and 109 classes

#### Scenario: Parent integrity

- **WHEN** every concept's parent is looked up
- **THEN** each group resolves to a division, each class resolves to a group, and no division has a parent

#### Scenario: Known transport term

- **WHEN** a consumer looks up `04.5.1`
- **THEN** it is a class labelled "Road transport" whose parent is the group `04.5` "Transport"

#### Scenario: Unknown code is absent

- **WHEN** a consumer looks up `04.5.9`
- **THEN** no concept with that code exists in any distribution

### Requirement: Classes state whether the service is collective or individual

Each class SHALL carry the service type indicated by the source's `(CS)` or `(IS)` marker, published as `collective` or `individual`. Divisions and groups SHALL carry no service type.

#### Scenario: Collective class

- **WHEN** the class `04.5.1` is published
- **THEN** its service type is `collective`

#### Scenario: Individual class

- **WHEN** the class `07.1.1` is published
- **THEN** its service type is `individual`

#### Scenario: Group has no service type

- **WHEN** the group `04.5` is published
- **THEN** its service type is null

### Requirement: The JSON distribution is hierarchical and indexed

The JSON distribution SHALL carry the scheme metadata and a nested divisions → groups → classes tree. It SHALL also carry a flat concept index keyed by code. Every concept SHALL appear exactly once in the tree and exactly once in the index, with the same URI, label, level, parent and service type in both.

#### Scenario: Tree and index agree

- **WHEN** the JSON distribution is read
- **THEN** the set of codes in the tree equals the set of codes in the index, and each concept's fields are identical in both

#### Scenario: Lookup by code

- **WHEN** a consumer needs the label and parent of `06.4.0`
- **THEN** the flat index returns "Street lighting", level `class`, parent `06.4` and service type `collective`

### Requirement: The CSV distribution keeps the established vocabulary shape

The CSV distribution SHALL keep the four columns `uri`, `notation`, `name` and `description`, and its CSVW metadata SHALL declare `uri` as the primary key and `{uri}` as the `aboutUrl`. It SHALL hold one row per concept. Its notation set SHALL equal the JSON concept code set.

#### Scenario: CSVW contract

- **WHEN** the CSVW metadata is read
- **THEN** it declares `uri` as the primary key and `{uri}` as the about URL

#### Scenario: CSV and JSON agree

- **WHEN** the CSV notations are compared with the JSON codes
- **THEN** the two sets are equal and both hold 188 terms

### Requirement: The Turtle distribution is SKOS

The Turtle distribution SHALL be valid Turtle encoding one `skos:ConceptScheme` and one `skos:Concept` per code. Each concept SHALL carry `skos:notation`, an English `skos:prefLabel`, `skos:inScheme` and, except for divisions, `skos:broader` pointing to its parent. The scheme SHALL list each division as a `skos:hasTopConcept`. Each class SHALL carry a `skos:scopeNote` naming its service type.

#### Scenario: Turtle parses with 188 concepts

- **WHEN** the Turtle distribution is parsed as RDF
- **THEN** it holds one concept scheme and 188 concepts

#### Scenario: SKOS hierarchy matches the JSON

- **WHEN** each concept's `skos:broader` is compared with the JSON parent
- **THEN** they agree for every group and class, and the scheme's top concepts are the 10 divisions

#### Scenario: Service type note

- **WHEN** the class `07.1.1` is read from the Turtle distribution
- **THEN** it carries a scope note identifying it as an individual service

### Requirement: Term URIs are stable and dereferenceable

Every concept SHALL have the URI `https://data.publicinformation.ie/ns/cofog#<code>`. The base `https://data.publicinformation.ie/ns/cofog` SHALL resolve to an HTML page that states the namespace is COFOG 1999 and links to the JSON, CSV, CSVW metadata and Turtle distributions. The URI shape SHALL NOT change within this vocabulary's lifetime.

#### Scenario: Term URI pattern

- **WHEN** the class `04.5.1` is published
- **THEN** its URI is `https://data.publicinformation.ie/ns/cofog#04.5.1`

#### Scenario: Resolver page links every distribution

- **WHEN** a browser opens `https://data.publicinformation.ie/ns/cofog`
- **THEN** it reaches a page that names COFOG 1999 and links to the JSON, CSV, CSVW metadata and Turtle files

### Requirement: The vocabulary is versioned independently of its consumers

The scheme SHALL declare the classification version `1999` and state that it is COFOG 1999. A future COFOG revision SHALL use a new namespace and a new vocabulary rather than changing the meaning of an existing term. Consumers SHALL be able to rely on `/ns/cofog#<code>` continuing to mean the 1999 concept.

#### Scenario: Version is published

- **WHEN** the scheme metadata is read
- **THEN** it declares version `1999`

#### Scenario: A revision does not overwrite the namespace

- **WHEN** a revised COFOG is adopted in future
- **THEN** it is published under a new namespace, and the 1999 concepts and their URIs are unchanged

### Requirement: One generator writes every distribution

A single generation command SHALL write the JSON, CSV, CSVW metadata and Turtle from the pinned reference. A check mode SHALL exit non-zero when any committed distribution differs from what the command would write. The generator SHALL write no distribution when the hierarchy is invalid.

#### Scenario: Regeneration is a no-op

- **WHEN** the generator runs against an unchanged reference
- **THEN** every committed distribution is byte-identical and the check mode exits zero

#### Scenario: Drift is detected

- **WHEN** a committed distribution is edited by hand
- **THEN** the check mode exits non-zero and names the differing file

#### Scenario: Invalid hierarchy writes nothing

- **WHEN** the reference contains a group whose parent is missing or a duplicate code
- **THEN** generation fails and no distribution is changed

### Requirement: The vocabulary is catalogued and documented

The vocabulary SHALL have a DCAT catalogue record listing its distributions and licence, a README describing its formats, URI pattern, provenance, licence and versioning, a link from the public data README, and a changelog entry. `DATA_SOURCES.md` SHALL attribute the UNSD source and state the licence.

#### Scenario: Catalogue parses and lists distributions

- **WHEN** the catalogue record is parsed as Turtle
- **THEN** it describes the COFOG vocabulary with JSON, CSV and Turtle distributions

#### Scenario: Discovery links reach the README

- **WHEN** a reader follows the public data README's vocabulary link
- **THEN** they reach the COFOG README, which links to every distribution

#### Scenario: Changelog and attribution exist

- **WHEN** the change is published
- **THEN** `public/CHANGELOG.md` records it and `DATA_SOURCES.md` names the UNSD source and licence

### Requirement: The SPC vocabulary contract is unchanged

The SPC schema's COFOG enum SHALL remain equal to the published notation set. No published SPC record SHALL change, and the SPC vocabulary build SHALL continue to produce the attendance, decision and subdomain vocabularies.

#### Scenario: Schema enum still matches

- **WHEN** the SPC test suite compares the schema enum with the published vocabulary
- **THEN** the notation sets are equal

#### Scenario: No SPC payload moves

- **WHEN** the vocabulary is regenerated
- **THEN** no file under `public/latest/spc-meetings/` or `public/v1.2.0/spc-meetings/` changes

#### Scenario: Other SPC vocabularies still build

- **WHEN** the SPC vocabulary build runs
- **THEN** it still writes the attendance, decision and transport-subdomain vocabularies
