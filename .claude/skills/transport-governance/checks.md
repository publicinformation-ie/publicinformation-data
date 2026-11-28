# Transport governance checks

Read only when validating or changing the skill. Each question expects one or more
published assignment lines: the assignment ID, the role that is Accountable and the role
that is Responsible, plus the line's evidence level. Every expected assignment ID must
exist in `public/latest/transport-raci/raci-wide.csv`; `tests/test_transport_governance_skill.py`
checks that.

## Procedure

1. Copy `SKILL.md` and `vocabulary.md` (not this file) to an empty scratch directory. Give
   the fresh agent a read-only pointer to the published dataset and vocabularies
   (`public/latest/transport-raci/` and `public/vocabularies/` in the repository).
2. Give it only that material and the Question column below. It answers with the activity,
   stage and variant it used, the `A` and `R` parties, and the line's evidence level.
3. Compare each answer with Expected. Resolve every miss as either a dataset gap (raise it
   for a dataset change) or a wrong expectation (fix this file), and record it in the
   Validation log.
4. In the same pass, run the banned-term grep over `SKILL.md` and `vocabulary.md`, and check
   that neither file carries an assignment ID.

## Questions

| # | Question | Expected | Evidence | Covers |
|---|---|---|---|---|
| 1 | Who maintains a regional or local road? | `RT-02.S12` → A: the Chief Executive and executive of Meath County Council; R: the Chief Executive and executive of Meath County Council and delivery agents | set by law | regional and local roads |
| 2 | Who maintains the N3 national road near Navan? | `RT-01.S12` is `not assessed`: say the dataset does not assess national road maintenance, and do not name a party | not assessed | trap: national vs regional roads |
| 3 | Who approves the yearly schedule of municipal district works? | `RT-02.S2` → A: the elected members of Meath County Council; R: the Chief Executive and executive | set by law | reserved function |
| 4 | Who approves a footpath scheme that goes through Part 8? | `RT-06.S7a~part-8-route` → A: the elected members of Meath County Council; R: the Chief Executive and executive | set by law | trap: Part 8 |
| 5 | The same footpath works are consented under s.38 instead. Who approves them? | `RT-06.S7b~s38-route` → A: the Chief Executive and executive of Meath County Council; R: the Chief Executive and executive | assumed by default (an executive function) | trap: s.38 against Part 8 |
| 6 | Who makes the parking bye-laws for a town? | `RT-24.S13a` → A: the elected members of Meath County Council; R: the Chief Executive and executive | set by law | kerbside parking |
| 7 | Who sets the special speed limit on a national managed road? | `RT-25.S13a~national-managed-roads` → A: Transport Infrastructure Ireland; R: Transport Infrastructure Ireland | set by law | national roads |
| 8 | Who sets the special speed limit on another national road? | `RT-25.S13a~other-national-roads` → A: the elected members of Meath County Council; R: the Chief Executive and executive | set by law | trap: national vs regional roads |
| 9 | Who enforces the speed limit? | `X-02.S14~speed-limits` → A: the Gardaí; R: the Gardaí | stated in official guidance or observed practice | enforcement |
| 10 | Who enforces the rules on a greenway? | `RT-10.S14` → A: the Chief Executive and executive of Meath County Council; R: the Chief Executive and executive | stated in official guidance or observed practice | greenway enforcement |
| 11 | Who makes the bye-laws for shared e-scooter hire? | `RT-26.S13a` → A: the elected members of Meath County Council; R: the Chief Executive and executive | set by law | shared micromobility |
| 12 | Who issues the operator licence under those bye-laws? | `RT-26.S13b` → A: the Chief Executive and executive of Meath County Council; R: the Chief Executive and executive | assumed by default (an executive function) | rules against licences |
| 13 | Who decides whether a school bus service is provided? | No activity covers school bus services. `X-03.S11` and `X-10.S11` are `not assessed`: report the gap, and do not name a party | not assessed | trap: school transport, deliberate gap |
| 14 | Who delivers a new bus lane in Kildare? | `RT-13.S10~nta-delivered-busconnects` → A: the National Transport Authority; R: the National Transport Authority and delivery agents; say it was analysed for Meath and may differ in Kildare | set by law | variant, other council |
| 15 | Who decides that a housing estate's roads are taken in charge? | `RT-38.S7D` → A: the elected members of Meath County Council (the municipal district members in Meath); R: the Chief Executive and executive | set by law | taking in charge |
| 16 | Who issues a road opening licence? | `RT-36.S13b` → A: the Chief Executive and executive of Meath County Council; R: the Chief Executive and executive | assumed by default (an executive function) | road works by others |
| 17 | Write one sentence of public copy saying who decides where parking is allowed on a street. | Plain party names only: the elected members make the bye-laws, the Chief Executive and staff apply them. No assignment, activity or stage ID, and no banned term | n/a | public register |

## Validation log

| Date | # | Answer given | Resolution |
|---|---|---|---|
| 2026-11-28 | all | Question set rewritten against the transport RACI dataset v0.1.0 after the GDA model was retired. Every expected assignment ID was checked against `raci-wide.csv` by `tests/test_transport_governance_skill.py`. | No fresh-agent run yet; the previous run (2026-10-14) tested the retired model and is not comparable. |
