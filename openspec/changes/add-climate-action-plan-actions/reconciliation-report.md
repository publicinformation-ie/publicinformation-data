# CAP annex reconciliation report (task 4)

Generated 2026-11-09 with `python -I scripts/reconcile_climate_action_plan_annexes.py /tmp/cap-sources/xlsx` against the extracted `resolve_action_identity` output (annex entries with `action_table_layout: [action_number_header, carry_header]`). XLSX rows belong to the edition named by their code year.

**Status: BLOCKED.** CAP23 has 4 missing references (below). CAP24 and CAP25 are clean. No `expected_action_count` is pinned.

| Edition | extracted | XLSX refs | matched | dash text = parent | missing | text mismatch | extra |
|---|---|---|---|---|---|---|---|
| climate-action-plan-2023-annex-of-actions | 441 | 254 | 185 | 61 | 4 | 4 | 191 |
| climate-action-plan-2024-annex-of-actions | 126 | 98 | 98 | 0 | 0 | 0 | 28 |
| climate-action-plan-2025-annex-of-actions | 82 | 82 | 82 | 0 | 0 | 0 | 0 |

## Blocking: missing references (CAP23)

- `BE/23/34/B`, `BE/23/34/C`, `BE/23/34/D` (PDF p.56, table 0): the continuation of the BE/23/34 table at the page break. The previous table (p.55) has 8 columns (an empty spacer column after Actions); this fragment has 7, with no spacer. `carry_header` requires the same column count (D7), so the fragment is logged as `UnreadActionTable` (page 56, table 0, first reference `BE/23/34/B`, 3 rows) and not extracted. Columns after Actions sit one index apart, so inheriting the header by index would misread them. Needs a design decision (column-offset carry), not a code tweak.
- `BE/23/38` (PDF p.57): the PDF prints this row's reference as `BE/23/36`, a duplicate of the row above. The XLSX (Q4 sheet) has it as `BE/23/38` with the same text (`Publish a review of relevant sources and a general training template ...`). The pipeline logs `DuplicateActionReference` and excludes the row. This is a source typo; fixing it needs an explicit per-document correction, which the design does not provide.

## Text mismatches (recorded reasons)

The PDF prints `-` in a sub-action's Actions cell (the text is the parent's). 61 of those rows match the XLSX, which repeats the parent text. The remaining 4:

- `AD/23/8/A`: PDF `-`; XLSX `Make TRANSLATE the national standard set of climate projections`. The XLSX text differs from the PDF parent row (abbreviation expanded or a different action's text), so the dash is not comparable.
- `AD/23/8/B`: PDF `-`; XLSX `Make TRANSLATE the national standard set of climate projections`. The XLSX text differs from the PDF parent row (abbreviation expanded or a different action's text), so the dash is not comparable.
- `PS/23/12/A`: PDF `-`; XLSX `Support implementation of Green Public Procurment (GPP) in public sector`. The XLSX text differs from the PDF parent row (abbreviation expanded or a different action's text), so the dash is not comparable.
- `PS/23/12/C`: PDF `-`; XLSX `Relevant bodies shall, where practicable, ensure private sector investment is consistent with the Go`. The XLSX text differs from the PDF parent row (abbreviation expanded or a different action's text), so the dash is not comparable.

## Extracted, in no XLSX (informational)

The XLSX workbooks are quarterly returns and legacy lists, not the whole annex.

- climate-action-plan-2023-annex-of-actions (191): AD/23/10, AD/23/12, AD/23/13, AD/23/17, AD/23/19, AD/25/1, AD/25/2, AG/23/13, AG/23/6, AG/24/1, AG/24/2, AG/24/2/A, BE/23/11, BE/23/15, BE/23/2, BE/23/20, BE/23/23, BE/23/26, BE/23/27, BE/23/28, BE/23/31, BE/23/31/A, BE/23/33, BE/23/33/A, BE/23/34, BE/23/35, BE/23/37, BE/23/5, BE/23/5/B, CE/23/10, CE/23/4, CE/23/5, CE/23/8, CP/23/12, CP/23/6/A, CP/23/8, CZ/23/1, CZ/23/10, CZ/23/11, CZ/23/2, CZ/23/3, CZ/23/3/C, CZ/23/5, CZ/23/6/A, CZ/23/6/B, CZ/23/6/C, CZ/23/7, CZ/23/8, CZ/23/8/A, CZ/23/8/B, CZ/23/8/C, CZ/23/8/D, CZ/23/8/E, CZ/23/8/F, CZ/23/8/G, CZ/23/8/H, EL/23/1, EL/23/10, EL/23/10/A, EL/23/10/B, EL/23/13, EL/23/14, EL/23/19, EL/23/21, EL/23/25, EL/23/28, EL/23/29, EL/23/30, EL/23/6, EL/23/6/A, EN/23/1, EN/23/10, EN/23/11, EN/23/13, EN/23/14, EN/23/8, GV/23/2, GV/23/2/A, GV/23/6, IC/23/2, JM/23/10, JM/23/2, JM/23/3, JM/23/4, JM/23/5, JM/23/6, JM/23/7, JM/23/8, JM/23/9, JT/23/3, JT/23/4, LU/23/18, LU/23/2, LU/23/7A, LU/25/1, MA/23/12, MA/23/13, MA/23/14, MA/23/15, MA/23/17, MA/23/6, MA/24/1, PS/23/1, PS/23/10, PS/23/12, PS/23/3, PS/23/5, PS/23/6, PS/23/7, PS/23/8, PS/23/9, PS/23/9/B, RE/23/10, RE/23/11, RE/23/13, RE/23/14, RE/23/2, RE/23/20, RE/23/3/A, RE/23/5, RE/23/7, RE/24/1, RE/24/2, RE/24/3, RE/25/1, TR/23/1, TR/23/10, TR/23/11, TR/23/12, TR/23/13, TR/23/14, TR/23/15, TR/23/16, TR/23/17, TR/23/18, TR/23/2, TR/23/20, TR/23/21, TR/23/22, TR/23/23, TR/23/24, TR/23/25, TR/23/26, TR/23/27, TR/23/28, TR/23/29, TR/23/3, TR/23/30, TR/23/31, TR/23/32, TR/23/33, TR/23/34, TR/23/35, TR/23/36, TR/23/37, TR/23/38, TR/23/39, TR/23/4, TR/23/40, TR/23/41, TR/23/42, TR/23/43, TR/23/44, TR/23/45, TR/23/47, TR/23/48, TR/23/49, TR/23/5, TR/23/50, TR/23/51, TR/23/52, TR/23/53, TR/23/54, TR/23/59, TR/23/6, TR/23/60, TR/23/64, TR/23/65, TR/23/67, TR/23/68, TR/23/69, TR/23/7, TR/23/70, TR/23/71, TR/23/72, TR/23/73, TR/23/74, TR/23/75, TR/23/76, TR/23/77, TR/23/8
- climate-action-plan-2024-annex-of-actions (28): BE/24/12, BE/24/13, BE/24/14, BE/24/15, BE/24/16, BE/24/18, BE/24/19, BE/24/2, BE/24/20, BE/24/3, BE/24/4, BE/24/5, BE/24/6, BE/24/7, IN/24/3, TR/24/1, TR/24/11, TR/24/12, TR/24/13, TR/24/14, TR/24/15, TR/24/16, TR/24/17, TR/24/18, TR/24/19, TR/24/20, TR/24/4, TR/24/9
- climate-action-plan-2025-annex-of-actions (0): 

## Other triage notes

- CAP23 `DuplicateActionReference` count: 1 (the BE/23/36 row above).
- CAP25: 62 rows excluded as `OutOfEditionReference` (legacy); 2 `UnresolvedActionNumber` on p.67 (blank Action Number cell). Neither is in the XLSX reference.
- `UnreadActionTable`: CAP23 1 (above), CAP24 0, CAP25 0.
