# parse_meeting_header

Reads the meeting date, venue and times from page 1, and the two-column
attendance table by word coordinates so label text never becomes part of a
name.

## Labels and blocks

The label column is the left-hand text; a block is one label line plus any
continuation lines:

| Printed label | Category |
|---|---|
| `Attendees – (Councillors):` | `councillors` |
| `Attendees – (Sectoral Representatives):` | `sectoral_representatives` |
| `Absent`, `Apologies:`, `Absent Apologies:` | `apologies` (combined) |
| `(Officials):` | `officials` |
| `Presenters`, `Presentations made by -` | `presenters` |

Any other label is `UnrecognisedHeaderLayout`; the meeting is not produced.
`Presentations made by -` may sit in the value column, with its text flowing on
after the dash; the label is skipped and the values parsed.

## Entry splitting

- A comma or semicolon ends a fragment.
- A title (`Cllr`, `Mr.`, `Ms.`, `Mrs.`, `Dr.`) after a complete name starts a
  new person (`Cllr Sean Drew Cllr Paddy Meade`).
- A wrapped line starts a new person when the next word is a capitalised name;
  a wrapped role (`Senior Engineer`, `Acting DOS /Senior Engineer`) continues
  the previous entry.
- A role fragment is attached to the person before it.
- Bullets (`•`, `\uf071`) start a new presenter.
- Markers are recorded, not treated as names: `online` / `via Teams` →
  `remote`; `in person` → `in_person`; `apologies` → `apologies`. A marker
  printed before a name applies to the previous entry.

Each entry has `category`, `printed_name`, `title`, `initials`, `role`,
`markers` and `raw`. `raw` is the printed text kept for the verbatim minutes;
when a role fragment is attached to the person before it, that fragment is
appended to `raw` too, so role text is never lost from the minutes. A stray
title fragment (`Cllr,`) is ignored and counted in `ignored_fragments`.

## Dates and identity

- Date: `19th February 2026` in the header line above the table.
- Month and year must agree with the link text when it gives them.
- End time: the printed value after `Meeting ended @` (formats vary).
- Meeting ID: `<committee_id>/<YYYY-MM-DD>`.

## Errors

| Type | When |
|---|---|
| `MeetingDateUnparseable` | no unambiguous `<day> <month> <year>` in the header |
| `MeetingDateMismatch` | the header's month/year disagrees with the link text |
| `UnrecognisedHeaderLayout` | no label column, or an unknown label |
| `DuplicateMeeting` | two files resolve to the same meeting ID; neither is produced |
| `ContradictoryInitials` | the same printed initials map to two names in one meeting |
