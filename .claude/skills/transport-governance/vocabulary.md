# Transport governance: question vocabulary

This file holds only what the published vocabularies do not: the words a question arrives
in, and the words an answer must avoid. Definitions are not repeated here.

- Activities and groupings: [`public/vocabularies/transport-activity.md`](../../../public/vocabularies/transport-activity.md)
- Stages: [`public/vocabularies/transport-stage.md`](../../../public/vocabularies/transport-stage.md)
- Parties: [`public/vocabularies/transport-raci-party.md`](../../../public/vocabularies/transport-raci-party.md)
- Evidence levels: [`public/vocabularies/raci-evidence-level.md`](../../../public/vocabularies/raci-evidence-level.md)

## Aliases

A question phrased with a left-hand expression is routed to the activity or stage on the
right. This table is a routing aid, not a vocabulary: the published term is the one to use
in an answer.

| The question says | Route to |
|---|---|
| public transport, bus service, train service | `RT-17`, `RT-18` (road passenger networks and fares), `RL-03` (railway services), `RT-19` (rural and community transport). School transport has no activity: see the gap note. |
| rural transport, Local Link | `RT-19` |
| bus lane, bus priority, bus gate | `RT-13` |
| bus stop, bus shelter | `RT-14a` (civil works), `RT-14b` (furniture and shelters), `RT-15` (interchange) |
| footpath, pavement, path | `RT-06`; crossings `RT-07`; dropped kerbs and tactile paving `RT-08`; pedestrian network planning `RT-05` |
| cycle lane, cycle track | `RT-09`; cycle parking `RT-11`; design standards `RT-12` |
| greenway | `RT-10` |
| parking, kerbside space, loading bay | `RT-22` (supply, charges and allocation); bye-laws `RT-24` |
| taxi rank | `RT-23` |
| taxi licence, hackney, limousine, SPSV | `RT-27` |
| special speed limit, local speed limit | `RT-24` (local bye-laws); national roads `RT-25`; national default limits `RT-40` |
| speed limit enforcement | `X-02`, variant `Speed limits` |
| traffic calming, road-space reallocation | `RT-29` |
| taking in charge, declaring a road public | `RT-38` |
| road opening licence, works on a public road by others | `RT-36` |
| road closure, temporary traffic management, event closure | `RT-37` |
| traffic signal, ITS equipment | `RT-42` (the asset); `X-01` (operating and controlling it) |
| street lighting | `X-09` |
| bridge, culvert, retaining structure | `RT-03` |
| winter service, gritting, flood response | `RT-39` |
| shared bikes, bike share, e-scooter hire, shared micromobility | `RT-41` (services); `RT-26` (bye-laws and licences) |
| EV charging, electric car charge point | `X-07` (not assessed) |
| port, harbour, pier | `WT-01`, `WT-02` |
| airport, airfield | `AT-01` |
| railway, rail line, station | `RL-01` |
| part 8 | stage `S7a`, variant `Part 8 route` |
| s.38, section 38 | stage `S7b`, variant `s.38 route` |
| planning permission, An Coimisiún Pleanála, planning appeal | stage `S7c` |
| enforcement | `X-02` (road traffic and parking), `RT-10` (greenway), `RT-36` (road works), `RT-37` (closures) |
| school bus, school transport | No activity covers school transport services. `X-03` (school crossing patrols) and `X-10` (school travel education and behaviour change) are the nearest rows and both are `not assessed`. Report the gap. |

## Banned terms

| Banned term | Replace with |
|---|---|
| manages, managed, managing | Name the stage: operation `S11`, maintenance `S12`, planning `S2`, regulation `S13a` or `S13b`. |
| oversees, oversaw, oversight | Name the stage. Approving another body's output is a gateway decision, `S5G`. |
| handles, handled | Name the stage. |
| in charge of | Name the stage. (*taking in charge* is a route to `RT-38` and is allowed.) |
| owns, owned, owner | Name the stage; ownership alone is not a role. |
| looks after | Name the stage. |
| the council (as a decision-maker) | Name the party: the elected members, the Chief Executive and executive, or the municipal district members. |
| the Minister (bare) | Name the department published in the party vocabulary. |
| LA, local authority (bare, where a party is meant) | Name the party the line publishes. |
| PSV (bare) | Say bus service, or SPSV for taxi, hackney and limousine services. |

## Registers

- Internal analysis and model files: canonical IDs and the published terms.
- Public-facing copy: the plain party names the dataset publishes; no assignment, activity
  or stage IDs, and no role letters.
- The Banned terms table applies to both registers.
