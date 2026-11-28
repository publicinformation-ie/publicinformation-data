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

Evidence is recorded per line. Where a ruling gives a role its own evidence, the
role carries that instead. This happens when the role rests on different
sources from the rest of the line, for example a Garda consultation role that is
stated in official guidance on a line that is otherwise assumed by default.
`assignment-roles.csv` and `transport-raci.json` give the evidence of every
role. In `raci-wide.csv` a role whose evidence differs from its line's is
marked after its name, for example "An Garda Síochána (stated in official
guidance or observed practice)".

## Coverage

- 613 activity × stage rows.
- 184 rows assessed; 429 not assessed.
- 224 assessed lines.
- 5 roles awaiting review.
- 34 roles with evidence of their own.

## Files

- [assignments.csv](assignments.csv) — one line per assessed assignment.
- [assignment-roles.csv](assignment-roles.csv) — one line per role, with the
  party URI and the evidence for that role.
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

- `RT-10.S14`, role C: role not yet published: awaiting review (recorded value `GS`).
- `RT-26.S14`, role C: role not yet published: awaiting review (recorded value `GS`).
- `RT-37.S11` (Garda-run event closures (e.g. Slane 2026)), role R: role not yet published: awaiting review (recorded value `GS`).
- `RT-37.S14` (Offences), role R: role not yet published: awaiting review (recorded value `GS`).
- `RT-37.S15`, role C: role not yet published: awaiting review (recorded value `GS`).

## Other items awaiting review

- None.

## Decisions on the source material

These ambiguities in the source were reviewed and left as they are. Each one is
recorded in `review_decisions.csv`.

- Variant labels `NTA-delivered (BusConnects) | NTA-delivered (BusConnects, GDA)`: kept separate. The two GDA lines record a separate open question (Ministerial approval of the GDA Strategy), and RT-17 appears only under the GDA variant.
- Variant labels `Royal Canal Greenway | Royal Canal Greenway (Waterways Ireland land)`: kept separate. The Waterways Ireland variant records a different landowner question; the plain line never carried that note.
- `X-07`, the register's grouping `X5 / RT1-RT4`: kept on X5. A charge point is an electricity supply asset before it is a road asset; the register already marks its COFOG placement as a candidate, and the ambiguity is noted in the activity.

## Corrections to the source analysis

These facts were corrected after the original analysis was compiled. Each one
is listed with its reason and its evidence.

- activity `X-18`, definition. Part XVI of the Planning and Development Act 2000, including s.230, was repealed on 9 September 2026 and event licences are now granted under s.479 of the 2024 Act and S.I. 468 of 2026. Evidence: set by law; sources P11, P12, P13.
- assignment `X-18.S13b`, note. Part XVI of the Planning and Development Act 2000, including s.230, was repealed on 9 September 2026 and event licences are now granted under s.479 of the 2024 Act and S.I. 468 of 2026. Evidence: set by law; sources P11, P12, P13.
- source `S153`, citation. The Meath page cites s.230 of the 2000 Act, which S.I. 466 of 2026 repealed with effect from 9 September 2026. Evidence: set by law; sources P13.
- assignment `RT-37.S14~offences`, party `LA-CE`: role changed from C to R. Section 81(3)(a) of the Roads Act 1993 says a summary offence under the Act "may be prosecuted by the road authority concerned" and the s.75(2) offences are summary offences, so the council executive carries out the enforcement. Evidence: set by law; sources P10.

## Corrections

If a line is wrong, email dave@publicinformation.ie with the assignment ID (for example
`RT-09.S12`), the role and, where possible, the source that contradicts it.
This is the contact point in the dataset's catalogue record. Corrections are
reviewed and appear in a later version.

Licence: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
