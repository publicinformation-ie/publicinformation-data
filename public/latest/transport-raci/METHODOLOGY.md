# Methodology: the transport RACI

This dataset is **analysis compiled by PublicInformation.ie**. It is not
official data, not a statement of any body's legal duties, and not legal
advice. Every assignment is a judgement about who appears to decide or act,
recorded with the evidence behind it so a reader can check or challenge it.

## Scope

The assignments have been analysed for Meath County Council only. They may differ for other councils. Meath is in the Greater Dublin Area.

The activity and stage vocabulary is generic to Irish local authorities; only
the assignments are scoped to Meath.

## Why COFOG

The classification anchor is the United Nations' Classification of the
Functions of Government (COFOG) 1999, which PublicInformation.ie already
publishes as an open vocabulary. COFOG supplies the first three levels:
division (for example 04 Economic affairs), group (04.5 Transport) and class
(04.5.1 Road transport). The fourth level is project-defined and is not an
official COFOG level.

Transport activities outside 04.5 stay under their own COFOG function. Traffic
control and enforcement, pollution abatement, land-use planning, street
lighting, electricity supply and education are therefore cross-cutting
groupings that link to the relevant COFOG class rather than being forced into
transport.

The dataset never copies COFOG labels or hierarchy. It references a class by
its published URI, with a status of `confirmed` or `candidate`. A candidate
link is shown with `skos:related`, not `skos:broader`.

## Activity × stage

There is one row per **activity × lifecycle stage**. A row is not a project and
does not imply that a local authority has a duty. The activity catalogue
defines the function; the stages describe where in a lifecycle a decision or
task sits. The 20 stages are:

| ID | Stage |
|---|---|
| S1 | Policy and strategy |
| S2 | Network and investment planning |
| S3 | Allocation to project |
| S4 | Sponsorship and funding application |
| S5 | Appraisal and design |
| S5G | Gateway and acceptance decision |
| S6 | Environmental assessment, screening and exemption check |
| S7a | Statutory consent: local authority development |
| S7b | Statutory consent: road traffic works |
| S7c | Statutory consent: application or appeal to An Coimisiún Pleanála |
| S7D | Statutory determination |
| S8 | Land and rights acquisition |
| S9 | Procurement and contract award |
| S10 | Construction and implementation |
| S11 | Operation and service management |
| S12 | Maintenance and renewal |
| S13a | Rules and bye-laws |
| S13b | Licences, permits and orders |
| S14 | Enforcement |
| S15 | Monitoring, close-out and reporting |

An activity has only the stages that apply to it. The full row register is
generated from those links, never stored by hand. Retired and placeholder
activities are kept in the vocabulary for traceability but produce no rows.

## RACI

Each assessed row carries one role line per party:

- **R, Responsible** — does the work.
- **A, Accountable** — owns the decision or result. There is at most one.
- **C, Consulted** — must be asked before the decision or work.
- **I, Informed** — is told afterwards.

A row may have no Accountable party only when its evidence is `unverified` and
its note explains why. A party is never both Accountable and Consulted on the
same row. A category party (a contractor, delivery agent, operator or third
party) is never Accountable, except a third party delivering under a
permission, licence or order.

Rows with no assessment at all are published as **not assessed**. That is
different from an assessed row on which no council organ holds a role. The
second is a finding; the first is a gap.

## The two council organs

A local authority is not one party. The model separates:

- **the elected members** (`LA-M`), who exercise reserved functions such as
  Part 8 resolutions, bye-laws, special speed limits, taking-in-charge orders
  and the Schedule of Municipal District Works;
- **the Chief Executive and executive** (`LA-CE`), who exercise executive
  functions such as road traffic works, road opening licences, closure orders,
  procurement and maintenance.

Other parties are public bodies, linked to the `public-bodies` dataset where an
entry exists, or categories such as delivery agents, operators and third
parties.

## Evidence

Each assessed line says how confident the role is:

| Evidence | Plain meaning |
|---|---|
| `statute` | set by law |
| `source` | stated in official guidance or observed practice |
| `default-s149-4` | assumed by default (an executive function because it is not reserved to elected members) |
| `unverified` | not yet confirmed |

The evidence level belongs to the line, not to the dataset. A single row can
mix a statutory role with an unverified one.

## Boundary rules

These rules decide which stage a decision belongs to. They are published with
the data so a reader can follow the reasoning.

| Rule | Rule text |
|---|---|
| B1 | S8 holds the acquiring authority's actions; CPO confirmation goes to S7c. |
| B2 | Where several consent routes are possible, the route actually used decides the row (S7a, S7b or S7c). Exemption is recorded in S6, not S7. |
| B3 | An outline delivery plan prepared by a partner sits in S2 (R = partner, A = sponsor). |
| B4 | S5G holds pre-construction and acceptance decisions; funder close-out acceptance or verification sits in S15. |
| B5 | Stages may recur: a trial gives S10 → S15 → S7b; an operator withdrawal gives S15 → S9. |
| B6 | Programme envelopes and terms sit in X-17; S3 of an activity is allocation to a project (A = allocating body). |
| B7 | RT-36: compliance inspection and T5 acceptance sit in S14. |
| B8 | RT-37: s.75(2) offences and s.75(3) cost recovery and damage repair sit in S14. |
| B9 | A prior statutory consent from another body, without which a decision cannot be made, is its own S5G row (A = consenting body). |
| B10 | Like-for-like renewal funded as maintenance = S12; a funded upgrade or change of layout = a new S3–S10 cycle on the same activity. |
| B11 | Release of planning security = X-16.S5G. |
| B12 | Road works speed limit orders (s.10 RTA 2004, CE order) = RT-37.S13b; RT-24 holds bye-laws only. |
| B13 | Network-wide service planning = RT-17.S2; route design for TFI Local Link services = RT-19.S2. |
| B14 | Where a third party delivers works or arrangements under a permission, licence or order (developer works; licence holder's reinstatement; event organiser's traffic management plan), it is Accountable for that row in that variant. Contractors remain Responsible only. |

## How the model was tested

The stage and boundary model was tested against **14 scenarios** covering
schemes, maintenance, consent routes, bus, rail, ports, aviation, parking,
micro-mobility, enforcement and taking estates in charge. The scenarios are not
published: they were working tests of the model, not evidence about Meath. Where
a scenario exposed an ambiguity, the model was changed (for example, splitting
consent into S7a, S7b, S7c and S7D, and separating programme funding into
X-17), and the rows were regenerated.

A test result is not a role assignment. The assignments come from the cited
sources and are limited to what those sources support. Where the sources did
not settle a question, the line is `unverified` and its note says what is
missing. Some roles are still awaiting review and are not published.

## Coverage, gaps and corrections

Coverage is stated honestly for every row. Many activities are not assessed.
Rail services, aviation, ports, parking and some enforcement rows are largely
gaps, not findings of "nobody". The README lists every role that is still
awaiting review.

If you find an error, please report it through the contact route on
PublicInformation.ie and cite the row ID (for example `RT-09.S12`), the role
and, where possible, the source that contradicts the line. Corrections are
reviewed and appear in a later version; published URIs do not change.
