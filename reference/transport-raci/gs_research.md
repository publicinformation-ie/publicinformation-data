# GS cell research: recommended rulings

Status: **ruled by Dave, 28 November 2026.** The recommendations below are
recorded in `migration_resolutions.csv` and published, except the five cells
left unresolved (see the summary table). The master tables and generated
outputs are now built from those rulings.
Researched 2026-11-28. Ruling values use the `migration_resolutions.csv` format (party ids
separated by `; `).

Scope: the 35 `GS` cells in `migration_errors.json`. Dave's earlier rulings (`X-02.S14` → `AGS`;
speed-limit C cells → `RSA; AGS`) are not re-opened and nothing below conflicts with them.

Confidence labels:

- **statute**: the operative words are in an Act or statutory instrument.
- **guidance**: ministerial, NTA, TII or DoT guidance or standard. It is not binding on the point.
- **inferred**: analogy or a general function. No source names the role for this activity and stage.

## 1. Summary table

Role-letter flag (**RL**): the cited source supports the party but not the role letter on the
cell (for example it supports "notified" where the cell says C). See open questions Q1 and Q3.

| # | error_key | Recommendation | Confidence | Provision (short) |
|--:|---|---|---|---|
| 1 | `RT-04.S7b\|s.38 route\|C\|GS` | `AGS` | statute (conditional), guidance. RL | s.95(3)(b) RTA 1961; s.38(3) RTA 1994 (not operative); Traffic Works Guidelines 2023 |
| 2 | `RT-06.S7b\|s.38 route\|C\|GS` | `AGS` | statute (conditional), guidance. RL | same as 1 |
| 3 | `RT-07.S7b\|s.38 route\|C\|GS` | `AGS` | statute (conditional), guidance. RL | same as 1 |
| 4 | `RT-09.S7b\|s.38 route\|C\|GS` | `AGS` | statute (conditional), guidance. RL | same as 1 |
| 5 | `RT-14a.S7b\|s.38 route\|C\|GS` | `AGS` | statute (conditional), guidance. RL | same as 1 |
| 6 | `RT-29.S7b\|s.38 route\|C\|GS` | `AGS` | statute (conditional), guidance. RL | same as 1 |
| 7 | `RT-42.S7b\|s.38 route\|C\|GS` | `AGS` | statute (conditional), guidance. RL | same as 1 |
| 8 | `RT-04.S5\|LA scheme, NTA-funded (e.g. SRTS, Active Travel)\|C\|GS` | `AGS` | guidance | Traffic Management Guidelines §3.3 |
| 9 | `RT-06.S5\|LA scheme, NTA-funded (e.g. SRTS, Active Travel)\|C\|GS` | `AGS` | guidance | same as 8 |
| 10 | `RT-07.S5\|LA scheme, NTA-funded (e.g. SRTS, Active Travel)\|C\|GS` | `AGS` | guidance | same as 8 |
| 11 | `RT-09.S5\|LA scheme, NTA-funded (e.g. SRTS, Active Travel)\|C\|GS` | `AGS` | guidance | same as 8 |
| 12 | `RT-14a.S5\|LA scheme, NTA-funded (e.g. SRTS, Active Travel)\|C\|GS` | `AGS` | guidance | same as 8 |
| 13 | `RT-29.S5\|LA scheme, NTA-funded (e.g. SRTS, Active Travel)\|C\|GS` | `AGS` | guidance | same as 8 |
| 14 | `RT-42.S5\|LA scheme, NTA-funded (e.g. SRTS, Active Travel)\|C\|GS` | `AGS` | guidance | same as 8 |
| 15 | `RT-04.S10\|LA scheme, NTA-funded (e.g. SRTS, Active Travel)\|C\|GS` | `AGS` | guidance | Traffic Signs Manual ch.8 §8.1.3.7; TII GE-STY-01024 §2 |
| 16 | `RT-06.S10\|LA scheme, NTA-funded (e.g. SRTS, Active Travel)\|C\|GS` | `AGS` | guidance | same as 15 |
| 17 | `RT-07.S10\|LA scheme, NTA-funded (e.g. SRTS, Active Travel)\|C\|GS` | `AGS` | guidance | same as 15 |
| 18 | `RT-09.S10\|LA scheme, NTA-funded (e.g. SRTS, Active Travel)\|C\|GS` | `AGS` | guidance | same as 15 |
| 19 | `RT-14a.S10\|LA scheme, NTA-funded (e.g. SRTS, Active Travel)\|C\|GS` | `AGS` | guidance | same as 15 |
| 20 | `RT-29.S10\|LA scheme, NTA-funded (e.g. SRTS, Active Travel)\|C\|GS` | `AGS` | guidance | same as 15 |
| 21 | `RT-42.S10\|LA scheme, NTA-funded (e.g. SRTS, Active Travel)\|C\|GS` | `AGS` | guidance | same as 15 |
| 22 | `RT-10.S13a\|-\|I\|GS` | `AGS` | **statute** | LGA 2001 s.200(3); S.I. 362/2006 art.4(b) |
| 23 | `RT-10.S14\|-\|C\|GS` | `UNRESOLVED — no evidence found` (as a *consultee*) | n/a | LGA 2001 s.204 supports AGS as an enforcer (R-type). See Q3 |
| 24 | `RT-14a.S13b\|-\|C\|GS` | `AGS` | guidance | NTA Guidance on Bus Stop Locations in Rural Areas (Oct 2016) §4.3.1. No statutory Garda role: s.85 RTA 1961 (as substituted by s.16 RTA 2002) |
| 25 | `RT-26.S13a\|-\|C\|GS` | `RSA; AGS` | guidance | DoT Advice Note: Shared Micromobility Services §6.1, §6.7 |
| 26 | `RT-26.S14\|-\|R\|GS` | `AGS` | **statute** | LGA 2001 s.204(1), (3)(d); S.I. 362/2006 art.8; GS Act 2005 s.7(1)(g) |
| 27 | `RT-26.S14\|-\|C\|GS` | `UNRESOLVED — no evidence found` | n/a | See Q3 |
| 28 | `RT-36.S13b\|-\|C\|GS` | `AGS` | guidance | Purple Book (2017) §3.4.2, §3.4.3, §5.2.4; Traffic Signs Manual ch.8 §8.1.3.7 |
| 29 | `RT-37.S11\|Council works\|C\|GS` | `AGS` | guidance | Traffic Signs Manual ch.8 §8.1.3.7, §8.4.4.17, §8.4.4.31 |
| 30 | `RT-37.S11\|Event under s.75 order\|C\|GS` | `AGS` | guidance | Meath events page; Roads Regs 1994 art.12 (notice). RL |
| 31 | `RT-37.S11\|Garda-run event closures (e.g. Slane 2026)\|R\|GS` | `AGS` | inferred | Garda traffic management plan (Slane 2026). Legal basis unverified |
| 32 | `RT-37.S13b\|s.75 closure order (works or events)\|C\|GS` | `AGS` | guidance. **RL: statute gives notice only** | Roads Regs 1994 art.12; Purple Book §3.4.2 |
| 33 | `RT-37.S14\|Offences\|R\|GS` | `AGS` | inferred. **Conflicts with current `C=LA-CE`** | GS Act 2005 s.7(1)(g); Roads Act 1993 s.81(3)(a) |
| 34 | `RT-37.S15\|-\|C\|GS` | `UNRESOLVED — no evidence found` | n/a | Nothing found |
| 35 | `X-18.S13b\|-\|C\|GS` | `AGS` | **statute** | S.I. 468/2026 regs 2, 9(1), 15; PDA 2024 s.479(3)(h) |

### Counts by recommendation type

| Recommendation | Cells |
|---|--:|
| `AGS` | 31 |
| `RSA; AGS` | 1 |
| `UNRESOLVED — no evidence found` | 3 |
| `REMOVE` | 0 |
| **Total** | **35** |

By confidence: statute 3 (rows 22, 26, 35); statute (conditional) plus guidance 7 (the S7b
rows); guidance 20; inferred 2 (rows 31, 33); unresolved 3.

No recommended value needs a new party id. `AGS` and `RSA` are both in `parties.csv`. An optional
follow-up for X-18 would need an `HSE` party (see Q6).

## 2. Legal bases

### 2.1 S7b "s.38 route" (rows 1 to 7)

**s.38 RTA 1994: Garda consultation is NOT currently operative.**
<https://www.irishstatutebook.ie/eli/1994/act/7/section/38> and
<https://revisedacts.lawreform.ie/eli/1994/act/7/section/38/revised/en/html>

> s.38(3) "Before providing or removing traffic calming measures under this section **of such
> class or classes as may be prescribed**, a road authority shall— (a) consult with the
> Commissioner; (b) publish a notice … (c) consider any observations made by the Commissioner …"

The duty applies only to classes "as may be prescribed". The Department of Transport's *Guidelines
on Traffic Works Procedures* (s.38(6) guidelines, October 2023), §4 "Prescribed Measures":
<https://assets.gov.ie/273747/752924fd-da41-4c49-a8d1-dd669275d309.pdf>

> "As at the date of these Guidelines, **no traffic calming measures have been prescribed by
> regulation** and, accordingly, the requirements set out in subsections 3(a), 3(b) and 3(c) are
> not mandatory and the associated requirement in subsection (4) is not applicable and is not in
> operation."

TII standards DN-GEO-03084 and DN-STY-03060 say the same ("Since the Minister has not as yet
prescribed such class or classes there is no current legal obligation to comply with the
consultation …"). The Traffic Management Guidelines §3.2 say the same (see 2.2). I found no
statutory instrument prescribing a class since October 2023, but that is an absence of evidence
(see Q2).

s.38 has no other Garda duty. s.38(5) gives the *National Roads Authority (now TII)* a
prior-consent power on national roads, not the Gardaí.

**s.95(3)(b) RTA 1961: Garda consultation on regulatory signs IS statutory.**
<https://revisedacts.lawreform.ie/eli/1961/act/24/section/95/revised/en/html>

> "(3)(b) A road authority may, after consultation with the Commissioner, provide in respect of
> public roads in their charge, other than national managed roads, such regulatory signs as they
> consider desirable."

The 2023 Traffic Works Guidelines §7 say that where a s.38 scheme includes traffic signs, s.95 must
also be followed ("It is insufficient to rely solely upon Section 38 powers for the provision of
regulatory signs"). The Traffic Management Guidelines §3.2 say "If traffic calming measures
include the provision of regulatory signs, then the normal requirement of consulting the Garda
Commissioner in respect of such signs, must be followed."

**Trial schemes (guidance).** Traffic Works Guidelines §9.2.3: "The local authority should consult
with An Garda Síochána and, in the case of schemes where the direction of general traffic movement
on a road is proposed to be changed or restricted, the fire service and the ambulance service."

**RSA:** no source gives the RSA any role in the s.38 route.

**Recommendation:** `AGS` on all seven cells. The statutory duty is conditional on the scheme
including regulatory signs. Otherwise the basis is guidance. The existing assignment note "Garda
consultation is statutory" is overstated. See Q2.

### 2.2 S5 appraisal and design (rows 8 to 14)

Traffic Management Guidelines, chapter 3 (Consultation), §3.3 "Who to consult". Extract hosted at
<https://www.roadguidelines.ie/wp-content/uploads/2025/05/Traffic-Management-Guidelines.pdf>
(the extract carries no date and refers to the NRA and the DTO):

> list item "3. An Garda Siochana/Garda Commissioner" … "In addition to any statutory
> requirements it is recommended that groups 1 to 5 [which include the Gardaí] be consulted on all
> traffic management schemes."

Chapter 2.3 (Road Safety Audit): "An Garda Siochana should be involved in the stage 3 audit and
earlier if resources allow."

The NTA Project Approval Guidelines (March 2024, already cited as S7) name neither the Gardaí nor
the RSA at the design stage. Their only road-safety reference is §11.3, a Stage 4 Road Safety
Audit "(if applicable)".

**RSA:** The RSA does not carry out road safety audits. Audits are done by an audit team
independent of the designer. For national roads, TII approves the auditors. The RSA Act 2006 gives
the RSA no consultee role in local schemes. Its relevant functions are s.4/s.5 (general road-safety
promotion, "co-operation with local authorities"). So nothing supports `RSA` at S5 or S10.

**Recommendation:** `AGS`, guidance. The guidance is old and is not NTA-specific. See Q4.

### 2.3 S10 construction and implementation (rows 15 to 21)

Traffic Signs Manual ch.8, *Temporary Traffic Measures and Signs for Roadworks* (Aug 2019):
<https://roadguidelines.ie/wp-content/uploads/2025/10/TSM-2019-Ch-8-Approved-Version-August-19-Online.pdf>

> §8.1.3.7 "The Road Authority has overall responsibility for the construction and maintenance of a
> public road. An Garda Síochána is the traffic authority, with responsibilities for matters
> relating to the control of traffic. Therefore, they should be consulted before TTM is deployed."
> §8.4.4.17 "An Garda Síochána must be consulted prior to the implementation of Stop and Go
> traffic control." §8.4.4.31 "… prior to the implementation of temporary traffic signals."

TII GE-STY-01024 *Road Safety Audit* (May 2025), §2:
<https://cdn.tii.ie/publications/GE-STY-01024-09.pdf>

> "The Client is responsible for ensuring that representatives of An Garda Síochána and those
> responsible for network management are invited to attend the Stage 3 and Stage 4 site visits …"

This standard applies to National Road Schemes. For others "where this Standard is being applied"
the overseeing organisation is the road authority. Its use on NTA-funded local schemes is by
adoption, so it is supporting guidance only.

**Recommendation:** `AGS`, guidance. The TSM §8.1.3.7 basis applies to any road works.

### 2.4 Greenway bye-laws (rows 22, 23)

LGA 2001 Part 19, <https://revisedacts.lawreform.ie/eli/2001/act/37/section/204/revised/en/html>
(also s.199, 200, 205, 206 on the same site).

> s.204(1) "'authorised person' means a person authorised in writing by a local authority for the
> purpose of this section **or, except in the case of subsection (4), a member of the Garda
> Síochána**." s.204(3)(d) "Where a member of the Garda Síochána is of the opinion that a person is
> committing or has committed an offence to which this section or section 205 relates, that member
> may arrest the person without warrant."

S.I. 362/2006 (LGA 2001 (Bye-Laws) Regulations 2006),
<https://www.irishstatutebook.ie/eli/2006/si/362/made/en/print>:

> art.4(b) A local authority shall, on publishing the s.200(1) notice, send a copy of the notice
> and draft bye-law "to each Superintendent of the Garda Síochána in whose district the bye-law
> would have application".
> art.8 "A fixed payment notice under section 206 shall be signed on behalf of the local authority
> concerned by an 'authorised person' within the meaning of section 204(1)."

- **Row 22 (RT-10.S13a, I):** art.4(b) is a notification duty. That matches **Informed** exactly.
  `AGS`, statute.
- **Row 23 (RT-10.S14, C):** the statute makes the Gardaí an *enforcer* (authorised person, power
  of arrest). It does not make them a consultee. No source was found for a consultee at
  enforcement. Recommend **UNRESOLVED** for the C cell. See Q3.

The Cork dog-control bye-law in S88 is a third-party copy of a draft and adds nothing on this
point.

### 2.5 Bus stop location approval (row 24)

s.85 RTA 1961 as substituted by s.16 RTA 2002 (commenced 1 Feb 2013 by S.I. 12/2013, which is a
commencement order):
<https://www.irishstatutebook.ie/eli/2002/act/12/section/16/enacted/en/html>

> s.85(3) "…the authority may, if it so thinks fit, **after consultation with the person** [the bus
> operator], give a direction specifying such points for stopping places …"

The statute names the operator only. NTA bus stops page (already S60):
"Section 16 transfers the responsibilities for the location of bus stops from An Garda Síochána to
the Local Authorities." So there is **no statutory Garda role**. The guidance still has one. NTA,
*Guidance on Bus Stop Locations in Rural Areas* (Version 1, Oct 2016), §4.3.1:
<https://nationaltransport.ie/wp-content/uploads/2016/11/Guidance_on_Bus_Stop_Locations_in_Rural_Areas.pdf>

> "the road authority should consult with An Garda Síochána regarding any specific incidents they
> are aware of, or concerns or problems that they may have with the stop location."

**Recommendation:** `AGS`, guidance. I did not recommend REMOVE: the statute names one consultee,
not a closed list, and the NTA guidance positively names the Gardaí. If Dave wants a statute-only
standard, the alternative is REMOVE on the statute's silence. The guidance is for rural areas.

### 2.6 Shared micromobility (rows 25 to 27)

DoT, *Shared Micromobility Services: Advice Note for Local Authorities* (2024):
<https://www.gov.ie/en/department-of-transport/publications/advice-note-for-local-authorities-shared-micromobility-services>
(PDF <https://assets.gov.ie/295764/73994291-8e51-405a-9c50-39eec18efb23.pdf>)

> §6.1 "…strong links with the Road Safety Authority and An Garda Síochána in respect of safety
> aspects…"
> market engagement list item (d) "Close cooperation with the Road Safety Authority and An Garda
> Síochána is also advised in this respect."
> §6.7 "Enforcement of e-scooter use (through the traffic legislation) – speed, age of rider, not
> carrying goods, not using footpaths and rules of the road – is, apart from parking, a matter for
> An Garda Síochána."

Statute for the bye-laws is the same LGA 2001 Part 19 route as 2.4 (s.199 bye-laws; art.4(b)
notice to the Superintendent; s.204(1) authorised person includes a Garda). The Road Traffic and
Roads Act 2023 and the 2024 regulations make e-scooters (powered personal transporters) legal. I
found no provision there that gives a local authority a bye-law or enforcement role specific to
shared schemes.

- **Row 25 (S13a, C):** `RSA; AGS`, guidance. The Advice Note names both bodies for safety input
  when setting up schemes. The statutory notice to the Superintendent alone would only support I.
- **Row 26 (S14, R):** `AGS`, statute (s.204(1), (3)(d); S.I. 362/2006 art.8, so a Garda can sign a
  fixed payment notice on the council's behalf), reinforced by the Advice Note §6.7 and
  Garda Síochána Act 2005 s.7(1)(g) ("regulating and controlling road traffic and improving road
  safety").
- **Row 27 (S14, C):** the Advice Note supports general RSA and AGS liaison, but not a consultee
  role at the enforcement stage. **UNRESOLVED.** Once AGS is R on this row, AGS as C would be
  redundant.

### 2.7 Road opening licences (row 28)

Roads Act 1993 s.13(10) (already S91) says nothing on the Gardaí. The *Guidelines for Managing
Openings in Public Roads* ("Purple Book", 2nd ed. Rev 1, April 2017), already S91:

> §3.4.2 a temporary closure for licensed works "will be subject to a statutory public
> consultation and input of An Garda Síochána".
> §3.4.3 "Any proposals to use positive traffic control measures are to be notified to An Garda
> Síochána by the Licence Holder prior to commencement of works."
> §5.2.4 on-site documents include "the written consent from the Garda Síochána for the use of
> temporary traffic lights/stop-go boards where applicable".

Traffic Signs Manual ch.8 §8.1.3.7 also applies (see 2.3).

**Recommendation:** `AGS`, guidance. Most of the Garda touchpoints fall on the *licence holder*, not
the council as decision-maker, so the C role on the council's decision is guidance-level. Only
this default variant has a GS cell. The telecoms and ESB variants have none.

### 2.8 Temporary road closures and temporary traffic management (rows 29 to 34)

Roads Act 1993 s.75, <https://revisedacts.lawreform.ie/eli/1993/act/14/section/75/revised/en/html>:

> s.75(1) "A road authority may by order— (a) for the purpose of facilitating a road race … or any
> other event, (b) for the purpose of facilitating the carrying out of works, or (c) for any other
> purpose, close a public road to traffic …"
> s.75(2)(d) "A person who without lawful authority closes a public road shall be guilty of an
> offence."

Roads Regulations 1994 (S.I. 119/1994) art.12,
<https://www.irishstatutebook.ie/eli/1994/si/119/made/en/print>:

> art.12(1) at least 14 days' notice of intention "(b) in writing to the **Superintendent of the
> Garda Síochána** within whose district the road is situated"; art.12(4)(b) at least 7 days'
> notice of the decision likewise; art.12(6)(a) in an urgent closure the authority "shall
> immediately notify the Superintendent".

This is a **notification** duty (Informed). It is not a duty to consult. s.75 names no consultee,
and art.12(3) requires consideration of *objections* from anyone. Compare s.74 (road races), which
requires the organiser to give notice "to the road authority and to the Superintendent of the Garda
Síochána" (Roads Act 1993 s.74(2)).

**Row 32 (s.75 order, C).** Statute gives notice only. Guidance goes further: the Purple Book
§3.4.2 says closures involve "input of An Garda Síochána", and Meath's event page requires a
"Gardai Letter / Email (where indicated that they are part of the Event Plan)" with any
road-event application (<https://www.meath.ie/council/council-services/roads-and-travel/road-permits-and-licences/safety-management-and-licencing-of-events>).
`AGS`, guidance, with the role-letter flag.

**Row 29 (S11 council works, C).** Traffic Signs Manual ch.8 §8.1.3.7, §8.4.4.17, §8.4.4.31
(2.3). `AGS`, guidance. Of the three S11 variants, only this one and the two below carry a GS
cell.

**Row 30 (S11 event under s.75 order, C).** Art.12 notice (statute, I), the Meath event
requirements above and TSM §8.1.3.7. `AGS`, guidance.

**Row 31 (S11 Garda-run event closures, R).** The Gardaí publish the plan and announce the closures
themselves. Garda page: <https://www.garda.ie/en/about-us/our-departments/office-of-corporate-communications/news-media/news-archive/an-garda-siochana-traffic-management-plan-luke-combs-slane-castle-concerts-2026.html>
(search excerpt: "At 12:30pm on 19th of July 2026 all roads into Slane will be closed"; the page
itself could not be fetched here). The variant is by definition the one where the Gardaí act, so
`AGS` is the natural R. **I could not verify the legal power for a Garda closure.** s.75(2)(d)
implies a closure needs "lawful authority". The existing assignment note already records "Legal
basis unknown; no Council s.75 order found (F36)". Confidence: inferred.

**Row 33 (S14 offences, R).** s.75(2) creates the offences but names no enforcer. Roads Act 1993
s.81(3)(a): "a summary offence under any provision of this Act may be prosecuted by the road
authority concerned." Garda Síochána Act 2005 s.7(1)(g) gives the Gardaí the general function of
"regulating and controlling road traffic". Recommend `AGS`, inferred. The current assignment has
only `C=LA-CE` on this row. That looks wrong, because the statute gives the *road authority* the
power to prosecute. See Q5.

**Row 34 (S15, C).** The S15 stage is monitoring, close-out and reporting. The assignment itself
says "Thin evidence" (source S152). I found nothing that names a Garda or RSA role at close-out of
a closure. **UNRESOLVED.**

### 2.9 Outdoor event licences (row 35)

PDA 2000 Part XVI (ss.230 to 234) was **repealed on 9 September 2026** (S.I. 466 of 2026, art.3).
The regime is now Part 16 of the Planning and Development Act 2024 and the Planning and
Development (Licensing of Outdoor Events) Regulations 2026 (S.I. 468 of 2026).

- PDA 2024 s.479(3)(h): regulations may provide for "the persons that shall be consulted in
  relation to an application". <https://www.irishstatutebook.ie/eli/2024/act/34/section/479/enacted/en/html>
- S.I. 468/2026 reg 2: "'prescribed body' means the following: (a) **the relevant Chief
  Superintendent of the Garda Síochána**; (b) the Health Service Executive; (c) any local,
  regional or planning authority; (d) the National Transport Authority."
  <https://www.irishstatutebook.ie/eli/2026/si/468/made/en/print>
- reg 9(1): "…a local authority shall consult with the prescribed bodies by sending a copy of the
  application to them and stating that submissions or observations may be made …". reg 15 does the
  same for events the local authority itself proposes. reg 7 (pre-application meeting) requires it
  to invite the prescribed bodies.

**Recommendation:** `AGS`, statute. The same list also names the **HSE** (no party in
`parties.csv`) and the **NTA** (already a party). If the GS cell was meant as "safety bodies", the
HSE is arguably in scope. See Q6.

## 3. Conflicts with current assignments and with Dave's rulings

- **No conflict with Dave's rulings.** `AGS` is not given any role in setting speed limits here.
  RT-37.S13b's *road works speed limit order* variant is already ruled and is a different key from
  row 32.
- **The S7b note is overstated.** Seven assignments say "Garda consultation is statutory".
  s.38(3) is inoperative (no class prescribed); only s.95(3)(b) RTA 1961 is statutory, and only
  where regulatory signs are provided. The evidence level is `default-s149-4`.
- **`X-18` activity definition** cites "s.230 PDA 2000". That section was repealed on
  9 September 2026. Source S153 (Meath event licence page) and the definition still carry it. The
  definition also says conditions include traffic management plans "agreed with the LA and An Garda
  Síochána". I did not verify that wording in S.I. 468/2026.
- **`RT-37.S14|Offences`** has `C=LA-CE` only. s.81(3)(a) Roads Act 1993 gives prosecution to the
  road authority, which points to R (and probably A) for `LA-CE`.
- **`RT-37.S13b` s.75 row** has no Gardaí role at all after the GS cell is removed. Statute gives
  them notice (art.12), which is an `I`.
- **`RT-14a.S13b` row** note says "Bus stop location approval, s.16 RTA 2002 / S.I. 12 of 2013".
  S.I. 12/2013 is a commencement order. The operative law is s.85 RTA 1961 as substituted by
  s.16 RTA 2002.
- **`RT-10.S14` and `RT-26.S14`** notes cite "authorised persons" without saying the Gardaí are
  among them by statute (s.204(1)).

## 4. Open questions for Dave

- **Q1. Role letter.** Where the source supports a body but only at "notified" level (rows 22,
  32 and the statutory half of 1 to 7), should a C cell become `AGS` anyway? I did that where
  guidance supports consultation (rows 1 to 7, 32). Row 32 is the weakest: statute is only notice.
  The alternative is to leave it UNRESOLVED or add `I=AGS` separately.
- **Q2. S7b.** (a) Confirm the "no class prescribed" finding. I found none after Oct 2023, but I
  could not search the Iris Oifigiúil. (b) Should the `AGS` ruling carry a qualifier (the model has
  a `qualifier` column), for example "where regulatory signs are provided"? (c) Should the seven
  notes be corrected? That would be in the master tables, not here.
- **Q3. Enforcement-stage C cells** (rows 23, 27). The statute makes the Gardaí enforcers, not
  consultees. I recommend leaving both C cells UNRESOLVED and, for RT-10.S14, considering a
  separate `R=AGS` (authorised person) line. RT-26.S14 R already gets `AGS` from row 26.
- **Q4. S5 and S10.** Both rest on non-binding, non-NTA guidance (the Traffic Management
  Guidelines are undated and old; the TII standard is formally for national roads). Is guidance
  enough for a published C? If not, these 14 cells become UNRESOLVED.
- **Q5. RT-37.S14.** Accept `AGS` as R (inferred)? Separately, should `LA-CE` be R on this row,
  given s.81(3)(a)?
- **Q6. HSE.** The event-licence prescribed bodies include the HSE. Add an `HSE` party and a
  separate role on X-18.S13b? That is outside the GS question, so I made no recommendation.
- **Q7. Row 31 legal basis.** Is "Garda-run closure" worth a source search for the Garda's statutory
  power (I found none), or is the Garda publication itself enough for an `AGS` R?
- **Q8. Row 24 stays `AGS`.** The statute is silent and the NTA guidance is rural-only. Do you
  prefer REMOVE (statute silence) or UNRESOLVED?

## 5. Sources not reachable in this session

- garda.ie traffic-plan page (fetch failed; relied on search excerpts).
- The Traffic Management Guidelines extract has no title page in the text I read, so its edition
  date is not verified.
- Iris Oifigiúil and the Oireachtas SI list were not searched for post-2023 s.38(3) prescriptions.
