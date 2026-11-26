# SPC meetings

Strategic Policy Committee meetings of Irish local authorities: the people who
attended, their attendance, agenda items with COFOG 1999 topics, official
decisions as verbatim quotes, and the minutes rendered verbatim as Markdown.

## Files

- `meetings` – one row per meeting
- `people` – one row per person recorded in attendance
- `attendance` – one row per person per meeting (`attendance_published` is false
  on a meeting whose attendance is withheld)
- `items` – agenda items with their topics; `topics_published` is false when
  the topics were withheld
- `decisions` – official decisions as contiguous quotes from the minutes
- `minutes/<council>/<committee>/<date>.md` – the verbatim minutes

Each table is published as JSON-LD and CSV with CSVW metadata.
In CSV, an empty array and a withheld value both appear as an empty cell;
`topics_published` distinguishes a withheld item's topics from a genuine
empty subdomain list.

## Counts

- Meetings: 6
- People: 28
- Attendance rows: 98
- Items: 46
- Decisions: 17

## Sources

Minutes are published by Meath County Council and are reproduced verbatim.
COFOG 1999 is the UN Statistics Division classification; transport
subdomains follow the transport-governance vocabulary.

License: CC BY 4.0. See `DATA_SOURCES.md`.
