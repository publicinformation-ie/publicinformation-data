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
| Funding | — | TII | TII | DoT | Roads Act 1993 s.19 | verify |
| Specification | — | TII | TII, LA-CE | NTA | Roads Act 1993 s.19 | verify |
| Consent | — | ACP | ACP | TII, LA-CE | Roads Act 1993 s.51 | verify |
| Delivery | — | TII | LA-CE, TII | — | Roads Act 1993 | verify |
| Operation | — | TII | TII, LA-CE | — | practice | verify |
| Maintenance | — | TII | LA-CE, TII | — | Roads Act 1993 s.13 | verify |
| Regulation | special speed limit | LA-members | LA-CE | TII, AGS | Road Traffic Act 2004 s.9 | verify |
| Regulation | toll | TII | TII | DoT | Roads Act 1993 s.57 | verify |
| Enforcement | toll | TII | TII | — | Roads Act 1993 | verify |

Not applicable: none.

1. LA-CE remains the road authority for national roads in its area and carries the statutory
   maintenance duty (Roads Act 1993 s.13). A is TII because TII funds, specifies and approves
   the work.
2. A special speed limit on a national road needs TII's consent, which is stronger than C. It is
   recorded as C until the model has a way to record a binding consent by another body.

### infra/regional-local-roads — tags: road

| Function | Qualifier | A | R | C | Basis | Status |
|---|---|---|---|---|---|---|
| Policy | — | DoT | DoT | DHLGH | practice | verify |
| Strategic planning | development plan | LA-members | LA-CE | NTA, LA-SPC | Planning and Development Act 2000 s.10 | verify |
| Strategic planning | Local Transport Plan | LA-members | LA-CE | NTA, TII | practice | verify |
| Funding | state grant | DoT | DoT | — | practice | verify |
| Funding | annual budget | LA-members | LA-CE | — | Local Government Act 2001 | verify |
| Specification | — | LA-CE | LA-CE | LA-members | Roads Act 1993 s.13 | verify |
| Specification | Municipal District | LA-MD | LA-CE | — | Local Government Reform Act 2014 | verify |
| Specification | taking in charge | LA-members | LA-CE | — | Roads Act 1993 s.11 | verify |
| Consent | Part 8 | LA-members | LA-CE | — | Planning and Development Act 2000 s.179 | verify |
| Consent | Section 38 | LA-CE | LA-CE | AGS | Road Traffic Act 1994 s.38 | verify |
| Consent | Section 51 approval | ACP | ACP | LA-CE | Roads Act 1993 s.51 | verify |
| Delivery | — | LA-CE | LA-CE | — | Roads Act 1993 s.13 | verify |
| Operation | — | LA-CE | LA-CE | — | practice | verify |
| Maintenance | — | LA-CE | LA-CE | LA-MD | Roads Act 1993 s.13 | verify |
| Regulation | special speed limit | LA-members | LA-CE | LA-MD, AGS | Road Traffic Act 2004 s.9 | verify |
| Regulation | traffic management | LA-CE | LA-CE | AGS | Road Traffic Act 1961 s.95 | verify |
| Regulation | road opening licence | LA-CE | LA-CE | — | Roads Act 1993 s.13 | verify |
| Enforcement | road opening licence | LA-CE | LA-CE | — | Roads Act 1993 s.13 | verify |

Not applicable: none.

1. `Specification · Municipal District` applies where the local authority is divided into
   Municipal Districts: LA-MD adopts the schedule of municipal district works. Dublin City, Dún
   Laoghaire–Rathdown, Fingal and South Dublin have no Municipal Districts, so the `—` row
   applies there.
2. LA-MD appears in C only where the local authority has Municipal Districts.

### infra/active-travel — tags: active

| Function | Qualifier | A | R | C | Basis | Status |
|---|---|---|---|---|---|---|
| Policy | — | DoT | DoT | NTA | practice | verify |
| Strategic planning | — | NTA | NTA | LA-CE | Dublin Transport Authority Act 2008 | verify |
| Funding | — | NTA | NTA | DoT | practice | verify |
| Specification | — | LA-CE | LA-CE | NTA, LA-members | practice | verify |
| Consent | Part 8 | LA-members | LA-CE | — | Planning and Development Act 2000 s.179 | verify |
| Consent | Section 38 | LA-CE | LA-CE | AGS, NTA | Road Traffic Act 1994 s.38 | verify |
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
2. In Operation, NTA runs passenger information at stops and LA-CE runs the traffic signals that
   give buses priority.

### infra/heavy-rail — tags: rail

| Function | Qualifier | A | R | C | Basis | Status |
|---|---|---|---|---|---|---|
| Policy | — | DoT | DoT | NTA, IE | practice | verify |
| Strategic planning | — | DoT | NTA | IE | Dublin Transport Authority Act 2008 s.12 | verify |
| Funding | — | DoT | DoT, NTA | — | practice | verify |
| Specification | — | NTA | NTA, IE | — | Dublin Transport Authority Act 2008 | verify |
| Consent | — | ACP | ACP | IE | Transport (Railway Infrastructure) Act 2001 | verify |
| Delivery | — | IE | IE | NTA | Transport (Railway Infrastructure) Act 2001 | verify |
| Operation | — | IE | IE | — | Railway Safety Act 2005 | verify |
| Maintenance | — | IE | IE | — | Railway Safety Act 2005 | verify |
| Regulation | — | CRR | CRR | — | Railway Safety Act 2005 | verify |
| Enforcement | — | CRR | CRR | — | Railway Safety Act 2005 | verify |

Not applicable: none.

1. In Funding, DoT pays for IE's maintenance and renewal of the existing network; NTA pays for
   new GDA rail projects.

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
| Strategic planning | — | LA-members | LA-CE | NTA, LA-SPC | Planning and Development Act 2000 s.10 | verify |
| Funding | — | LA-members | LA-CE | — | Local Government Act 2001 | verify |
| Funding | EV charging | DoT | DoT | LA-CE | practice | verify |
| Specification | — | LA-CE | LA-CE | LA-MD | practice | verify |
| Consent | — | LA-CE | LA-CE | — | Planning and Development Act 2000 s.254 | verify |
| Delivery | — | LA-CE | LA-CE | — | practice | verify |
| Operation | — | LA-CE | LA-CE | — | practice | verify |
| Maintenance | — | LA-CE | LA-CE | — | Roads Act 1993 s.13 | verify |
| Regulation | parking | LA-members | LA-CE | LA-MD, AGS | Road Traffic Act 1994 s.36 | verify |
| Regulation | appointed stand | LA-members | LA-CE | NTA, AGS | Road Traffic Act 1994 | verify |
| Regulation | clamping | NTA | NTA | — | Vehicle Clamping Act 2015 | verify |
| Enforcement | parking | LA-CE | LA-CE | — | Road Traffic Act 1994 s.36 | verify |
| Enforcement | clamping | NTA | NTA | — | Vehicle Clamping Act 2015 | verify |

Not applicable: none.

1. Where the local authority has Municipal Districts, confirm whether its parking bye-laws are
   made by LA-MD; if so, split `Regulation · parking`.
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
| Consent | — | ACP | ACP | LA-CE | Planning and Development Act 2000 s.37A | verify |
| Delivery | port | Port-co | Port-co | — | Harbours Act 1996 | verify |
| Delivery | airport | daa | daa | — | practice | verify |
| Operation | port | Port-co | Port-co | — | Harbours Act 1996 | verify |
| Operation | airport | daa | daa | — | State Airports Act 2004 | verify |
| Maintenance | port | Port-co | Port-co | — | Harbours Act 1996 | verify |
| Maintenance | airport | daa | daa | — | practice | verify |
| Regulation | port | Port-co | Port-co | DoT | Harbours Act 1996 | verify |
| Regulation | airport | IAA | IAA | — | Air Navigation and Transport Act 2022 | verify |
| Enforcement | port | Port-co | Port-co | — | Harbours Act 1996 | verify |
| Enforcement | airport | IAA | IAA | — | Air Navigation and Transport Act 2022 | verify |

Not applicable: none.

1. A military aerodrome has no rows: DoD is A and R for every function there.
2. Where a port is vested in a local authority rather than a Port-co, LA-CE takes the Port-co
   role in every port row and LA-members adopt its annual budget.
