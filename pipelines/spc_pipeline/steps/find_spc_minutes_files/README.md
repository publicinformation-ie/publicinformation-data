# find_spc_minutes_files

Reads each committed committee's page and collects its minutes PDFs, ignoring
agendas and every other link.

## Input and configuration

- Input: the `find_local_authorities` output, used only to validate that each
  committee's `public_body_id` is a real local authority.
- `committees.json`: a list of entries with `committee_id`
  (`<council>/<committee>`), `name` (the name printed on the minutes),
  `public_body_id`, `minutes_link_pattern` (a regular expression matched
  against the link text, or the file name when the text does not say minutes),
  `layout`, and the minutes page(s):
  - `page_url` (one page, a string) or `page_urls` (several; Kildare publishes
    a page per year). Never both. Only declared pages are read; there is no
    crawling.
  - `layout`: the header layout profile (`meath-table`, `kildare-table` or
    `westmeath-list`) that `parse_meeting_header` applies. An unknown layout is
    a fatal config error.
  - `years` (optional): limit discovery to these years. The year is the single
    four-digit year in the link text, never inferred from the file name or URL.
    A minutes link whose text gives no single year, while a window is set, is
    an `UndatedMinutesLink` error and is not collected.
  - `site_name` (optional): the committee's name on the council's own web
    page when it differs from the printed name. Provenance only.

Spaces in a link's path are percent-encoded once (`%20`), so a URL that is
already encoded is unchanged. A file linked from more than one page is
collected once.

Excluded councils: Wicklow (Sucuri JavaScript challenge) and Monaghan
(Cloudflare 403) block non-browser clients. They are not declared, and the
pipeline never solves or bypasses a challenge.

## Output

`results[]`, one record per minutes PDF, de-duplicated by URL:

| Field | Meaning |
|---|---|
| `committee_id`, `committee_name`, `public_body_id` | the declaring committee |
| `page_url` | the declared page the link was found on |
| `file_url` | the absolute PDF URL |
| `link_text` | the anchor text as printed |

## Errors

| Type | When |
|---|---|
| `CommitteeConfigError` | a missing field, a duplicate committee ID, an invalid pattern, or a `public_body_id` absent from the local-authority list |
| `PageFetchFailed` | a declared page could not be fetched (network, TLS or HTTP status such as a 403), or answered with a bot-protection challenge, which is never bypassed |
| `NoMinutesFound` | the pages loaded but no link matched the minutes pattern (and the year window) |
| `UndatedMinutesLink` | a `years` window is set and a minutes link's text has no single four-digit year |

All of these are fatal for the run (`errors.json`, non-zero exit). Verification is
never disabled: a certificate failure is reported, not bypassed.
