# export_spc_meetings

Assembles the five published tables and the verbatim minutes from a completed
extraction run.

## Output

`results` holds:

- `meetings` — identity, date, venue, times, source URL and sha256,
  `minutes_path` (`minutes/<council>/<committee>/<YYYY-MM-DD>.md`) and
  `attendance_published`;
- `people` — only the people referenced by attendance or a decision, with
  `kind`, `councillor_id` and `public_body_id`;
- `attendance` — one row per person per meeting with `category`, `role`,
  `status`, `mode` and `presented`;
- `items` — number, key, title, text, `is_minutes_approval`, and the topics
  with `topics_published`;
- `decisions` — the verbatim decisions with their IDs;
- `minutes` — one Markdown document per meeting.

`report` counts each table plus `render_failures`, `attendance_withheld`,
`topics_withheld` and `by_error_type`, so every withheld part is visible.

## Withholding

- A meeting whose `word_check` is not `passed` (or that has no Markdown) is not
  published at all and is counted as a render failure.
- A meeting with withheld attendance keeps its record and minutes but has no
  attendance rows and `attendance_published: false`.
- Withheld topics keep the item with `topics_published: false`; a failed
  extraction keeps the meeting with no decisions and no topics.

The step exits 0: withholding is a designed, visible outcome recorded upstream
in `errors.json`. Missing or unreadable input is fatal.
