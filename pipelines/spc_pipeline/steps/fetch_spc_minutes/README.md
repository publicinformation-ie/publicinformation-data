# fetch_spc_minutes

Downloads each discovered minutes PDF into a git-ignored cache and records its
content, with the words and coordinates the later steps need.

## Output

`results[]`, one record per successfully fetched, text-bearing PDF:

| Field | Meaning |
|---|---|
| `committee_id`, `committee_name`, `public_body_id`, `page_url` | carried from discovery |
| `file_url`, `link_text` | the source file |
| `sha256`, `size_bytes`, `retrieved_at` | provenance of the exact downloaded bytes |
| `page_count` | number of pages |
| `pages[]` | `{page, width, height, words[]}`; each word has `text`, `x0`, `x1`, `top`, `bottom` |

## Cache

`pipelines/spc_pipeline/cache/<url-hash>-<file-name>.pdf` plus a `.json`
sidecar with the first retrieval time. A warm cache makes no HTTP request; the
sha256 and size are recomputed from the cached bytes.

## Errors

| Type | When |
|---|---|
| `DownloadFailed` | the request failed (network, HTTP status or certificate verification); no record is produced |
| `NoTextLayer` | the PDF has no extractable text on any page; no record is produced and OCR is never attempted |

## TLS

`www.meath.ie` omits the DigiCert Global G2 intermediate from its chain.
`src/lib/certs` loads the committed public intermediate as an extra
verification certificate. Verification stays on; a certificate failure is
never worked around.
