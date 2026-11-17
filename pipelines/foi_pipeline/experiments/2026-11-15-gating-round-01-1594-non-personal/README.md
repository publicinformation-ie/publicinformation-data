# Gating round 1: body 1594, non-personal FOI requests 2017 to 2020

Cluster `1594-non-personal-2017-2020` (4 files, 567 recoverable records). See `diagnosis-input.md`.

## Hypothesis

**Fault kind: G (gate).** The four files fail only `role_contamination` under three different extractors,
with `date_received` contaminated at 0.99 to 1.0 while every row is anchored. The 2018 dump shows
`date_received` cells like `04-Jan-18` classified by `cell_kinds` as `reference`, not `date`.
`lib.value_kinds._is_date` reads numeric dd/mm/yyyy and `parse_date` deadline phrases, not `DD-Mon-YY`;
`_is_reference` then matches a single token with digits and `-`. The downstream normaliser already parses
`DD-Mon-YY` (`extract_disclosures_normalize_rows`), so the data is fine and the scorer is wrong.
This points away from an extractor fault (all extractors map column 1 correctly, only camelot_stream differs).

Side note: row 0 is a title row ("FOI Requests - 2018"), the true header is row 1; the header detector handles it.

## Competing fixes

`current`, `force:pdfplumber`, `force:pymupdf`, `force:camelot_lattice`, `force:camelot_stream`, `force:mistral_cache`,
`docling`, and `gate-dd-mon-yy` (round `fixes.py`; global scope, so it needs a full before/after over all bodies
before any shipping).

## Result and decision

| | |
|---|---|
| Winner | `gate-dd-mon-yy` (gate hypothesis, global scope) |
| Cluster files resolved | 4 of 4 (gate pass, agreement 0.99 with independent extractor family, cluster gold 1.0 on the 2018 file) |
| Records recoverable | 568 |
| Controls worse | 0 (10 controls; 0 differ) |
| Other fixes | all `force:*` and docling resolve 0 of 4; docling makes 2 controls worse |

Caveats: the cluster gold (sha `eeb9d0a7`) is a 20-row sample, still `provisional` (no gold-cell verdicts were
given, so it was not marked checked). A gate change is global: it still needs a full before/after over all bodies.

**User verdict (review page): ship = no. Superseded 2026-11-17: the user approved shipping this winner (PR #29).** Reasons recorded by the user:
- On three control files "current" is not correct, so a control cannot be assumed good just because the gate passes:
  body 1210 (`foi-requests-january-march-2024.pdf`, current = pymupdf) should take **docling**;
  body 1508 (Mayo `FOI-Disclosure-Log-Q3-2024.pdf`, current = camelot_stream) should take **force:pdfplumber**;
  body 1235 (Dublin City `disclosure-log-2025.pdf`, current = camelot_stream) should take **force:mistral_cache**.
  Fixes for those are separate routing work (clusters of kind E), not part of this gate change.
- 1210 file also tagged `split cells` (DRCD-FOI-2024-0018 split over 12 rows).
- Text-layer garbling in the source, present whatever the extractor: 2018 row 1309 (interleaved characters in the
  description) and 2020 record 1618 (date `2 7 - J a n -20`). Not fixed by this round; the gate fix does not touch it.

Recommendation: do not ship `gate-dd-mon-yy` yet. It is a recommendation only. Next: (1) a full before/after of the gate
over all bodies, (2) a new round for the three mis-extracted controls, (3) check how the 2020 `2 7 - J a n -20` garble
reaches the normaliser.
