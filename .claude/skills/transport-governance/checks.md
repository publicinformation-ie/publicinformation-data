# Transport governance checks (GDA)

Read only when changing or validating the model. Each question has its expected answer as row
references with A and R. Checks marked `motion` are drawn from real council motions in
`pipelines/minutes_pipeline/steps/extract_motions/output.json` (read only; `extract_motions` is
never run for this).

## Procedure

1. Copy `SKILL.md`, `vocabulary.md` and `raci-gda.md` (not this file) to an empty scratch
   directory.
2. Give a fresh subagent only that directory and the Question column below. It answers each
   question with the row reference(s) and their A and R, citing the row it used.
3. Compare each answer with Expected. Resolve every miss as either a model gap or ambiguity (fix
   the model) or a wrong expectation (fix this file), and record it in the Validation log.
4. In the same pass, run the banned-term grep over `raci-gda.md` and `SKILL.md`.

## Questions

| # | Question | Expected | Covers | Source |
|---|---|---|---|---|
| 1 | Who maintains the N3 national road near Navan? | infra/national-roads · Maintenance → A: TII, R: LA-CE, TII | trap: national road maintenance | design |
| 2 | Does An Bord Pleanála still approve new Luas lines? If not, who does? | infra/light-rail · Consent → A: ACP, R: ACP | renamed body | design |
| 3 | Who sets the fare on a Dublin Bus route, and who sets the fare on a licensed commercial coach route? | svc/pso-bus · Specification → A: NTA, R: NTA; svc/commercial-bus · Specification → A: Comm-op, R: Comm-op | trap: PSO vs commercial fares | design |
| 4 | Who sets the maximum taxi fare? | svc/spsv · Regulation → A: NTA, R: NTA | trap: taxi rank vs SPSV | design |
| 5 | Who issues driving licences? | users/vehicles-drivers · Regulation → A: RSA, R: RSA | subdomain coverage | design |
| 6 | Who enforces speed limits? | users/traffic-law · Enforcement → A: AGS, R: AGS | subdomain coverage | design |
| 7 | Who issues pay-parking fines in a town centre? | infra/kerbside · Enforcement · parking → A: LA-CE, R: LA-CE | LA enforcement | design |
| 8 | Who licenses clamping companies? | infra/kerbside · Regulation · clamping → A: NTA, R: NTA | non-obvious regulator | design |
| 9 | Who approves a new footpath and cycle track scheme that goes through Part 8? | infra/active-travel · Consent · Part 8 → A: LA-members, R: LA-CE | reserved function | design |
| 10 | Who runs DART trains day to day? | svc/rail · Operation → A: NTA, R: IE | subdomain coverage | design |
| 11 | Who maintains the railway track between Drogheda and Dublin? | infra/heavy-rail · Maintenance → A: IE, R: IE | subdomain coverage | design |
| 12 | Who pays for BusConnects bus priority works, and who builds them? | infra/bus · Funding → A: NTA, R: NTA; infra/bus · Delivery → A: NTA, R: NTA, LA-CE | Funding, Delivery | design |
| 13 | Who draws up Dublin Port's masterplan? | infra/ports-airfields · Strategic planning · port → A: Port-co, R: Port-co | subdomain coverage | design |
| 14 | Who makes the rules for a shared e-scooter scheme in a town? | svc/shared-mobility · Regulation → A: LA-members, R: LA-CE | subdomain coverage | design |
| 15 | Who sets national policy on licensing commercial bus routes? | svc/commercial-bus · Policy → A: DoT, R: DoT | Policy | design |
| 16 | Who runs Luas trams day to day? | svc/light-rail · Operation → A: NTA, R: PSO-op | subdomain coverage | design |
| 17 | A motion asks the NTA to add later evening services to the TFI Local Link 188 Drogheda–Athboy bus. Who decides? | svc/pso-bus · Specification → A: NTA, R: NTA | motion | motion: 1511, 2026-06-11 |
| 18 | A motion asks that proposed housing estate special speed limit bye-laws go to full council for approval. Who decides? | infra/regional-local-roads · Regulation · special speed limit → A: LA-members, R: LA-CE | motion; trap: special speed limit bye-law | motion: 1511, 2023-07-06 |
| 19 | A motion calls on Bus Éireann and the Department of Education to provide a school bus place for every pupil who needs one. Who decides? | svc/school-transport · Specification → A: DoE, R: BE | motion; trap: school transport | motion: 1511, 2023-10-02 |
| 20 | A motion asks that a taxi rank be installed in a town, with locations put to the elected members. Who decides? | infra/kerbside · Regulation · appointed stand → A: LA-members, R: LA-CE | motion; trap: taxi rank vs SPSV | motion: 1511, 2017-04-24 |
| 21 | A motion asks for high-powered EV charging hubs in a Municipal District. Who pays, and who decides where they go? | infra/kerbside · Funding · EV charging → A: DoT, R: DoT; infra/kerbside · Specification → A: LA-CE, R: LA-CE | motion | motion: 1511, 2024-09-03 |
| 22 | A motion calls on the local authority to take a housing estate in charge and repair its roads and footpaths. Who decides the taking in charge? | infra/regional-local-roads · Specification · taking in charge → A: LA-members, R: LA-CE | motion | motion: 1511, 2026-05-20 |
| 23 | A motion asks for a pedestrian crossing at a bus stop. Who decides whether it is built? | infra/active-travel · Specification → A: LA-CE, R: LA-CE | boundary: crossing at a bus stop | motion: 1511, 2026-05-20 |
| 24 | Who decides the yearly programme of road maintenance works in Dún Laoghaire–Rathdown, and in Meath? | infra/regional-local-roads · Specification → A: LA-CE, R: LA-CE; infra/regional-local-roads · Specification · Municipal District → A: LA-MD, R: LA-CE | with and without Municipal Districts | design |
| 25 | Who pays for a licensed commercial bus route? | svc/commercial-bus · Funding → Not applicable | answer is no body | design |
| 26 | Write one sentence of public-facing copy saying who decides where taxi ranks go. | copy: uses the plain labels of LA-members and LA-CE; no IDs, no row references, no banned terms | public register | design |

## Validation log

| Date | # | Answer given | Resolution |
|---|---|---|---|
