# fetch_spc_minutes

Downloads each discovered minutes PDF into a git-ignored cache and records its
content, with the words and coordinates the later steps need. A page with no
text-layer words is read by OCR, so scanned minutes are ingested too.

## Output

`results[]`, one record per successfully fetched PDF that yields text:

| Field | Meaning |
|---|---|
| `committee_id`, `committee_name`, `public_body_id`, `page_url` | carried from discovery |
| `file_url`, `link_text` | the source file |
| `sha256`, `size_bytes`, `retrieved_at` | provenance of the exact downloaded bytes |
| `page_count` | number of pages |
| `text_source` | `text_layer`, `ocr` or `mixed`, by where the words of the file's pages came from (pages skipped by override count as neither) |
| `ocr_engine` | the engine string, e.g. `tesseract 5.5.2 lang=eng psm=4 dpi=300`; `null` when no page's words came from OCR |
| `ocr_skipped_pages` | number of pages skipped by a reviewed override |
| `pages[]` | `{page, width, height, source, words[]}`; each word has `text`, `x0`, `x1`, `top`, `bottom` (PDF points, origin top left). `source` is `text_layer`, `ocr` or `skipped`. OCR words also carry `conf` (0–100) and OCR pages `ocr_mean_confidence`; a skipped page has `skip_reason` |

The step output's `metadata.ocr_skipped_pages` totals the skipped pages.

## OCR

Tesseract through `src/lib/ocr.py`: pages rendered by `pymupdf` at 300 dpi,
`--psm 4`, language `eng`; pixel boxes scaled by 72/300 into PDF points, so
the point-based layout rules of the later steps apply unchanged. The binary is
needed only for live runs and for regenerating fixtures (`brew install
tesseract`); CI replays committed output.

- **Cache.** `<pdf>.ocr.json` next to the PDF, keyed on the file's sha256,
  the page number and the engine string (version, language, psm, dpi). Any
  mismatch is a miss; stale output is never reused.
- **Fixtures.** `tests/fixtures/ocr/<meeting_date>.json` has the same layout
  as the cache file. Tests inject it through `FixtureOcr`, so they never call
  tesseract. `tests/test_ocr_fixtures.py` re-OCRs each fixture when the binary
  is present and reports drift; a tesseract upgrade is a deliberate fixture
  refresh with a reviewable `public/` diff.
- **Confidence gate.** `OCR_MIN_PAGE_CONF` (mean word confidence of a page,
  currently provisional at 60.0 until set from the scanned fixtures). A page
  below it fails the file. No individual word is dropped.
- **Overrides.** `ocr_overrides.json` is a list of
  `{file_sha256, page, action: "skip", reason}` for a page that is legitimately
  blank or signature-only. It is keyed on the file's sha256, so a republished
  file needs a fresh review. An entry that matches no fetched file is a
  `StaleOcrOverride` error.

## Cache

`pipelines/spc_pipeline/cache/<url-hash>-<file-name>.pdf` plus a `.json`
sidecar with the first retrieval time. A warm cache makes no HTTP request; the
sha256 and size are recomputed from the cached bytes.

## Errors

| Type | When |
|---|---|
| `DownloadFailed` | the request failed (network, HTTP status or certificate verification); no record is produced |
| `InvalidPdf` | the bytes are not a readable PDF |
| `NoTextRecovered` | neither the text layer nor OCR yields a word on any page; no record |
| `OcrLowConfidence` | an OCR'd page's mean confidence is below `OCR_MIN_PAGE_CONF`; the error names the page and confidence, and no record is produced |
| `EmptyOcrPage` | an OCR'd page has no words and no `ocr_overrides.json` entry; no record |
| `StaleOcrOverride` | an override's sha256 matches no file fetched in this run |

## TLS

`www.meath.ie` omits the DigiCert Global G2 intermediate from its chain.
`src/lib/certs` loads the committed public intermediate as an extra
verification certificate. Verification stays on; a certificate failure is
never worked around.
