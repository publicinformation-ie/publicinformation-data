# reconcile_summary

Checks the extracted totals against the document's own per-recipient summary.

## The check

The 2025 and 2026 editions open with a table of one total per recipient
(`Agency`, `2025 AT Allocations`, and for 2026 a third `BSEP allocations`
column). Each of those totals is compared with the active-travel total the
project tables yielded for the same recipient — the first block's rows.

- **Match** — the section stands.
- **Mismatch** — the recipient's `active_travel` rows are withheld and a
  `SummaryMismatch` error names the recipient, the declared total and the
  extracted total. A different stream's rows are unaffected.
- **Summary lists a recipient with no project table** — reported as
  `SummaryMismatch` with the declared total and no extracted one. Nothing is
  withheld, because there is nothing to withhold: the dataset is missing a
  recipient the publisher says it allocated money to.

## What is skipped, and why

| Skipped | Reason |
|---|---|
| The 2022 Annex 1 (`programme_summary`) | It is a programme budget view — €289.0m across A3.1–A3.4 by GDA/regional/rural split — while the 2022 project tables total €387.8m. It is a different view of the money, not a control on the project rows, so comparing them would produce a permanent false failure. |
| 2023, 2024 | No per-recipient summary in the document. |
| The 2026 `BSEP allocations` column | A body-level allocation with no project-level counterpart in the table: it cannot be reconciled and is not published as a project allocation. |
| Aggregate summary lines (`Greater Dublin Area Sub-Total:`, `Others Sub- Total`, and the non-local-authority line) | They are sums over several table blocks and streams, not a recipient's total. The 2026 non-local-authority line (€6,390,000) is one of four subtotals in the table it summarises (€18,390,000), so a per-recipient comparison does not exist. |

Every skipped line is recorded in `summary_skipped` and every excluded summary
row (with its reason) in the step's output, so nothing disappears quietly.

## Output

`rows` (restricted to what may be published), `sections` (with the withheld
streams marked), `summary_comparisons` (one entry per compared recipient with
`declared_eur` and `extracted_eur`) and `summary_skipped`.

## Errors

`SummaryMismatch` — see above. Both sums are in the context, so the review is
"which is right, the summary or the rows?".
