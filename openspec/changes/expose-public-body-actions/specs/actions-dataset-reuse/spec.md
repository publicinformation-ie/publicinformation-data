## Purpose

Makes the public-body-actions open dataset consumable by publicinformation-web, so that extracted plan actions and their reported status are visible on publicinformation.ie body pages and reusable through the site's dataset catalogue and API mirrors.

## ADDED Requirements

### Requirement: The web build fetches the actions dataset from the open data site

The static build of publicinformation.ie SHALL fetch `latest/public-body-actions/public-body-actions.jsonld` from the configured data base URL (default `https://data.publicinformation.ie`, overridable for offline development) and SHALL parse its `@graph` into actions, status observations, and relationships.

#### Scenario: Successful fetch at build time

- **WHEN** the static build runs and the dataset is reachable
- **THEN** the build loads the JSON-LD graph and splits it into action, observation, and relationship records

#### Scenario: Offline development against a local checkout

- **WHEN** the data base URL is set to a local filesystem path (e.g. the sibling data repo's `public/` directory)
- **THEN** the dataset is read from disk and the build behaves identically

#### Scenario: Dataset unavailable or malformed

- **WHEN** the dataset cannot be fetched or does not match the expected shape
- **THEN** the build fails with an explicit error instead of silently rendering empty pages

### Requirement: The actions dataset is registered in the site dataset catalogue

The dataset SHALL be registered in the web site's dataset registry under the id `public-body-actions`, so that the generic catalogue page and API mirrors serve it like any other registered dataset.

#### Scenario: Catalogue page

- **WHEN** a user visits `/data/public-body-actions/`
- **THEN** the page presents the dataset's name, description, and records

#### Scenario: API mirrors

- **WHEN** a client requests `/api/data/public-body-actions.json` or `/api/data/public-body-actions.csv`
- **THEN** the response contains the actions records from the dataset

### Requirement: Body pages show the body's actions with their reported status

For every public body that has one or more actions, the site SHALL render a per-body actions page at `/bodies/<slug>/public-body-actions/`. Each listed action SHALL show its action text, the plan it belongs to, its original deadline, and its most recent reported status observation, if any.

#### Scenario: Body with actions

- **WHEN** a user visits the per-body actions page of a body that has actions
- **THEN** all of that body's actions are listed with action text, plan title, original deadline, and latest reported status

#### Scenario: Most recent observation determines displayed status

- **WHEN** an action has status observations from multiple reports
- **THEN** the observation with the most recent `as_of` date determines the status shown for that action

#### Scenario: Body without actions

- **WHEN** a body has no actions in the dataset
- **THEN** no per-body actions page is generated for that body and the actions dataset does not appear in that body's dataset navigation

### Requirement: Dataset freshness is surfaced

The actions dataset's freshness (derived from the fetched payload's last-modified signal, as with other build-time datasets) SHALL be available on its catalogue page.

#### Scenario: Freshness displayed

- **WHEN** a user views the `/data/public-body-actions/` catalogue page
- **THEN** the page shows when the dataset was last updated
