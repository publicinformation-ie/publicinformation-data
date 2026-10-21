# Transport RACI — Greater Dublin Area

Who does what in transport for the seven GDA local authorities. Terms, IDs and boundary rules are
in `vocabulary.md`. A row is identified as `<subdomain> · <Function> · <Qualifier>`. Every row is
`verify` until the user confirms it.

## Infrastructure

### infra/national-roads — tags: road

| Function | Qualifier | A | R | C | Basis | Status |
|---|---|---|---|---|---|---|
| Policy | — | DoT | DoT | TII | practice | verify |
| Strategic planning | — | TII | TII | DoT, NTA, LA-CE | practice | verify |
| Funding | — | TII | TII | DoT | Roads Act 1993 s.24 | verify |
| Specification | — | TII | TII, LA-CE | NTA | Roads Act 1993 s.17(1)(a) | verify |
| Consent | Section 51 approval | ACP | ACP | TII, LA-CE | Roads Act 1993 s.51 | verify |
| Consent | Part 8 | LA-members | LA-CE | TII | Planning and Development Act 2000 s.179 | verify |
| Delivery | — | TII | LA-CE, TII | — | Roads Act 1993 | verify |
| Operation | — | TII | TII, LA-CE | — | practice | verify |
| Maintenance | — | LA-CE | LA-CE | — | Roads Act 1993 s.13 | verify |
| Regulation | special speed limit | LA-members | LA-CE | TII, AGS | Road Traffic Act 2004 s.9(7) | verify |
| Regulation | toll | TII | TII | DoT | Roads Act 1993 s.57 | verify |
| Enforcement | toll | TII | TII | — | Roads Act 1993 | verify |

Not applicable: none.

1. The split is by function. TII is A for Funding, Specification, Strategic planning and
   Consent, because it funds, specifies and supervises the network. LA-CE is the road authority
   and carries the statutory maintenance duty (Roads Act 1993 s.13), so it is A for Maintenance.
   Delivery and Operation are still recorded with TII as A, pending confirmation.
2. A special speed limit on a national road needs TII's prior written consent (Road Traffic Act
   2004 s.9(7)), so TII's role is binding, not advisory. The row still records TII as C (see Open
   questions).

### infra/regional-local-roads — tags: road

| Function | Qualifier | A | R | C | Basis | Status |
|---|---|---|---|---|---|---|
| Policy | — | DoT | DoT | DHLGH | practice | verify |
| Strategic planning | development plan | LA-members | LA-CE | NTA, LA-SPC | Planning and Development Act 2024 s.43, s.55 | verify |
| Strategic planning | Local Transport Plan | LA-members | LA-CE | NTA, TII | practice | verify |
| Funding | state grant | DoT | DoT | — | practice | verify |
| Funding | annual budget | LA-members | LA-CE | — | Local Government Act 2001 | verify |
| Specification | — | LA-CE | LA-CE | LA-members | Roads Act 1993 s.13 | verify |
| Specification | schedule of municipal district works · Municipal District | LA-MD | LA-CE | — | Local Government Reform Act 2014 | verify |
| Specification | taking in charge | LA-members | LA-CE | — | Roads Act 1993 s.11 | verify |
| Specification | taking in charge · Municipal District | LA-MD | LA-CE | — | Roads Act 1993 s.11 | verify |
| Consent | Part 8 | LA-members | LA-CE | — | Planning and Development Act 2000 s.179 | verify |
| Consent | Section 38 | LA-CE | LA-CE | AGS | Road Traffic Act 1994 s.38 | verify |
| Consent | Section 38 · Municipal District | LA-MD | LA-CE | AGS | Road Traffic Act 1994 s.38 | verify |
| Consent | Section 51 approval | ACP | ACP | LA-CE | Roads Act 1993 s.51 | verify |
| Delivery | — | LA-CE | LA-CE | — | Roads Act 1993 s.13 | verify |
| Operation | — | LA-CE | LA-CE | — | practice | verify |
| Maintenance | — | LA-CE | LA-CE | — | Roads Act 1993 s.13 | verify |
| Regulation | special speed limit | LA-members | LA-CE | AGS | Road Traffic Act 2004 s.9 | verify |
| Regulation | traffic management | LA-CE | LA-CE | AGS | Road Traffic Act 1961 s.95 | verify |
| Regulation | road opening licence | LA-CE | LA-CE | — | Roads Act 1993 s.13 | verify |
| Enforcement | road opening licence | LA-CE | LA-CE | — | Roads Act 1993 s.13 | verify |

Not applicable: none.

1. Rows with the `Municipal District` qualifier apply where the local authority is divided into
   Municipal Districts: LA-MD adopts the schedule of municipal district works, makes Section 38
   decisions and takes estates in charge. Dublin City, Dún Laoghaire–Rathdown, Fingal and South
   Dublin have no Municipal Districts, so the rows without it apply there.
2. LA-MD appears in C only where the local authority has Municipal Districts.

### infra/active-travel — tags: active

| Function | Qualifier | A | R | C | Basis | Status |
|---|---|---|---|---|---|---|
| Policy | — | DoT | DoT | NTA | practice | verify |
| Strategic planning | — | DoT | NTA | LA-CE | Dublin Transport Authority Act 2008 | verify |
| Funding | — | NTA | NTA | DoT | practice | verify |
| Specification | — | LA-CE | LA-CE | NTA, LA-members | practice | verify |
| Consent | Part 8 | LA-members | LA-CE | — | Planning and Development Act 2000 s.179 | verify |
| Consent | Section 38 | LA-CE | LA-CE | AGS, NTA | Road Traffic Act 1994 s.38 | verify |
| Consent | Section 38 · Municipal District | LA-MD | LA-CE | AGS, NTA | Road Traffic Act 1994 s.38 | verify |
| Delivery | — | LA-CE | LA-CE | NTA | practice | verify |
| Maintenance | — | LA-CE | LA-CE | — | Roads Act 1993 s.13 | verify |
| Regulation | — | LA-CE | LA-CE | AGS | Road Traffic Act 1961 s.95 | verify |

Not applicable: Operation, Enforcement.

1. Offences on cycle tracks and footpaths are enforced by AGS under
   `users/traffic-law · Enforcement`.

### infra/bus — tags: bus

| Function | Qualifier | A | R | C | Basis | Status |
|---|---|---|---|---|---|---|
| Policy | — | DoT | DoT | NTA | practice | verify |
| Strategic planning | — | DoT | NTA | LA-CE | Dublin Transport Authority Act 2008 s.12 | verify |
| Funding | — | NTA | NTA | DoT | Dublin Transport Authority Act 2008 | verify |
| Specification | — | NTA | NTA, LA-CE | — | Dublin Transport Authority Act 2008 | verify |
| Consent | Part 8 | LA-members | LA-CE | NTA | Planning and Development Act 2000 s.179 | verify |
| Consent | Section 51 approval | ACP | ACP | NTA, LA-CE | Roads Act 1993 s.51 | verify |
| Delivery | — | NTA | NTA, LA-CE | — | practice | verify |
| Operation | — | NTA | NTA, LA-CE | — | practice | verify |
| Maintenance | — | LA-CE | LA-CE | NTA | Roads Act 1993 s.13 | verify |
| Regulation | — | LA-CE | LA-CE | NTA, AGS | Road Traffic Act 1961 s.95 | verify |

Not applicable: Enforcement.

1. Bus lane offences are enforced by AGS under `users/traffic-law · Enforcement`.

### infra/heavy-rail — tags: rail

| Function | Qualifier | A | R | C | Basis | Status |
|---|---|---|---|---|---|---|
| Policy | — | DoT | DoT | NTA, IE | practice | verify |
| Strategic planning | — | DoT | NTA | IE | Dublin Transport Authority Act 2008 s.12 | verify |
| Funding | existing network | DoT | DoT | — | practice | verify |
| Funding | new GDA project | NTA | NTA | DoT | practice | verify |
| Specification | — | NTA | NTA, IE | — | Dublin Transport Authority Act 2008 | verify |
| Consent | — | ACP | ACP | IE | Transport (Railway Infrastructure) Act 2001 | verify |
| Delivery | — | IE | IE | NTA | Transport (Railway Infrastructure) Act 2001 | verify |
| Operation | — | IE | IE | — | Railway Safety Act 2005 | verify |
| Maintenance | — | IE | IE | — | practice | verify |
| Regulation | — | CRR | CRR | — | Railway Safety Act 2005 | verify |
| Enforcement | — | CRR | CRR | — | Railway Safety Act 2005 | verify |

Not applicable: none.

### infra/light-rail — tags: light-rail

| Function | Qualifier | A | R | C | Basis | Status |
|---|---|---|---|---|---|---|
| Policy | — | DoT | DoT | NTA, TII | practice | verify |
| Strategic planning | — | DoT | NTA | TII | Dublin Transport Authority Act 2008 s.12 | verify |
| Funding | — | NTA | NTA | DoT | Dublin Transport Authority Act 2008 | verify |
| Specification | — | NTA | NTA, TII | — | Dublin Transport Authority Act 2008 | verify |
| Consent | — | ACP | ACP | TII | Transport (Railway Infrastructure) Act 2001 | verify |
| Delivery | — | TII | TII | NTA | Transport (Railway Infrastructure) Act 2001 | verify |
| Operation | — | TII | PSO-op | NTA | practice | verify |
| Maintenance | — | TII | PSO-op | — | practice | verify |
| Regulation | — | CRR | CRR | — | Railway Safety Act 2005 | verify |
| Enforcement | — | CRR | CRR | — | Railway Safety Act 2005 | verify |

Not applicable: none.

### infra/kerbside — tags: road, taxi

| Function | Qualifier | A | R | C | Basis | Status |
|---|---|---|---|---|---|---|
| Policy | — | DoT | DoT | — | practice | verify |
| Strategic planning | — | LA-members | LA-CE | NTA, LA-SPC | Planning and Development Act 2024 s.43, s.55 | verify |
| Funding | — | LA-members | LA-CE | — | Local Government Act 2001 | verify |
| Funding | EV charging | DoT | DoT | LA-CE | practice | verify |
| Specification | — | LA-CE | LA-CE | — | practice | verify |
| Consent | — | LA-CE | LA-CE | — | Planning and Development Act 2000 s.254 | verify |
| Delivery | — | LA-CE | LA-CE | — | practice | verify |
| Operation | — | LA-CE | LA-CE | — | practice | verify |
| Maintenance | — | LA-CE | LA-CE | — | Roads Act 1993 s.13 | verify |
| Regulation | parking | LA-members | LA-CE | AGS | Road Traffic Act 1994 s.36 | verify |
| Regulation | parking · Municipal District | LA-MD | LA-CE | AGS | Road Traffic Act 1994 s.36 | verify |
| Regulation | appointed stand | LA-members | LA-CE | NTA, AGS | Road Traffic Act 1961 s.84 | verify |
| Regulation | appointed stand · Municipal District | LA-MD | LA-CE | NTA, AGS | Local Government Act 2001 Sch. 14A item 29 | verify |
| Regulation | clamping | NTA | NTA | — | Vehicle Clamping Act 2015 | verify |
| Enforcement | parking | LA-CE | LA-CE | — | Road Traffic Act 1994 s.36 | verify |
| Enforcement | clamping | NTA | NTA | — | Vehicle Clamping Act 2015 | verify |

Not applicable: none.

1. The `Municipal District` rows apply where the local authority has Municipal Districts; the
   rows without it cover the rest.
2. `Regulation · appointed stand` decides where taxi ranks are. Licensing taxis and their
   drivers is `svc/spsv · Regulation`.

### infra/ports-airfields — tags: maritime, aviation

| Function | Qualifier | A | R | C | Basis | Status |
|---|---|---|---|---|---|---|
| Policy | — | DoT | DoT | DoD | practice | verify |
| Strategic planning | port | Port-co | Port-co | DoT, LA-CE | Harbours Act 1996 | verify |
| Strategic planning | airport | daa | daa | IAA, LA-CE | practice | verify |
| Funding | port | Port-co | Port-co | — | Harbours Act 1996 | verify |
| Funding | airport | daa | daa | — | State Airports Act 2004 | verify |
| Specification | port | Port-co | Port-co | — | Harbours Act 1996 | verify |
| Specification | airport | daa | daa | IAA | practice | verify |
| Consent | strategic infrastructure | ACP | ACP | LA-CE | Planning and Development Act 2000 s.37A | verify |
| Consent | planning application | LA-CE | LA-CE | — | Planning and Development Act 2000 s.34 | verify |
| Delivery | port | Port-co | Port-co | — | Harbours Act 1996 | verify |
| Delivery | airport | daa | daa | — | practice | verify |
| Operation | port | Port-co | Port-co | — | Harbours Act 1996 | verify |
| Operation | airport | daa | daa | — | State Airports Act 2004 | verify |
| Maintenance | port | Port-co | Port-co | — | Harbours Act 1996 | verify |
| Maintenance | airport | daa | daa | — | practice | verify |
| Regulation | port | Port-co | Port-co | DoT | Harbours Act 1996 | verify |
| Regulation | airport | IAA | IAA | — | Air Navigation and Transport Act 2022 | verify |
| Regulation | aircraft noise | LA-CE | LA-CE | IAA, daa | Aircraft Noise (Dublin Airport) Regulation Act 2019 | verify |
| Enforcement | port | Port-co | Port-co | — | Harbours Act 1996 | verify |
| Enforcement | airport | IAA | IAA | — | Air Navigation and Transport Act 2022 | verify |

Not applicable: none.

1. A military aerodrome has no rows: DoD is A and R for every function there.
2. Where a port is vested in a local authority rather than a Port-co, LA-CE takes the Port-co
   role in every port row and LA-members adopt its annual budget.

## Services

### svc/pso-bus — tags: bus

| Function | Qualifier | A | R | C | Basis | Status |
|---|---|---|---|---|---|---|
| Policy | — | DoT | DoT | NTA | practice | verify |
| Strategic planning | — | DoT | NTA | LA-CE | Dublin Transport Authority Act 2008 s.12 | verify |
| Funding | — | NTA | NTA | DoT | Dublin Transport Authority Act 2008 | verify |
| Specification | — | NTA | NTA | DB, BE, PSO-op, LA-CE | Dublin Transport Authority Act 2008 | verify |
| Delivery | — | NTA | NTA | — | Dublin Transport Authority Act 2008 | verify |
| Operation | — | NTA | DB, BE, PSO-op | — | Dublin Transport Authority Act 2008 | verify |
| Maintenance | — | NTA | DB, BE, PSO-op | — | practice | verify |
| Regulation | — | NTA | NTA | — | Public Transport Regulation Act 2009 | verify |
| Enforcement | — | NTA | DB, BE, PSO-op | AGS | practice | verify |

Not applicable: Consent.

1. Specification covers routes, timetables and fares.
2. Delivery is the procurement of PSO contracts and of buses.
3. Rural services branded TFI Local Link are PSO bus services run by PSO-op.

### svc/commercial-bus — tags: bus

| Function | Qualifier | A | R | C | Basis | Status |
|---|---|---|---|---|---|---|
| Policy | — | DoT | DoT | NTA | practice | verify |
| Specification | — | Comm-op | Comm-op | NTA | Public Transport Regulation Act 2009 | verify |
| Operation | — | Comm-op | Comm-op | — | Public Transport Regulation Act 2009 | verify |
| Maintenance | — | Comm-op | Comm-op | — | practice | verify |
| Regulation | — | NTA | NTA | — | Public Transport Regulation Act 2009 | verify |
| Enforcement | — | NTA | NTA | AGS | Public Transport Regulation Act 2009 | verify |

Not applicable: Strategic planning, Funding, Consent, Delivery.

1. NTA's approval of a route and timetable through the licence is Regulation; the choice of
   route, timetable and fare is Comm-op's Specification.

### svc/rail — tags: rail

| Function | Qualifier | A | R | C | Basis | Status |
|---|---|---|---|---|---|---|
| Policy | — | DoT | DoT | NTA, IE | practice | verify |
| Strategic planning | — | DoT | NTA | IE | Dublin Transport Authority Act 2008 s.12 | verify |
| Funding | — | NTA | NTA | DoT | Dublin Transport Authority Act 2008 | verify |
| Specification | — | NTA | NTA | IE | Dublin Transport Authority Act 2008 | verify |
| Delivery | — | NTA | IE | — | practice | verify |
| Operation | — | NTA | IE | — | Dublin Transport Authority Act 2008 | verify |
| Maintenance | — | NTA | IE | — | practice | verify |
| Regulation | — | CRR | CRR | — | Railway Safety Act 2005 | verify |
| Enforcement | bye-law | IE | IE | AGS | practice | verify |
| Enforcement | rail safety | CRR | CRR | — | Railway Safety Act 2005 | verify |

Not applicable: Consent.

1. Delivery and Maintenance here are of trains; track and stations are `infra/heavy-rail`.
2. Maintenance is A for NTA, following the decision to use NTA for vehicle maintenance. The owner
   of the Irish Rail fleet has not been checked (see Open questions).

### svc/light-rail — tags: light-rail

| Function | Qualifier | A | R | C | Basis | Status |
|---|---|---|---|---|---|---|
| Policy | — | DoT | DoT | NTA | practice | verify |
| Strategic planning | — | DoT | NTA | TII | Dublin Transport Authority Act 2008 s.12 | verify |
| Funding | — | NTA | NTA | DoT | Dublin Transport Authority Act 2008 | verify |
| Specification | — | NTA | NTA | TII | Dublin Transport Authority Act 2008 | verify |
| Delivery | — | NTA | TII | — | practice | verify |
| Operation | — | NTA | PSO-op | TII | practice | verify |
| Maintenance | — | TII | PSO-op | — | practice | verify |
| Regulation | — | CRR | CRR | — | Railway Safety Act 2005 | verify |
| Enforcement | bye-law | TII | PSO-op | AGS | practice | verify |
| Enforcement | rail safety | CRR | CRR | — | Railway Safety Act 2005 | verify |

Not applicable: Consent.

1. Delivery is the procurement of the operations and maintenance contract, which TII runs for
   NTA.
2. Maintenance is A for TII as recorded. The Luas fleet owner has not been confirmed (see Open
   questions).

### svc/spsv — tags: taxi

| Function | Qualifier | A | R | C | Basis | Status |
|---|---|---|---|---|---|---|
| Policy | — | DoT | DoT | NTA | practice | verify |
| Funding | — | NTA | NTA | DoT | practice | verify |
| Operation | — | Comm-op | Comm-op | — | Taxi Regulation Act 2013 | verify |
| Maintenance | — | Comm-op | Comm-op | — | Taxi Regulation Act 2013 | verify |
| Regulation | — | NTA | NTA | AGS | Taxi Regulation Act 2013 | verify |
| Enforcement | — | NTA | NTA, AGS | — | Taxi Regulation Act 2013 | verify |

Not applicable: Strategic planning, Specification, Consent, Delivery.

1. Regulation includes licensing vehicles and drivers and setting the national maximum taxi fare.
2. Where taxi ranks are is `infra/kerbside · Regulation · appointed stand`.

### svc/school-transport — tags: bus, school

| Function | Qualifier | A | R | C | Basis | Status |
|---|---|---|---|---|---|---|
| Policy | — | DoE | DoE | — | practice | verify |
| Funding | — | DoE | DoE | — | practice | verify |
| Specification | — | DoE | BE | — | practice | verify |
| Delivery | — | DoE | BE | — | practice | verify |
| Operation | — | BE | BE | — | practice | verify |
| Maintenance | — | BE | BE | — | practice | verify |

Not applicable: Strategic planning, Consent, Regulation, Enforcement.

1. DoE sets eligibility; BE plans the routes.
2. NTA, LA-members and LA-CE have no row in this subdomain.

### svc/shared-mobility — tags: active, shared

| Function | Qualifier | A | R | C | Basis | Status |
|---|---|---|---|---|---|---|
| Policy | — | DoT | DoT | NTA | practice | verify |
| Funding | — | NTA | NTA | LA-CE | practice | verify |
| Specification | — | LA-CE | LA-CE | NTA | practice | verify |
| Delivery | — | LA-CE | LA-CE | NTA | practice | verify |
| Operation | — | Comm-op | Comm-op | — | practice | verify |
| Maintenance | — | Comm-op | Comm-op | — | practice | verify |
| Regulation | — | LA-members | LA-CE | AGS | Road Traffic and Roads Act 2023 | verify |
| Enforcement | — | LA-CE | LA-CE | — | Road Traffic and Roads Act 2023 | verify |

Not applicable: Strategic planning, Consent.

1. Use of a privately bought e-scooter on a public road is `users/traffic-law`.

## Users

### users/vehicles-drivers — tags: road

| Function | Qualifier | A | R | C | Basis | Status |
|---|---|---|---|---|---|---|
| Policy | — | DoT | DoT | RSA | practice | verify |
| Strategic planning | — | DoT | RSA | AGS, TII | practice | verify |
| Funding | — | DoT | DoT | — | practice | verify |
| Operation | — | RSA | RSA | — | Road Safety Authority Act 2006 | verify |
| Regulation | — | RSA | RSA | DoT | Road Safety Authority Act 2006 | verify |
| Enforcement | — | RSA | RSA | — | Road Safety Authority Act 2006 | verify |

Not applicable: Specification, Consent, Delivery, Maintenance.

1. Operation covers driver testing and vehicle testing services; issuing licences is Regulation.
2. Driving without a licence or test certificate is enforced by AGS under
   `users/traffic-law · Enforcement`; this Enforcement row covers RSA's roadside checks of
   commercial vehicles.

### users/traffic-law — tags: road

| Function | Qualifier | A | R | C | Basis | Status |
|---|---|---|---|---|---|---|
| Policy | — | DoT | DoT | RSA, AGS | Road Traffic Acts 1961–2024 | verify |
| Strategic planning | — | DoT | RSA | AGS | practice | verify |
| Regulation | — | DoT | DoT | RSA | Road Traffic Acts 1961–2024 | verify |
| Enforcement | — | AGS | AGS | — | Road Traffic Acts 1961–2024 | verify |

Not applicable: Funding, Specification, Consent, Delivery, Operation, Maintenance.

1. Regulation covers the rules of the road and default speed limits; a special speed limit is
   Regulation on the road's infra subdomain.

## Open questions

Parked decisions. Each stays open until the user records an answer here.

1. **Binding consent in the model.** TII's consent to a special speed limit on a national road is
   binding (`infra/national-roads · Regulation · special speed limit`, note 2), but the model has
   no way to record a binding consent. Options: a new column, a qualifier, or a note. The row
   records TII as C for now.
2. **Luas fleet owner.** No official source confirms who owns the Luas trams.
   `svc/light-rail · Maintenance` has TII as A on that basis. If NTA owns the fleet, the decision
   to use NTA for vehicle maintenance would apply.
3. **Irish Rail fleet owner.** `svc/rail · Maintenance` has NTA as A under the decision to use NTA
   for vehicle maintenance. The owner of the fleet has not been checked.
4. **National road Delivery and Operation.** Both have TII as A, which follows the split of
   national roads by function. Confirm whether LA-CE is A for either.
5. **Municipal District rule.** All GDA local authorities have Municipal Districts, so the rule
   that an unqualified row covers "the rest" (vocabulary, Boundary rule 6) rarely applies in this
   region. Decide whether to keep the rule for the non-GDA file.
6. **Enforcement of parking.** `infra/kerbside · Enforcement · parking` cites RTA 1994 s.36, which
   is the bye-law power, not an enforcement power. Find the enforcement basis.
