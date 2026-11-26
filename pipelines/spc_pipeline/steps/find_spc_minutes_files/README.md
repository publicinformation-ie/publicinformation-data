# find_spc_minutes_files

Reads each committed committee's page and collects its minutes PDFs, ignoring
agendas and every other link.

## Input and configuration

- Input: the `find_local_authorities` output, used only to validate that each
  committee's `public_body_id` is a real local authority.
- `committees.json`: a list of entries with `committee_id`
  (`<council>/<committee>`), `name`, `public_body_id`, `page_url` and
  `minutes_link_pattern` (a regular expression matched against the link text,
  or the file name when the text does not say minutes).

## Output

`results[]`, one record per minutes PDF, de-duplicated by URL:

| Field | Meaning |
|---|---|
| `committee_id`, `committee_name`, `public_body_id` | the declaring committee |
| `page_url` | the page the link was found on |
| `file_url` | the absolute PDF URL |
| `link_text` | the anchor text as printed |

## Errors

| Type | When |
|---|---|
| `CommitteeConfigError` | a missing field, a duplicate committee ID, an invalid pattern, or a `public_body_id` absent from the local-authority list |
| `PageFetchFailed` | the page could not be fetched (network, TLS or HTTP status) |
| `NoMinutesFound` | the page loaded but no link matched the minutes pattern |

All three are fatal for the run (`errors.json`, non-zero exit). Verification is
never disabled: a certificate failure is reported, not bypassed.
