# Data Sources & Attribution

PublicInformation.ie aggregates data from several Irish public sector sources. We are grateful to each for making this information available.

---

## Central Statistics Office (CSO)

**Source:** [CSO StatBank — Public Register of Public Bodies in Ireland (PRPBI)](https://www.cso.ie/en/statistics/publicadministration/publicregisterofpublicbodiesinireland/)

The CSO publishes the authoritative register of public bodies in Ireland. We use this as our master list of bodies, including their names, sector classifications, and parent-body relationships.

**Licence:** [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/)

> Data sourced from the Central Statistics Office, Ireland (CSO). Licensed under CC BY 4.0.

---

## gov.ie

**Source:** [gov.ie — Departments, Agencies & Local Authorities](https://www.gov.ie/en/departments/)

The gov.ie departments directory provides the canonical list of Irish government departments, public bodies, and local authorities, along with their official website URLs. We also retrieve disclosure documents that public bodies host on assets.gov.ie.

**Licence:** [Open Government Licence (OGL) for Ireland](https://data.gov.ie/pages/licence)

> Contains public sector information licensed under the Open Government Licence v1.0.

---

## foi.gov.ie

**Source:** [foi.gov.ie — All FOI Bodies](https://foi.gov.ie/all-foi-bodies)

The Department of Public Expenditure, NDP Delivery and Reform operates the official Irish FOI portal. We use it to identify which bodies are subject to the Freedom of Information Act 2014, and to source official FOI contact email addresses.

**Licence:** [Open Government Licence (OGL) for Ireland](https://data.gov.ie/pages/licence)

> Contains public sector information licensed under the Open Government Licence v1.0.

---

## datacatalogue.gov.ie

**Source:** [datacatalogue.gov.ie — Public Service Data Catalogue](https://datacatalogue.gov.ie/organization/)

The Public Service Data Catalogue is a single information point where Irish public sector bodies list the data they hold — including "protected data" holdings under the EU Data Governance Act — and where data reusers can make a data request. We use its CKAN organisation list to link each canonical public body to its organisation page on the catalogue.

**Licence:** not stated. The catalogue publishes no reuse licence; its pages carry only "© Government of Ireland". The derived dataset reproduces each organisation's name, page URL and its own self-description, and adds only the identifier matching, so check the catalogue's terms before reusing the underlying descriptions.

> Source: Public Service Data Catalogue (datacatalogue.gov.ie), Government of Ireland.

---

## Irish Public Body Websites

We crawl the individual websites of Irish public bodies to locate their FOI pages, collect FOI contact details, and retrieve disclosure log documents (PDF, XLSX, XLS). The data published here — FOI request records, decision statuses, and related metadata — originates from these disclosure logs and is reproduced for transparency and public interest purposes.

Each disclosure log remains the property of the publishing body. Where a body's website specifies a licence or reuse policy, that policy applies to their data.

---

## National Transport Authority (NTA)

**Source:** the NTA's annual Active Travel Investment Grant allocations, published each January on [nationaltransport.ie](https://www.nationaltransport.ie/):

- 2022 — [Active Travel Investment Grants – List of Projects 2022](https://www.nationaltransport.ie/publications/active-travel-investment-grants-list-of-projects-2022/): [2022 allocations](https://www.nationaltransport.ie/wp-content/uploads/2022/01/2022-Active-Travel-Investment-Allocations.pdf) and [Annex 1, programme budget and commentary](https://www.nationaltransport.ie/wp-content/uploads/2022/01/20220124-Annex-1-Summary-of-Active-Travel-funding.pdf)
- 2023 — [Active Travel Investment Grants: 2023 Allocations](https://www.nationaltransport.ie/news/active-travel-investment-grants-2023/): [combined allocations](https://www.nationaltransport.ie/wp-content/uploads/2023/01/Combined_2023_ActiveTravel_Allocations.pdf)
- 2024 — [Active Travel Investment Grants: 2024 Allocations](https://www.nationaltransport.ie/news/active-travel-investment-grants-2024-allocations/): [allocations](https://www.nationaltransport.ie/wp-content/uploads/2024/02/2024-Active-Travel-Allocations.pdf)
- 2025 — [Active Travel Investment Grants: 2025 Allocations](https://www.nationaltransport.ie/news/active-travel-investment-grants-2025-allocations/): [full allocations table](https://www.nationaltransport.ie/wp-content/uploads/2025/01/Full-Allocations-Table-130125.pdf)
- 2026 — [Active Travel Investment Grants 2026 Allocations](https://www.nationaltransport.ie/news/active-travel-investment-grants-2026-allocations/): [allocations](https://www.nationaltransport.ie/wp-content/uploads/2026/01/Active-Travel-Investment-Grants-2026-Allocations.pdf)

The NTA allocates this funding to local authorities, public transport bodies and other agencies for walking and cycling infrastructure. We publish each printed project allocation with its source document and page, and reproduce the figures only where the document's own declared totals confirm them.

**Licence:** the documents are published by the National Transport Authority as public sector information. Where the NTA specifies a licence or reuse policy, that policy applies. The derived dataset is published under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

> Source: National Transport Authority, Active Travel Investment Grant allocations (2022–2026).

---

## Department of Public Expenditure, Infrastructure, Public Service Reform and Digitalisation (PER)

**Source:** [PER Databank — Open Data PS Numbers Source](https://databank.per.gov.ie/OpenData/Open%20Data%20PS%20Numbers%20Source.csv)

Quarterly public service numbers (full-time-equivalent staff) by department, sector and body. We publish the most recent quarter, matched to our canonical list of public bodies.

**Licence:** not yet confirmed. The derived dataset adds matching and structure only; check the PER Databank's terms before reusing the underlying figures.

> Source: Department of Public Expenditure, Infrastructure, Public Service Reform and Digitalisation, Public Service Numbers.

---

## Meath County Council

**Source:** [Transportation and Urban Regeneration Strategic Policy Committee](https://www.meath.ie/council/your-council/your-elected-council/strategic-policy-committees/transportation-and-urban-regeneration-spc)

The council publishes the committee's agendas and minutes as PDFs on one page. We ingest the minutes only (February 2025 to May 2026), record each file's sha256, and reproduce each meeting's text verbatim as Markdown. Attendance, decisions and topics are derived from that text; names are reproduced as the council published them.

**Licence:** the minutes are published by Meath County Council as public sector information. The derived dataset is published under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

> Source: Meath County Council, Transportation and Urban Regeneration Strategic Policy Committee minutes.

---

## United Nations Statistics Division — COFOG 1999

**Source:** [COFOG 1999 English structure file](https://unstats.un.org/unsd/classifications/Econ/Download/In%20Text/COFOG_english_structure.txt)

The UN Statistics Division's Classification of the Functions of Government (COFOG) 1999, used as the common taxonomy for agenda-item topics. The committed list records the source file's sha256 (`5368887b…4b39b5`, retrieved 2026-11-26).

**Licence:** the classification is published by the United Nations for statistical use. The derived code list and dataset are published under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

> Source: United Nations Statistics Division, Classification of the Functions of Government (COFOG) 1999.

---

*If you are a public body and have a concern about how your data is represented here, please contact us.*
