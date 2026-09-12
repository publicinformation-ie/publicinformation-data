# find_minutes_files

Crawls each authority's minutes page(s) and collects links to meeting-minutes PDFs, mirroring `find_disclosure_files` with one-level year-link following.

## What it does

1. For each `minutes_page_url` from `find_meeting_minutes_pages_search`, fetches the page and walks its anchor links.
2. **PDF links** are kept only when the link text/href looks like minutes (`minutes`/`meeting`/`minute`) and not an agenda/report/other non-minutes document (negative tokens like `agenda`, `report`, `scheme`, `annual` disqualify).
3. **Out-of-scope links are excluded (logged, never silent)** — heritage/archive-collection paths (`heritage`, `collection(s)`, `museum`, `librar`, `digitised`; deliberately *not* bare `archiv*`, since councils file current minutes under `ArchivedMeetings` folders) and documents whose every year in link text/URL predates 1990 (e.g. digitised 1800s minute books). Each exclusion goes to `errors.json` (`ArchivedDocument` / `HistoricalDocument`) with `file_url` + `link_text` for human review.
4. **Year-looking anchor links** (`^(19|20)\d{2}$`, e.g. `2024`) are followed exactly one level deep to reach the actual PDF listing.
5. A `meeting_date` is parsed deterministically from the link text or file URL (ISO `YYYY-MM-DD`, or `D Month YYYY`); it is left `null` when not determinable — `extract_motions` may resolve it from document content, but an unresolved date ultimately fails closed in `canonicalize_motions`.

## Input

- `find_meeting_minutes_pages_search/output.json` (generated upstream)

## Output

`output.json` — `{ metadata, results: [...] }`, one record per PDF:

| Field | Description |
|---|---|
| `public_body_id` | Authority body id |
| `municipal_district` | District name, or `null` for the full-council page |
| `minutes_page_url` | The minutes page the link was found on |
| `file_url` | Absolute URL of the minutes PDF |
| `meeting_date` | ISO date or `null` |
| `link_text` | Anchor text of the link |

## Notable files

- `errors.json` — fetch/crawl failures per minutes page, plus `ArchivedDocument` / `HistoricalDocument` per-link exclusions.
- `output_schema.json` — JSON Schema for the output format.