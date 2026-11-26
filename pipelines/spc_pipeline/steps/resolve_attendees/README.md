# resolve_attendees

Matches every printed attendee to a person in `reference/people.json` and
records status and mode.

## Normalisation and matching

A printed name is normalised (NFKC; curly apostrophes to straight; `O' Reilly`
→ `O'Reilly`; `Mc Caul` → `McCaul`; leading titles removed; whitespace
collapsed; casefolded) and must match the canonical name or an alias **exactly**.
No fuzzy or similarity matching is used.

Status: `apologies` for the absent/apologies category or an `apologies` marker;
otherwise `present`. Mode: `remote` for `online`/`via Teams`, `in_person` for
`in person`, otherwise `not_stated`. A marker applies only to its own entry.

Meeting initials (the printed `(XX)` map) are used first; the register's
`initials` are the fallback. An initialism mapping to two people at one meeting
is an error, never a guess.

## One row per person

A person's name can be printed in two blocks — an official who also presented,
for example. Those prints are merged into **one** attendance row: the row keeps
the category earliest in the table (councillors, sectoral representatives,
officials, presenters, apologies), its roles are joined with `"; "`, and
`presented` is `true` when the name appears in the presenters block. A person
whose name appears only as a presenter keeps the `presenters` category. This is
what makes attendance countable per person per meeting.

## Output

Each meeting record keeps its page/date fields, gains `printed_attendance`
(always), and carries:

- `attendance[]` — `{meeting_id, person_id, printed_name, category, role,
  status, mode, presented}`, or `[]` when withheld;
- `attendance_published` — `false` when any error occurred for the meeting;
- `withheld_reasons[]` — one line per error.

The meeting's rendered minutes still publish when attendance is withheld.

## Errors

| Type | When |
|---|---|
| `UnresolvedAttendee` | a printed name matches no registered person |
| `ContradictoryAttendance` | one person is both `present` and `apologies` at a meeting |
| `ContradictoryMode` | one entry is marked both online and in person |

Any of these withholds the whole meeting's attendance.

## Adding a person or alias

Add an entry to `reference/people.json`:

```json
{
  "person_id": "meath/person/joan-carroll",
  "canonical_name": "Joan Carroll",
  "kind": "official",
  "councillor_id": null,
  "aliases": ["Joan Carroll"],
  "initials": ["JC"],
  "public_body_id": 1511
}
```

Councillors use their `councillors.csv` ID as `person_id`; everyone else uses
`<council_slug>/person/<name-slug>`. Aliases and canonical names must be unique
across people after normalisation; `tests/test_resolve_attendees.py` checks
this and the 4.1 register rules.
