# Agreement calibration

Independent pairs with a defined agreement: 113
Lowest safe threshold (0.80-0.99): None
Violations at 0.90 (agreement >= 0.90, min gold < 0.9): 7

settings.json stays at 0.90; any change is the user's decision.

| sha | fix_a | fix_b | agreement | gold_a | gold_b |
|---|---|---|---|---|---|
| 6ab587f2 | current | force:pymupdf | 1.000 | 0.875 | 0.875 |
| 6ab587f2 | force:pdfplumber | force:pymupdf | 1.000 | 0.875 | 0.875 |
| 6ab587f2 | force:mistral_cache | docling | 0.998 | 0.731 | 1.000 |
| 494a788e | current | force:pymupdf | 1.000 | 0.978 | 0.222 |
| 494a788e | force:camelot_lattice | force:pymupdf | 1.000 | 0.978 | 0.222 |
| 494a788e | force:pymupdf | force:mistral_cache | 1.000 | 0.222 | 0.978 |
| 494a788e | force:pymupdf | docling | 1.000 | 0.222 | 0.978 |

