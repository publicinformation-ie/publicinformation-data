# tests

Tests for `activetravel_pipeline`.

Most of them run from `fixtures/real_pages.json`, which holds verbatim
`pdfplumber` rows for a few pages of each of the five documents. That keeps the
suite deterministic and independent of the downloaded cache, which is
git-ignored.

## Fixtures

| Fixture | Contents |
|---|---|
| `real_pages.json` | One entry per document, each with a few pages of raw extracted rows |

Regenerate it after deliberately changing the source pages (needs the cache):

```python
import json, pdfplumber, sys
from pathlib import Path
sys.path[:0] = ["pipelines/activetravel_pipeline", "src"]
from allocations import normalise

cache = Path("pipelines/activetravel_pipeline/cache")
pages = {
    "nta-active-travel-2022": ("e7974bee0220e526", [1, 6, 59, 76]),
    "nta-active-travel-2023": ("5e51d615550b9e1e", [1, 7, 73]),
    "nta-active-travel-2024": ("87fe42cb3e3973d4", [4, 5, 6, 7, 34]),
    "nta-active-travel-2025": ("05c8f2e9cdd41579", [1, 3, 4, 30, 31, 73]),
    "nta-active-travel-2026": ("5ff8df0349faf01f", [3, 7, 21, 22, 23, 31, 36, 37, 58, 78, 79]),
}
out = {"note": "...", "documents": []}
for document_id, (digest, numbers) in pages.items():
    with pdfplumber.open(cache / f"{digest}.pdf") as pdf:
        out["documents"].append({"document_id": document_id, "pages": [
            {"page": n, "rows": [[normalise(c) for c in row]
                                 for row in (pdf.pages[n - 1].extract_table() or [])]}
            for n in numbers]})
print(json.dumps(out, indent=1, ensure_ascii=False))
```

The cache filename is the first 16 hex characters of the SHA-256 of the
document URL (see `allocations.cache_path`).

## The end-to-end test

`test_end_to_end.py` runs the whole chain over the cached documents and asserts
per-year record counts within 2% of the first clean run's baseline. It is
skipped when the PDFs or the public-body register
(`pipelines/foi_pipeline/steps/find_public_bodies/output.json`) are missing, so
a code-only clone still runs the rest of the suite.
