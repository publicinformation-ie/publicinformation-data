# render_spc_minutes

Renders each meeting's minutes as verbatim, phone-readable Markdown and proves
that no source word was added, lost or changed.

## Layouts

How a meeting is rendered follows its committee's layout profile
(`parse_meeting_header/layouts.py`):

| | `meath-table` | `kildare-table`, `westmeath-list` |
|---|---|---|
| Furniture | running header, `Page N of M`, footer (below) | none declared: nothing is removed |
| Body starts | after the `Item` table header | at the `body_start` the header parse recorded: the first line below the attendance block |
| Item headings | `N.N Title` | `Item 2 — Title`, `Item 2: Title`, `Item 9- Title`; `Item` is matched case-insensitively and `ltem` is read as `Item` |
| Attendance headings | Councillors, Sectoral Representatives, Absent / Apologies, Officials, Presenters | the layout's printed labels (`Attendees`, `Also present`, `Guests`, `Apologies`, `Not present`; `Members present`, `Sectoral reps`, ...) |

For a scanned meeting the source words are its OCR words, grouped into lines by
Tesseract's own line numbers and read in page order, so the word check proves
the render is **verbatim to the OCR text**, not to the printed page. Only
declared furniture is removed: a stray mark OCR reads that passed the
confidence gate is source text, and stays. Pages skipped by a reviewed override
have no words. An item heading OCR misreads (`Item &:` for `Item 8:`) is not a
heading: its words stay in the previous block, so nothing is lost. A heading
printed twice with the same number gets `item-3`, then `item-3-2`.

## Furniture (Meath)

Lines that repeat at the top or bottom edge of every page, the `Page N of M`
line, and the page-1 running header are removed and counted in
`furniture_removed` (`total`, `page_numbers`, and `by_text` with a `kind` of
`running_header`, `footer` or `unrecognised`). Three pages are normally needed;
a two-page document needs both. A single-page document keeps everything, since
frequency cannot tell a footer from the body. The edge requirement matters: a
genuine body line that repeats on three pages ("Noted.") stays in the body.
Body text that merely mentions `www.meath.ie` is kept. A removed edge line that
is neither the running header nor a recognisable Meath footer fails the meeting
(`UnrecognisedFurniture`) instead of silently deleting text.

## Blocks

- A line beginning `N.N` is a second-level heading with the number and title as
  printed and an anchor `{#item-N-N}` (dots become dashes).
- A line that is exactly `AOB` (optionally after a bullet glyph) is an AOB
  heading (`{#aob}`, then `{#aob-2}`, …).
- Bullet glyphs (`•`, `\uf071`) become `- ` list items; wrapped bullet lines
  are rejoined.
- `Proposed by`, `Seconded by` and `Meeting ended` start new blocks.
- Every other line is joined to the previous block with a space, including
  across page breaks.

Markup characters (`\`, backticks, `*`, `_`, `{`, `}`, `[`, `]`, `<`, `>`, `#`,
`|`, `&`) are backslash-escaped, and a leading `-`/`+` is escaped, so the file
contains no raw HTML.

## Front matter and attendance

The file begins with YAML front matter: meeting ID, committee ID and name,
`public_body_id`, date, venue, start/end times as printed, source URL, sha256,
`text_source` (`text_layer`, `ocr` or `mixed`) and, when any page was OCR'd, the
`ocr_engine`. The attendance block lists each printed category (the layout's
headings, above) with each entry's printed text; a withheld attendance is
marked in the block.

## Word check

Two independent checks run before a meeting is eligible for publication:

1. **Body.** The words read straight from the PDF pages (furniture and bullet
   glyphs removed) must equal the words recovered from the rendered body with
   markup and escapes undone, in the same order. Because the source side is not
   derived from the renderer's own block-splitting, a lost block, an
   over-eager page-1 header cut or a wrong furniture removal is a mismatch.
2. **Attendance.** Every word of a parsed role must appear in the printed text
   kept for that entry, and the rendered attendance list must equal the
   concatenated printed entries. A role fragment that never reached `raw`
   (and therefore never reached the Markdown) fails here.

On any difference the meeting is not published.

## Output

`results[]` carries the whole meeting record without `pages`, plus `markdown`,
`items[]` (`item_key`, `number`, `title`, `text`, `is_minutes_approval`),
`furniture_removed` and `word_check: "passed"`.

## Errors

| Type | When |
|---|---|
| `UnrecognisedBodyLayout` | page 1 has no `Item` table header |
| `RenderMismatch` | the rendered words differ from the source (message gives the first differing position and both words) |

A meeting with an error produces no output record.
