---
name: transport-governance
description: "Use when determining who does what in Irish local transport: which body plans, funds, specifies, consents, delivers, operates, maintains, regulates or enforces a transport activity, or when writing public copy about who decides a transport matter."
---

# Transport governance

Answers a "who does what" question about local transport from PublicInformation.ie's
published transport RACI dataset. The dataset holds every assignment. This file only says
how to find the line, what to say about it, and what not to claim.

## What to read

Read the dataset, not a copy of it:

- `public/latest/transport-raci/raci-wide.csv` — one line per assignment: `activity_id`,
  `stage_id`, `variant`, `evidence`, and plain party names in the `R`, `A`, `C` and `I`
  columns. This is the answer table.
- `public/latest/transport-raci/rows.csv` — every activity × stage row with its `coverage`
  (`assessed` or `not assessed`) and `assessed_lines`. Read it when the answer is a gap.
- `public/latest/transport-raci/README.md` — scope, how to read a line, the evidence
  levels, and the roles still awaiting review.
- `public/latest/transport-raci/transport-raci.json` — the same data nested by activity,
  for walking a whole activity.
- `public/vocabularies/transport-activity.md`, `transport-stage.md`,
  `transport-raci-party.md` and `raci-evidence-level.md` — the terms.
- `vocabulary.md` (this directory) — only the question vocabulary the dataset does not
  publish: the words a question arrives in and the words an answer must avoid.
- `checks.md` (this directory) — the validation question set. Read it only to validate or
  change the skill.

Never copy an assignment into this skill or into a second table. A change to the dataset
must change the answer without editing the skill.

## Route the question

1. Name the **activity** from the transport-activity vocabulary. `vocabulary.md` maps the
   words a lay question uses ("bus lane", "Part 8", "taking in charge") to an activity or a
   stage. A question can match more than one activity; keep every row that applies.
2. Name the **stage** from the transport-stage vocabulary: `S1` policy, `S2` network and
   investment planning, `S3` allocation to project, `S4` sponsorship, `S5` appraisal and
   design, `S5G` gateway or acceptance decision, `S6` environmental assessment, `S7a`/`S7b`/
   `S7c` statutory consent, `S7D` statutory determination, `S8` land and rights, `S9`
   procurement, `S10` construction, `S11` operation, `S12` maintenance and renewal, `S13a`
   rules and bye-laws, `S13b` licences and orders, `S14` enforcement, `S15` monitoring and
   close-out.
3. Name the **variant** where the activity records one for the case asked about, for example
   `NTA-delivered (BusConnects)` for a bus lane, `Part 8 route` against `s.38 route` for a
   consent, `NTA scheme (TFI Bikes)` against `LA scheme` for shared bikes, or
   `National managed roads` against `Other national roads` for a speed limit. The variant
   states which case the line was analysed for; do not answer from one variant's line
   without saying that you used it.
4. Look the row up in `raci-wide.csv` by `activity_id`, `stage_id` and variant. If the row
   has no assessed line, `rows.csv` says `not assessed`.
5. Say the activity, stage and variant you used, in plain words, before the parties.

## Answer rules

**Roles.** `A` is the body that owns the decision (at most one per line); `R` does the work;
`C` must be asked before the decision; `I` is told afterwards. Name parties in the plain
names the dataset publishes, not internal IDs. A party label reading "the council" means
the jurisdiction named on the line.

**Evidence.** Every line carries an evidence level, and every answer states it: `set by law`
(statute), `stated in official guidance or observed practice` (source), `assumed by default
(an executive function because it is not reserved to elected members)` (default-s149-4), or
`not yet confirmed` (unverified). Never describe a guidance-backed or default-backed role as
a statutory duty.

**Roles awaiting review.** The README lists lines whose `R`, `C` or `I` is recorded but not
published. Where the question touches one, say the role is not published yet rather than
naming a party or inferring one.

**Coverage.** The assignments were analysed for **Meath County Council** only and may differ
for another council. For a question about another council, give the answer the model
supports and say it was analysed for Meath and may differ there. Do not refuse, and do not
present the Meath line as the other council's.

**Gaps.** Where the matching row is `not assessed`, or no activity in the dataset covers the
question (for example school bus services), say that the dataset does not assess it. Never
infer a role from a neighbouring activity, stage or council, and never say that nobody is
responsible: a gap is not a finding.

**What this is.** Present the dataset as PublicInformation.ie's analysis, not as an official
statement of any body's duties and not as legal advice. On the first governance answer in a
conversation, say that each line carries its evidence so it can be checked or challenged.

**Public copy.** When writing for the public, use the plain party names the vocabularies
publish. Do not put assignment, activity or stage IDs into public copy, and apply the banned
terms in `vocabulary.md`.

## Working example

Question: "Who approves a footpath scheme on a housing estate road?"

- Activity `RT-06` *Construct and maintain footpaths and pedestrian routes*.
- Stage `S7a` *Statutory consent: LA development*, variant `Part 8 route`.
- Answer: the elected members of Meath County Council are Accountable; the Chief Executive
  and executive carry out the work; prescribed bodies and third parties are consulted.
  Evidence: set by law.

The same works consented under s.38 sit on stage `S7b`, variant `s.38 route`, where the
Chief Executive is Accountable. Naming the consent route is part of the answer.
