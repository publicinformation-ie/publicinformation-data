# render_spc_minutes

Renders each meeting's minutes as verbatim, phone-readable Markdown and proves
that no source word was added, lost or changed.

## Furniture

Lines that repeat on at least three pages, the `Page N of M` line, and the
page-1 running header are removed and counted in `furniture_removed`
(`total`, `page_numbers`, and `by_text` with a `kind` of `running_header` or
`footer`). Body text that merely mentions `www.meath.ie` is kept.

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
`public_body_id`, date, venue, start/end times as printed, source URL and
sha256. The attendance block lists each printed category (Councillors,
Sectoral Representatives, Absent / Apologies, Officials, Presenters) with each
entry's printed text; a withheld attendance is marked in the block.

## Word check

The source body words (furniture and bullet glyphs removed) must equal the
rendered body words (markup stripped) in the same order. On any difference the
meeting is not published.

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
