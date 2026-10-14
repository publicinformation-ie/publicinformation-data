# Transport governance vocabulary

Controlled vocabulary for the transport governance model. It is region-neutral: which body does
what in a particular region lives only in that region's RACI file (`raci-gda.md`).

## Rules

1. In model files a controlled term appears only as its ID or exact term.
2. *Accountable* and *responsible* are used only in the RACI sense (A and R below).
3. Banned terms are replaced as the Banned terms table says.
4. *Public transport* is a defined alias for exactly `svc/pso-bus`, `svc/commercial-bus`,
   `svc/rail` and `svc/light-rail`. It excludes SPSV and school transport.
5. A term used in the RACI or notes without a vocabulary entry is a defect.
6. Two registers: canonical terms (ID or Term) in model files and internal analysis; the Plain
   label column in public-facing copy.

## Boundary rules

1. A rule that applies to a specific road or place (special speed limit, parking control, bus
   lane) is **Regulation** on that place's infra subdomain. A rule that applies to all road users
   nationally is on `users/traffic-law`.
2. Enforcement by AGS of road traffic offences is recorded once, under
   `users/traffic-law · Enforcement`. Enforcement run by the LA (parking) is recorded on the
   infra subdomain whose rule is breached.
3. A footpath or cycle facility is `infra/active-travel` wherever it is located; the carriageway
   and other road assets are the relevant roads subdomain.
4. A pedestrian crossing is a pedestrian facility and is `infra/active-travel`.
5. A contractor acting for a body is recorded as that body.
6. A row whose Qualifier is `—` covers every case not covered by a qualified row for the same
   subdomain and function.

## RACI letters

| ID | Term | Definition | Plain label | Excludes / not to be confused with |
|---|---|---|---|---|
| A | Accountable | The single body that approves an activity's output and answers for it if it fails. | has the final say | Not the body doing the work (R); never also C on the same row. |
| R | Responsible | A body that carries out the activity. | does the work | Not approval (A). |
| C | Consulted | A body whose views are sought, by law or in practice, before the output is approved. | is asked for its views | Not I (informed), which this model does not record. |

## Functions

| ID | Term | Definition | Plain label | Excludes / not to be confused with |
|---|---|---|---|---|
| policy | Policy | The function of setting national objectives, legislation and guidelines. | sets national policy | Not Strategic planning, which plans a network. |
| strategic-planning | Strategic planning | The function of producing long-range network plans. | draws up the long-term plan | Not Policy; not Specification of a single scheme. |
| funding | Funding | The function of allocating capital or current money. | pays for it | Not Delivery. |
| specification | Specification | The function of deciding what is built or run, including location, alignment, route, frequency and fare. | decides what is built or run | Not Consent; not Strategic planning. |
| consent | Consent | The function of giving statutory approval to build. | gives permission to build | Not Regulation, which licenses ongoing activity. |
| delivery | Delivery | The function of procuring and constructing. | builds or procures it | Not Operation. |
| operation | Operation | The function of running an asset or service day to day. | runs it day to day | Not Maintenance. |
| maintenance | Maintenance | The function of keeping an asset in its specified condition. | keeps it in repair | Not Delivery of new assets. |
| regulation | Regulation | The function of licensing third parties and setting binding rules or standards for them or for the use of an asset. | licenses others and sets the rules | Not Policy; not Enforcement. |
| enforcement | Enforcement | The function of detecting breaches and applying penalties. | checks the rules are kept and penalises breaches | Not Regulation. |

## Modes

| ID | Term | Definition | Plain label | Excludes / not to be confused with |
|---|---|---|---|---|
| road | Road | The mode tag for motor traffic on public roads. | roads and traffic | Not bus. |
| bus | Bus | The mode tag for buses and coaches carrying passengers. | buses | Not SPSV. |
| rail | Rail | The mode tag for heavy rail. | trains | Not light-rail. |
| light-rail | Light rail | The mode tag for tram and metro systems. | Luas and metro | Not rail. |
| active | Active travel | The mode tag for walking and cycling. | walking and cycling | Not shared. |
| taxi | Taxi | The mode tag for SPSV. | taxis | Not bus. |
| school | School | The mode tag for the school transport scheme. | school transport | Not bus generally. |
| shared | Shared mobility | The mode tag for schemes renting vehicles to the public for short trips. | bike and scooter sharing | Not taxi. |
| maritime | Maritime | The mode tag for ports and harbours. | ports | Not aviation. |
| aviation | Aviation | The mode tag for airports and aerodromes. | airports | Not maritime. |

## Subdomains

| ID | Term | Definition | Plain label | Excludes / not to be confused with | Mode tags |
|---|---|---|---|---|---|
| infra/national-roads | National roads | The physical assets of roads classified as national, including motorways. | national roads and motorways | Footpaths and cycle facilities (infra/active-travel); parking (infra/kerbside). | road |
| infra/regional-local-roads | Regional and local roads | The physical assets of public roads not classified as national. | regional and local roads | Footpaths and cycle facilities (infra/active-travel); bus priority (infra/bus). | road |
| infra/active-travel | Active travel infrastructure | The physical assets used by pedestrians and cyclists, wherever located. | footpaths, cycle lanes and crossings | Shared mobility schemes (svc/shared-mobility). | active |
| infra/bus | Bus infrastructure | The physical assets used only by buses and their passengers on the road network. | bus stops, shelters and bus lanes | Bus services (svc/pso-bus, svc/commercial-bus). | bus |
| infra/heavy-rail | Heavy rail infrastructure | The track, stations, signalling and structures of the national rail network. | railway lines and stations | Light rail (infra/light-rail). | rail |
| infra/light-rail | Light rail infrastructure | The track, stops and depots of tram and metro systems. | Luas and metro lines | Heavy rail (infra/heavy-rail). | light-rail |
| infra/kerbside | Kerbside | The space at the edge of a public road used by stationary vehicles. | parking, taxi ranks, loading bays and charging points | The carriageway; footpaths (infra/active-travel). | road, taxi |
| infra/ports-airfields | Ports and airfields | The physical assets of ports, airports and military aerodromes. | ports and airports | Ferry and flight services, which this model does not cover. | maritime, aviation |
| svc/pso-bus | PSO bus services | Bus services provided under a PSO contract. | subsidised bus services | Commercial bus services; school transport. | bus |
| svc/commercial-bus | Commercial bus services | Bus and coach services run under a route licence without PSO payment. | private bus and coach services | PSO bus services. | bus |
| svc/rail | Rail services | Passenger train services on the heavy rail network. | train services | Light rail services. | rail |
| svc/light-rail | Light rail services | Passenger tram and metro services. | Luas and metro services | Rail services. | light-rail |
| svc/spsv | Small public service vehicles | Passenger services by taxi, hackney and limousine. | taxis, hackneys and limousines | Taxi ranks (infra/kerbside); bare PSV. | taxi |
| svc/school-transport | School transport | The state scheme carrying pupils to and from school. | school buses | PSO bus services that pupils also use. | bus, school |
| svc/shared-mobility | Shared mobility | Schemes renting bikes, e-bikes, e-scooters or cars to the public for short trips. | bike, scooter and car sharing | Privately owned e-scooters (users/traffic-law). | active, shared |
| users/vehicles-drivers | Vehicles and drivers | The licensing and testing of drivers and vehicles. | driving licences and vehicle tests | SPSV licensing (svc/spsv). | road |
| users/traffic-law | Traffic law | The national rules of the road for all road users, and their enforcement. | road traffic law | Special speed limits and parking rules (infra subdomains). | road |

## Bodies

| ID | Term | Definition | Plain label | Excludes / not to be confused with |
|---|---|---|---|---|
| DoT | Department of Transport | The government department that sets national transport policy and legislation and funds transport agencies. | the Department of Transport | NTA and TII, which are agencies under it. |
| DHLGH | Department of Housing, Local Government and Heritage | The government department that sets planning and local government policy and legislation. | the Department of Housing | DoT. |
| DoE | Department of Education and Youth | The government department whose functions include the school transport scheme. | the Department of Education | Not an environment department; DoE here always means education. |
| DoD | Department of Defence | The government department whose functions include military aerodromes. | the Department of Defence | IAA, the aviation regulator. |
| NTA | National Transport Authority | The state agency that plans GDA transport, contracts and funds PSO services, and licenses commercial bus and SPSV services. | the National Transport Authority | TII. |
| TII | Transport Infrastructure Ireland | The state agency that funds, specifies and supervises national roads and delivers light rail infrastructure. | Transport Infrastructure Ireland | Not the road authority for national roads (LA-CE is); not the light rail operator (PSO-op). |
| LA-members | Elected members (plenary) | The elected members of a local authority acting together at a full meeting, where reserved functions are exercised. | the councillors at a full council meeting | LA-MD; LA-SPC. |
| LA-CE | Chief Executive | The Chief Executive and staff of a local authority, who exercise its executive functions. | the council's Chief Executive and staff | LA-members. |
| LA-MD | Municipal District members | The elected members for one Municipal District acting together on the reserved functions assigned to that district. | the municipal district councillors | Exists only where the local authority is divided into Municipal Districts. |
| LA-SPC | Strategic Policy Committee | An advisory committee of elected members and sectoral representatives that prepares policy for LA-members to adopt. | the council's policy committee | Never A or R; appears only in C. |
| IE | Iarnród Éireann | The state rail company that is infrastructure manager of the heavy rail network and operator of PSO rail services. | Irish Rail | NTA, which contracts and funds its PSO services. |
| BE | Bus Éireann | The state bus company that operates PSO and commercial bus services outside Dublin Bus's network and runs the school transport scheme. | Bus Éireann | DB. |
| DB | Dublin Bus | The state bus company that operates PSO bus services in the Dublin area under contract to NTA. | Dublin Bus | BE. |
| PSO-op | PSO contracted operator | A private company that runs a PSO bus or light rail service under contract to NTA. | a private operator contracted by the National Transport Authority | DB, BE and IE, which are listed separately; Comm-op. |
| Comm-op | Licensed commercial operator | A private operator that runs a bus, SPSV or shared mobility service at its own commercial risk under a licence or permit. | a private operator | PSO-op. |
| RSA | Road Safety Authority | The state agency that licenses drivers, runs driver and vehicle testing, and promotes road safety. | the Road Safety Authority | AGS, which enforces road traffic law. |
| AGS | An Garda Síochána | The national police service, whose functions include enforcing road traffic law. | the Gardaí | RSA. |
| ACP | An Coimisiún Pleanála | The national planning body that decides planning appeals and gives consent for strategic infrastructure, road schemes and railways. | An Coimisiún Pleanála, the national planning body | Formerly An Bord Pleanála; not LA-CE, which decides ordinary planning applications. |
| IAA | Irish Aviation Authority | The state agency that regulates civil aviation safety, security and economic matters. | the Irish Aviation Authority | daa; DoD. |
| CRR | Commission for Railway Regulation | The state agency that regulates the safety of heavy and light rail. | the rail safety regulator | NTA; IE. |
| Port-co | Port company | A state-owned company that is the harbour authority for a commercial port. | the port company | A harbour vested in a local authority. |
| daa | daa | The state-owned company that operates and develops the state airports at Dublin and Cork. | daa, the Dublin Airport operator | IAA. |

## Governance terms

| ID | Term | Definition | Plain label | Excludes / not to be confused with |
|---|---|---|---|---|
| g/reserved-function | reserved function | A local authority power that by law only its elected members may exercise. | decided by the councillors | executive function. |
| g/executive-function | executive function | A local authority power that is not reserved and so is exercised by the Chief Executive. | decided by council officials | reserved function. |
| g/road-authority | road authority | The body with the statutory duty to construct and maintain the public roads in its area under the Roads Act 1993. | the road authority | For national roads the road authority remains the local authority, not TII. |
| g/gda | GDA | The Greater Dublin Area: the areas of Dublin City, Dún Laoghaire–Rathdown, Fingal, South Dublin, Kildare, Meath and Wicklow local authorities. | the Greater Dublin Area | The Dublin region (the four Dublin local authorities only). |
| g/pso | PSO | A public service obligation: a service that a public body pays an operator to provide because it would not run commercially. | subsidised public service | Commercial services. |
| g/public-transport | public transport | The defined alias for exactly svc/pso-bus, svc/commercial-bus, svc/rail and svc/light-rail. | public transport | SPSV; school transport. |
| g/municipal-district | Municipal District | A statutory subdivision of a county council whose members exercise some reserved functions for that area. | municipal district | Dublin area committees, which are not Municipal Districts. |
| g/bye-law | bye-law | A binding local rule made by a public body under a specific statutory power. | local bye-law | National regulations. |
| g/part-8 | Part 8 | The procedure under Part 8 of the Planning and Development Regulations 2001 by which a local authority's elected members approve or reject its own development. | council approval of its own project | Planning permission; Section 38. |
| g/section-38 | Section 38 | The power under Road Traffic Act 1994 s.38 for a road authority to provide traffic calming measures as an executive function. | traffic-calming decision by council officials | Part 8. |
| g/section-51 | Section 51 approval | The approval by ACP, under Roads Act 1993 s.51, of a road scheme that needs environmental impact assessment. | national planning approval for a road scheme | Part 8. |
| g/railway-order | Railway Order | The consent by ACP, under the Transport (Railway Infrastructure) Act 2001, to build a railway. | permission for a new railway or Luas line | Planning permission. |
| g/development-plan | development plan | The six-year statutory land-use plan adopted by a local authority's elected members under Planning and Development Act 2000 s.10. | county or city development plan | Local Transport Plan. |
| g/local-transport-plan | Local Transport Plan | A transport plan for a town or area, prepared by a local authority, that feeds into a local area plan or development plan. | local transport plan | GDA Transport Strategy. |
| g/gda-transport-strategy | GDA Transport Strategy | The statutory long-range transport strategy for the GDA, prepared by NTA and approved by DoT. | the Greater Dublin Area transport strategy | Local Transport Plan. |
| g/annual-budget | annual budget | The yearly local authority budget, adopted by its elected members as a reserved function. | the council budget | state grant. |
| g/state-grant | state grant | Money allocated by a government department or state agency to another body for a set purpose. | government grant | annual budget. |
| g/taking-in-charge | taking in charge | The declaration by a local authority's elected members that a road becomes a public road maintained by the road authority. | taking an estate in charge | Specification of road works. |
| g/road-opening-licence | road opening licence | A licence from the road authority to open or occupy a public road for works. | road opening licence | Consent to build. |
| g/traffic-management | traffic management | The control of vehicle movement on a specific road through regulatory traffic signs and road markings. | traffic management | special speed limit; parking. |
| g/special-speed-limit | special speed limit | A speed limit set by bye-law for a specific road in place of the default limit for that class of road. | local speed limit | Default speed limits (users/traffic-law). |
| g/parking | parking | The control of where, when and on what terms vehicles may stop or park on a public road. | parking rules | appointed stand. |
| g/appointed-stand | appointed stand | A place on a public road set aside by bye-law for taxis to wait for hire. | taxi rank | SPSV licensing (svc/spsv). |
| g/clamping | clamping | The immobilisation or removal of a parked vehicle by a clamping operator. | clamping | Parking fines. |
| g/ev-charging | EV charging | Public charge points for electric vehicles on or beside a public road. | public charging points for electric cars | Private home chargers. |
| g/toll | toll | A charge for using a road, set by bye-law. | road toll | parking charges. |
| g/port | port | A harbour together with its quays and land, run by a port company or local authority as harbour authority. | port or harbour | airport. |
| g/airport | airport | A civil aerodrome open to commercial passenger flights. | airport | military aerodrome. |
| g/military-aerodrome | military aerodrome | An aerodrome operated by the Defence Forces. | military airfield | airport. |
| g/rail-safety | rail safety | The safety obligations that rail operators and infrastructure managers must meet under the Railway Safety Act 2005. | rail safety | bye-law. |
| g/national-road | national road | A public road classified as a national road under the Roads Act 1993. | national road | regional road. |
| g/regional-road | regional road | A public road classified as a regional road under the Roads Act 1993. | regional road | national road; local road. |
| g/local-road | local road | A public road that is neither national nor regional. | local road | regional road. |

## Banned terms

| Banned term | Replace with |
|---|---|
| manages, managed, managing | Name the function (Operation, Maintenance, Specification). |
| oversees, oversaw, oversight | Name the function; approving another body's output is A. |
| handles, handled | Name the function. |
| in charge of | Name the function. (*taking in charge* is a governance term and is allowed.) |
| owns, owned, owner | Name the function; ownership alone is not a function. |
| looks after | Name the function. |
| PSV (bare) | bus (svc/pso-bus, svc/commercial-bus) or SPSV (svc/spsv). |
| the Minister (bare) | Name the department: DoT, DHLGH, DoE or DoD. |
| council (as a decision-maker) | LA-members, LA-CE or LA-MD. |
| LA (bare, as a body) | LA-members, LA-CE, LA-MD or LA-SPC. |
