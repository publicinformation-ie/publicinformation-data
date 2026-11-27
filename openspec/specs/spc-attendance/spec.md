## Purpose

Records who attended each SPC meeting, covering councillors, sectoral representatives, officials and presenters, as attendance records resolved to stable person IDs, so attendance can be counted per person across meetings without guessing who a printed name refers to.

## Requirements

### Requirement: People are held in a committed register

Every person who may appear in attendance SHALL be listed in a committed people register with a person ID, a canonical name, a kind (`councillor`, `sectoral_representative`, `official` or `guest`) and every alias and initialism they appear under. A councillor's person ID SHALL be their councillor ID from the councillor reference or, for a council it does not cover, from the committed SPC councillor roster. Any other person's ID SHALL be `<council_slug>/person/<name-slug>`.

#### Scenario: Councillor reuses the councillor ID

- **WHEN** the register lists Cllr Mike Bray
- **THEN** his person ID is `meath/michael-bray`, the ID already in the councillor reference

#### Scenario: Councillor from the SPC roster

- **WHEN** the register lists Councillor Kevin Duffy of Kildare County Council, who is absent from the councillor reference
- **THEN** his person ID is `kildare/kevin-duffy`, the ID in the SPC councillor roster

#### Scenario: Sectoral representative

- **WHEN** the register lists Mr. Dave Anderson, PPN representative
- **THEN** his person ID is `meath/person/dave-anderson` and his kind is `sectoral_representative`

#### Scenario: Unknown councillor ID

- **WHEN** a register entry of kind `councillor` names an ID absent from both the councillor reference and the SPC councillor roster
- **THEN** the run stops with an error naming the entry

### Requirement: Attendance is parsed by category

The attendance block SHALL be read by the geometry its committee's layout declares (a two-column table, or labelled lines whose continuation lines align with the value), so label text never becomes part of a name. Every printed name SHALL be assigned the category and status the layout maps its label to. A label the layout does not map SHALL produce an `UnrecognisedHeaderLayout` error, and no meeting is produced.

#### Scenario: Two-column table

- **GIVEN** the table row "Attendees – (Councillors):" whose value cell reads "Cllr Mike Bray (MB) Chair, Cllr Amanda Smith (AS), Cllr Sean Drew Cllr Paddy Meade (PM) online"
- **WHEN** attendance is parsed
- **THEN** the names are Mike Bray, Amanda Smith, Sean Drew and Paddy Meade, and none contains the text "(Councillors):"

#### Scenario: Labelled list with continuation lines

- **GIVEN** a Westmeath header with "Members Present: Cllr. Frankie Keena (Cathaoirleach)" followed by the lines "Cllr. Tom Farrell" and "Cllr. Niall Gaffney" aligned under the value
- **WHEN** attendance is parsed
- **THEN** all three names are in category `councillors` and none contains "Members Present:"

#### Scenario: Kildare labels

- **WHEN** a Kildare header has rows labelled "Attendees:", "Also Present", "Guest:", "Apologies:" and "Not Present:"
- **THEN** their names are in categories `councillors`, `officials`, `guests`, `apologies` and `absent` respectively

#### Scenario: Kildare "Also" and "Online" rows

- **WHEN** a Kildare header has a row labelled "Also" (without "Present") and a row labelled "Online:" listing "Councillor Kevin Duffy (Chair)"
- **THEN** the "Also" names are in category `officials`, and Kevin Duffy is in category `councillors` with mode `remote`, because the label itself prints the mode

#### Scenario: Unmapped label

- **WHEN** a header has a label row "Observers:" that its layout does not map
- **THEN** an `UnrecognisedHeaderLayout` error names the meeting and the label, and no meeting is produced

### Requirement: Every attendee gets an attendance record

Each resolved name SHALL produce one attendance record with the meeting ID, person ID, the name as printed, the category, the role as printed (for example "Chair", "PPN Rep", "Senior Engineer"), a status and a mode. Status SHALL be `present` for attendee, official, guest and presenter rows, `apologies` for names in an absent/apologies row or marked "apologies", and `absent` for names in a row that records non-attendance separately from apologies (Kildare's "Not Present").

#### Scenario: Official is recorded

- **WHEN** the officials row lists "Joan Carroll (JC) Senior Executive Officer"
- **THEN** an attendance record has person `meath/person/joan-carroll`, category `official`, role "Senior Executive Officer" and status `present`

#### Scenario: Official who also presented

- **WHEN** the officials row lists "Caroline Corrigan (CC) Senior Engineer" and the presenters row lists her presentation
- **THEN** one attendance record is produced, category `officials`, `presented: true`, and both printed roles joined

#### Scenario: Presenter who sent apologies

- **WHEN** the presenters row reads "Cllr Alan Tobin, Cllr Helen Meyer, apologies, …"
- **THEN** Alan Tobin is `present` and Helen Meyer is `apologies`

#### Scenario: Member in apologies

- **WHEN** the absent/apologies row lists "Cllr Wayne Harding (WH)"
- **THEN** an attendance record has person `meath/wayne-harding` and status `apologies`

#### Scenario: Not present without apologies

- **WHEN** a Kildare "Not Present:" row lists "Councillor Ger Dunne"
- **THEN** an attendance record has category `absent` and status `absent`, not `apologies`

### Requirement: Mode is recorded only when printed

Mode SHALL be `remote` when the name's entry is marked "online" or "via Teams", in any letter case, `in_person` when marked "in person", and `not_stated` otherwise. A mode marker SHALL apply only to the entry it is printed in and SHALL NOT be carried to other names.

#### Scenario: Remote attendee

- **WHEN** the entry reads "Cllr Caroline O'Reilly (COR) online"
- **THEN** her mode is `remote`

#### Scenario: Unmarked attendee

- **WHEN** the entry reads "Cllr Amanda Smith (AS)" with no marker
- **THEN** her mode is `not_stated`

#### Scenario: Capitalised marker

- **WHEN** a Kildare entry reads "Cllr Paul Ward (Online)"
- **THEN** his mode is `remote`

### Requirement: Names resolve only through the register

A printed name SHALL be matched to a person only by an exact match, after whitespace, apostrophe and title normalisation, against the person's canonical name or a registered alias. Fuzzy or similarity matching SHALL NOT be used. Empty fragments such as a stray "Cllr," SHALL be ignored and counted.

#### Scenario: Registered spelling variant

- **GIVEN** "Nicholas Whyatt" is a registered alias of Nicholas Wyatt
- **WHEN** the minutes print "Nicholas Whyatt, Senior Engineer"
- **THEN** the record resolves to Nicholas Wyatt's person ID

#### Scenario: Stray title fragment

- **WHEN** the row reads "Cllr, Cllr Wayne Harding (WH)"
- **THEN** one record for Wayne Harding is produced and the stray "Cllr," is counted, not treated as a person

### Requirement: Unresolved or contradictory attendance blocks the meeting's attendance

A printed name that matches no person, or matches more than one, SHALL produce an `UnresolvedAttendee` error. A person recorded as both `present` and `apologies` at one meeting SHALL produce a `ContradictoryAttendance` error. A meeting with either error SHALL have none of its attendance published until a human resolves it. Its rendered minutes SHALL still be published.

#### Scenario: New guest presenter

- **WHEN** a meeting lists a presenter who is not in the register
- **THEN** an `UnresolvedAttendee` error names the meeting and the printed name, and no attendance for that meeting is published

#### Scenario: Resolved by a register edit

- **WHEN** the presenter is added to the register and the pipeline is re-run
- **THEN** that meeting's attendance is published in full

### Requirement: The SPC councillor roster agrees with the councillor reference

The committed SPC councillor roster SHALL list, for each councillor of a council the councillor reference does not cover, a councillor ID of the form `<council_slug>/<name-slug>`, name, `public_body_id` and the source page. An ID in both files with a different name or body, or a roster entry for a council the reference covers, SHALL fail validation.

#### Scenario: Council covered by the reference

- **WHEN** the roster lists a Meath councillor
- **THEN** validation fails, naming the entry, because Meath is covered by the councillor reference

#### Scenario: Reference later covers a roster council

- **WHEN** the councillor reference gains Kildare councillors and one shares an ID with a roster entry but has a different name
- **THEN** validation fails, naming the ID
