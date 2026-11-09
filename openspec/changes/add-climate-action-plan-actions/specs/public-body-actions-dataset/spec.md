# Spec Delta

## Purpose

The published contract of the `public-body-actions` dataset: how a published action is identified, cited and addressed, how actions are assigned to the plan edition that declares them, how an edition's extracted actions are checked against an independent list before they publish, and how a change to that contract is versioned. No spec covers this dataset today; these requirements record the contract as this change leaves it, including the existing behaviour it must preserve.

## ADDED Requirements

### Requirement: Action identity is the reference its plan publishes

A published action SHALL be identified by its plan edition together with the action reference that edition itself prints — an ordinal such as `12` for a plan that numbers its actions, or a code such as `EL/23/1` or `EL/23/6/A` for a plan that codes them. `action_number` SHALL carry that reference as text, exactly as printed apart from whitespace normalisation. A row whose reference cannot be read confidently SHALL be excluded and logged, never given a synthetic or positional number.

#### Scenario: Coded plan reference

- **WHEN** a Climate Action Plan annex prints an action as `EL/23/1`
- **THEN** the published action has `action_number` `"EL/23/1"` and `action_id` `<plan_slug>#EL/23/1`

#### Scenario: Ordinal plan reference

- **WHEN** a plan prints an action as `12.`
- **THEN** the published action has `action_number` `"12"`, and its `action_id` is unchanged from the previous release

#### Scenario: Unreadable reference

- **WHEN** an action row carries no reference that can be read confidently
- **THEN** the row is excluded, an error names the document, page and raw cell text, and no number is invented for it

### Requirement: Printed flags are separated from identity and preserved

A reference printed with recognised flag suffixes SHALL be identified without them. The recognised flags are `*`, `**` and `(TF)`, in any combination and order. Every published action SHALL carry `action_reference_printed` (the reference as printed, whitespace-normalised) and `action_flags`, a list drawn from the closed set `non_reportable`, `duplicate`, `taskforce`. An unrecognised suffix SHALL NOT be stripped. Recognising a new flag is a reviewed change to this requirement.

#### Scenario: Flagged reference

- **WHEN** an annex prints `TR/23/46(TF)` or `TR/24/4 (TF)`
- **THEN** the action is identified as `TR/23/46` (or `TR/24/4`), `action_reference_printed` is `TR/23/46(TF)` (or `TR/24/4 (TF)`), and `action_flags` is `[taskforce]`

#### Scenario: Combined flags

- **WHEN** an annex prints `RE/23/2*` or `TR/23/26**(TF)`
- **THEN** the actions are identified as `RE/23/2` with `action_flags` `[non_reportable]` and `TR/23/26` with `action_flags` `[duplicate, taskforce]`

#### Scenario: Unflagged reference

- **WHEN** an action's reference carries no flag, including every ordinal reference
- **THEN** its `action_flags` is empty

#### Scenario: Same action printed both ways

- **WHEN** one source prints `TR/23/46(TF)` and another prints `TR/23/46`
- **THEN** both resolve to the single action `TR/23/46`

#### Scenario: Unrecognised suffix

- **WHEN** a reference carries a parenthesised suffix other than a recognised flag, such as `EL/23/4(X)`
- **THEN** it is not stripped, and the row is excluded and logged with the raw reference

### Requirement: Published identity is permanent

Once published, an action's `action_id` and URI SHALL NOT change on re-extraction or republication. A change to how identity is represented SHALL be published as a contract change at the version severity it warrants.

#### Scenario: Re-extraction keeps identity

- **WHEN** the corpus is re-extracted and republished with no change to the source documents
- **THEN** every previously published action keeps its `action_id` and URI

### Requirement: Action URIs are derived from the printed reference

An action's URI SHALL be `{base}/action/{plan_slug}/{reference}`, where each `/` in a coded reference is kept as a path separator, so a sub-action's URI sits beneath its parent's. A reference SHALL contain only ASCII letters, digits and `/`, with no empty segment; a reference outside that set SHALL be excluded and logged rather than escaped or rewritten.

#### Scenario: Coded reference URI

- **WHEN** action `EL/23/6/A` of `climate-action-plan-2023-annex-of-actions` is published
- **THEN** its URI ends `/action/climate-action-plan-2023-annex-of-actions/EL/23/6/A`

#### Scenario: Existing URIs unchanged

- **WHEN** the dataset is republished under this contract
- **THEN** every action URI published by the previous release is unchanged byte for byte

#### Scenario: Reference outside the permitted characters

- **WHEN** a reference contains a character other than an ASCII letter, a digit or `/`
- **THEN** the action is excluded and an error records the raw reference

### Requirement: Sub-actions are actions in their own right

A sub-action (a reference ending in a letter, as its own segment or attached to the final number) SHALL be published as its own action, with its reference as printed. Its parent is the reference with that letter removed. Where the parent is a published action of the same edition, the dataset SHALL record a `part_of` relationship from sub-action to parent; otherwise the sub-action publishes without one.

#### Scenario: Parent published

- **WHEN** both `EL/23/6` and `EL/23/6/A` are published actions of one edition
- **THEN** a `part_of` relationship links `…#EL/23/6/A` to `…#EL/23/6`

#### Scenario: Letter attached to the number

- **WHEN** `EL/23/10A` and `EL/23/10` are both published actions of one edition
- **THEN** `EL/23/10A` keeps its printed reference in its identity and URI, and a `part_of` relationship links it to `…#EL/23/10`

#### Scenario: Parent not published

- **WHEN** `EL/23/6/A` is published and `EL/23/6` is not
- **THEN** `EL/23/6/A` is published and no `part_of` relationship is emitted for it

### Requirement: Actions belong to the edition that declares them

A row whose code year (its delivery year) is earlier than the edition's year is a legacy reprint, and SHALL be excluded from that edition and logged. Any other row SHALL be published under the edition that prints it. Where two editions print the same reference as their own, both SHALL publish it, linked by `carried_forward_to` from the earlier to the later.

#### Scenario: Legacy row in a later annex

- **WHEN** the 2025 annex reprints action `EL/23/1`
- **THEN** no 2025 action is published for that row, and the exclusion is logged with the document, page and reference

#### Scenario: Forward-year action in an earlier plan

- **WHEN** the 2023 annex prints `RE/24/1` as one of its actions
- **THEN** it is published as an action of the 2023 edition

#### Scenario: Same reference printed by two editions

- **WHEN** both the 2023 and the 2025 annex print `LU/25/1`
- **THEN** both editions publish it, and a `carried_forward_to` relationship links the 2023 action to the 2025 action

### Requirement: References to unpublished editions stay unresolved

A relationship whose target is an action of a plan edition not in the dataset SHALL keep a null `to_action_id`. It SHALL NOT be resolved by matching its number or code against an action of a different edition.

#### Scenario: Earlier Climate Action Plan cited by number

- **WHEN** a transport plan cites "CAP action 268" (a Climate Action Plan 2021 number) and only the CAP23–CAP25 editions are published
- **THEN** the relationship keeps `to_plan_hint` `CAP` and a null `to_action_id`

### Requirement: Source misprints are corrected only by curated, evidenced declarations

A reference misprinted by its source MAY be corrected only by a correction declared on the document's curated entry, citing the page, the printed reference, the corrected reference and its evidence. The corrected reference SHALL be the identity, and `action_reference_printed` SHALL keep the misprint. A declared correction whose printed reference isn't found SHALL be a fatal error.

#### Scenario: Misprinted duplicate reference

- **WHEN** the 2023 annex prints `BE/23/36` on page 57 for the action the XLSX lists as `BE/23/38`, and a correction is declared
- **THEN** the action publishes as `BE/23/38` with `action_reference_printed` `BE/23/36`

#### Scenario: Stale correction

- **WHEN** a declared correction's printed reference doesn't appear on its page
- **THEN** extraction fails, naming the document and the correction

### Requirement: A "same as parent" action cell inherits the parent's text

An action row whose action text is printed as "-" SHALL publish the action text of its parent row in the same table. A "-" row with no parent row SHALL be excluded and logged.

#### Scenario: Sub-action printed with "-"

- **WHEN** `EL/23/6/A` prints "-" as its action text beneath `EL/23/6`
- **THEN** `EL/23/6/A` publishes with the action text of `EL/23/6`

### Requirement: Extracted actions are reconciled before they publish

Before a plan edition's actions first publish, they SHALL be reconciled against an independent list of that edition's actions published by the State, where one exists, by reference and by text. Every reference on the independent list SHALL resolve to an extracted action, and every text mismatch SHALL be either fixed or recorded with its reason. The edition's action count SHALL be pinned on its curated entry, and publication SHALL fail when the extracted count differs from the pin.

#### Scenario: Independent list names an action that was not extracted

- **WHEN** the independent list carries reference `MA/23/5` and no extracted action has it
- **THEN** reconciliation reports the missing reference and the edition does not publish until it is resolved

#### Scenario: Extracted action absent from a partial list

- **WHEN** the independent list covers only some of the edition's actions (for example, those due in one year)
- **THEN** extracted actions absent from it are reported for review but do not block publication

#### Scenario: Count drift

- **WHEN** an edition's extracted action count differs from its pinned count
- **THEN** publication fails, naming the edition, the expected count and the actual count

### Requirement: Existing editions are unaffected

Adding a plan edition SHALL NOT change the actions, status observations or relationships already published for any other edition, apart from the representation changes recorded in this contract: `action_number` becoming text and the addition of `action_reference_printed` and `action_flags`.

#### Scenario: Transport editions after the CAP editions are added

- **WHEN** the dataset is republished with the CAP23–CAP25 editions added
- **THEN** every transport action, observation and relationship row is identical to the previous release, except that `action_number` is text and each action gains `action_reference_printed` (equal to its `action_number` for ordinal plans) and an empty `action_flags`

### Requirement: Breaking contract changes are versioned and staged

A change that alters the type or meaning of a published field SHALL be published as a new MAJOR version in its own versioned directory, with the `latest` mirror, the catalog's `owl:versionInfo` and the changelog updated together. The `latest` mirror SHALL NOT move to a new MAJOR version until known consumers of `latest` accept it.

#### Scenario: `action_number` becomes text

- **WHEN** `action_number` changes from integer to text
- **THEN** the dataset publishes as 3.0.0 under its own versioned directory, with a changelog entry that names the change

#### Scenario: Consumer not yet compatible

- **WHEN** a known consumer of `latest` still requires an integer `action_number`
- **THEN** `latest` stays on the previous MAJOR version
