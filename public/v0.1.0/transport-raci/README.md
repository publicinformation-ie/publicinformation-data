# Transport RACI

Who is Responsible, Accountable, Consulted and Informed for local transport
activities and lifecycle stages, as compiled by PublicInformation.ie.

**This is analysis, not official data.** It is not a statement of any body's
legal duties and it is not legal advice. Every line carries its evidence so you
can check or challenge it.

## Scope

The assignments have been analysed for Meath County Council only. They may differ for other councils. Meath is in the Greater Dublin Area.

The activity and stage vocabulary is generic to Irish local authorities; only
the assignments are analysed for Meath.

## How to read a line

Each row is one activity × stage. A line names the parties for each role:

- **R** does the work.
- **A** owns the decision; there is at most one.
- **C** must be asked.
- **I** is told afterwards.

A row is `assessed` when at least one line exists for it, and `not assessed`
otherwise. "Not assessed" is a gap, not a finding that nobody is responsible.

Each assessed line carries a derived `no_local_authority_role` value. It is a
boolean with a null: in `transport-raci.json` it is `true`, `false` or `null`;
in `raci-wide.csv` the cell reads `true`, `false` or `unknown`, and the CSVW
metadata declares the column as boolean with `unknown` as its null value.

- `false`: the council's elected members or its Chief Executive and executive
  hold a role on the line.
- `true`: the line has an Accountable party and no council organ holds any
  role. That is a finding.
- `unknown` (`null` in JSON): the line has no Accountable party (for example
  an unverified line). Unknown means it is not established who is
  Accountable — not that the council has no role.

"The council" in a party label means the council named in the line's
`jurisdiction` column; for this version that is Meath County Council.

## Evidence levels

| Evidence | Plain meaning |
|---|---|
| `statute` | set by law |
| `source` | stated in official guidance or observed practice |
| `default-s149-4` | assumed by default (an executive function because it is not reserved to elected members) |
| `unverified` | not yet confirmed |

## Coverage

- 613 activity × stage rows.
- 184 rows assessed; 429 not assessed.
- 224 assessed lines.
- 35 roles awaiting review.

## Files

- [assignments.csv](assignments.csv) — one line per assessed assignment.
- [assignment-roles.csv](assignment-roles.csv) — one line per role, with the
  party URI.
- [assignment-sources.csv](assignment-sources.csv) — the sources for each line.
- [rows.csv](rows.csv) — every activity × stage row with its coverage state.
- [raci-wide.csv](raci-wide.csv) — a generated reading view, one line per
  assignment with readable party names and evidence. It is never edited.
- [transport-raci.json](transport-raci.json) — the same data nested by
  activity → stage → assignments, for programs and LLMs.
- [sources.csv](sources.csv), [variants.csv](variants.csv) and
  [boundary-rules.csv](boundary-rules.csv) — the cited sources, the variant
  labels and the boundary rules.
- [METHODOLOGY.md](METHODOLOGY.md) — how the model was built and what it means.

## Roles awaiting review

These roles are recorded in the working model but are not published yet. They
are listed here so the gap is visible.

- `RT-04.S10` (LA scheme, NTA-funded (e.g. SRTS, Active Travel)), role C: role not yet published: awaiting review (recorded value `GS`).
- `RT-04.S5` (LA scheme, NTA-funded (e.g. SRTS, Active Travel)), role C: role not yet published: awaiting review (recorded value `GS`).
- `RT-04.S7b` (s.38 route), role C: role not yet published: awaiting review (recorded value `GS`).
- `RT-06.S10` (LA scheme, NTA-funded (e.g. SRTS, Active Travel)), role C: role not yet published: awaiting review (recorded value `GS`).
- `RT-06.S5` (LA scheme, NTA-funded (e.g. SRTS, Active Travel)), role C: role not yet published: awaiting review (recorded value `GS`).
- `RT-06.S7b` (s.38 route), role C: role not yet published: awaiting review (recorded value `GS`).
- `RT-07.S10` (LA scheme, NTA-funded (e.g. SRTS, Active Travel)), role C: role not yet published: awaiting review (recorded value `GS`).
- `RT-07.S5` (LA scheme, NTA-funded (e.g. SRTS, Active Travel)), role C: role not yet published: awaiting review (recorded value `GS`).
- `RT-07.S7b` (s.38 route), role C: role not yet published: awaiting review (recorded value `GS`).
- `RT-09.S10` (LA scheme, NTA-funded (e.g. SRTS, Active Travel)), role C: role not yet published: awaiting review (recorded value `GS`).
- `RT-09.S5` (LA scheme, NTA-funded (e.g. SRTS, Active Travel)), role C: role not yet published: awaiting review (recorded value `GS`).
- `RT-09.S7b` (s.38 route), role C: role not yet published: awaiting review (recorded value `GS`).
- `RT-10.S13a`, role I: role not yet published: awaiting review (recorded value `GS`).
- `RT-10.S14`, role C: role not yet published: awaiting review (recorded value `GS`).
- `RT-14a.S10` (LA scheme, NTA-funded (e.g. SRTS, Active Travel)), role C: role not yet published: awaiting review (recorded value `GS`).
- `RT-14a.S13b`, role C: role not yet published: awaiting review (recorded value `GS`).
- `RT-14a.S5` (LA scheme, NTA-funded (e.g. SRTS, Active Travel)), role C: role not yet published: awaiting review (recorded value `GS`).
- `RT-14a.S7b` (s.38 route), role C: role not yet published: awaiting review (recorded value `GS`).
- `RT-26.S13a`, role C: role not yet published: awaiting review (recorded value `GS`).
- `RT-26.S14`, role C: role not yet published: awaiting review (recorded value `GS`).
- `RT-26.S14`, role R: role not yet published: awaiting review (recorded value `GS`).
- `RT-29.S10` (LA scheme, NTA-funded (e.g. SRTS, Active Travel)), role C: role not yet published: awaiting review (recorded value `GS`).
- `RT-29.S5` (LA scheme, NTA-funded (e.g. SRTS, Active Travel)), role C: role not yet published: awaiting review (recorded value `GS`).
- `RT-29.S7b` (s.38 route), role C: role not yet published: awaiting review (recorded value `GS`).
- `RT-36.S13b`, role C: role not yet published: awaiting review (recorded value `GS`).
- `RT-37.S11` (Council works), role C: role not yet published: awaiting review (recorded value `GS`).
- `RT-37.S11` (Event under s.75 order), role C: role not yet published: awaiting review (recorded value `GS`).
- `RT-37.S11` (Garda-run event closures (e.g. Slane 2026)), role R: role not yet published: awaiting review (recorded value `GS`).
- `RT-37.S13b` (s.75 closure order (works or events)), role C: role not yet published: awaiting review (recorded value `GS`).
- `RT-37.S14` (Offences), role R: role not yet published: awaiting review (recorded value `GS`).
- `RT-37.S15`, role C: role not yet published: awaiting review (recorded value `GS`).
- `RT-42.S10` (LA scheme, NTA-funded (e.g. SRTS, Active Travel)), role C: role not yet published: awaiting review (recorded value `GS`).
- `RT-42.S5` (LA scheme, NTA-funded (e.g. SRTS, Active Travel)), role C: role not yet published: awaiting review (recorded value `GS`).
- `RT-42.S7b` (s.38 route), role C: role not yet published: awaiting review (recorded value `GS`).
- `X-18.S13b`, role C: role not yet published: awaiting review (recorded value `GS`).

## Corrections

If a line is wrong, email dave@publicinformation.ie with the assignment ID (for example
`RT-09.S12`), the role and, where possible, the source that contradicts it.
This is the contact point in the dataset's catalogue record. Corrections are
reviewed and appear in a later version.

Licence: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
