# parse_meeting_header

Reads the meeting date, venue and times from page 1, and the attendance block
by word coordinates so label text never becomes part of a name.

## Layout profiles

Each committee names a profile (`layout` in `committees.json`). A profile is
data in `layouts.py`: the label vocabulary, the date line and the item heading
forms. Geometry is code in `header.py`. A label a profile does not map is
`UnrecognisedHeaderLayout`; a layout is never inferred.

| Profile | Council | Routine |
|---|---|---|
| `meath-table` | Meath | labels in a left column, values in a right column (the section below) |
| `kildare-table` | Kildare | `Label:  value` rows; continuation lines align under the value |
| `westmeath-list` | Westmeath | the same geometry, one person per line |

`kildare-table` and `westmeath-list` share one routine: the value column starts
where the first value word of each mapped label line sits, a continuation line
sits under it (within 12 pt, and within 1.5 line pitches of the previous line),
and the block ends at the first line that is neither. A line printed as
`Label   value` whose label is not mapped is an error naming the label.

| Profile | Printed label | Category | Status |
|---|---|---|---|
| Kildare | `Attendees` | `councillors` | present |
| Kildare | `Online` | `councillors`, mode `remote` | present |
| Kildare | `Also Present`, `Also` | `officials` | present |
| Kildare | `Guest` | `guests` | present |
| Kildare | `Apologies` | `apologies` | apologies |
| Kildare | `Not Present` | `absent` | absent |
| Westmeath | `Members Present` | `councillors` | present |
| Westmeath | `Sectoral Reps` | `sectoral_representatives` | present |
| Westmeath | `Officials Present` | `officials` | present |
| Westmeath | `External Presenters` | `presenters` | present |
| Westmeath | `Apologies` | `apologies` | apologies |

The category is the printed label's: Kildare's `Attendees` row also lists
non-councillors (PPN members), who are recorded under `councillors` here and
told apart by their `kind` in the people register.

Kildare entries start at each title (`Mr`, `Ms`, `Cllr`, `Councillor`,
`Cathaoirleach`); the name ends at a comma, a bracket or the first role word.
`Mr Cormac Browne and Eamonn Mahoney` is two people. Westmeath entries are one
per line, `Name, Role`. In these layouts a bracket prints a role
(`(Chair)`, `(Cathaoirleach)`), never initials, and an empty bracket left by a
mode marker (`(Online)`) is removed. Scanner noise tokens (`|`, a leading `-`)
are never names and are counted in `ignored_fragments`. Entry `raw` text keeps
what was printed.

Scanned pages arrive as OCR words with Tesseract's own line numbers. A scan is
rarely level, so words are grouped into lines by that number, not by `top`.

The header's date line is per profile. Kildare:
`held on Thursday, 11 December 2025 at 3.30p.m. in the Committee Room, ...`;
Westmeath: `held in the Executive Lounge, ... at 10am on Friday 6th March 2026`. A
date line with no year is `MeetingDateUnparseable`. The output record carries
`layout`, `text_source`, `ocr_engine` and `body_start` (`{page, top}`, where the
body begins below the attendance block).

## Meath layout (the table)

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
- Month and year must agree with the link text when it gives them (full or
  abbreviated month: `Nov`, `Sept`).
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
