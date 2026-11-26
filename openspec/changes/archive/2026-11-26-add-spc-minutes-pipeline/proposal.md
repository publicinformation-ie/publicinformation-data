# Proposal

## Why

Strategic Policy Committee (SPC) minutes record how council policy is shaped before it reaches the full council. That includes who attended, which officials presented, what was agreed, and which subjects took up the committee's time. None of it is captured today. The existing `minutes_pipeline` extracts only motions, and its curated minutes-page filters deliberately exclude SPC files. In SPC minutes the only formal proposed/seconded motion is nearly always the approval of the previous meeting's minutes, so a motions-only view captures almost nothing of value.

Meath County Council's Transportation and Urban Regeneration SPC publishes six sets of minutes (February 2025 to May 2026) from one page. They are text-layer PDFs with a regular layout: a dated header, a two-column attendance table, then numbered agenda items. That regularity makes a deterministic, fail-closed treatment practical for one committee first. Other councils and committees can be added once the model works.

## What Changes

- New pipeline `pipelines/spc_pipeline/` with these steps:
  - Read a committed list of committees (MVP: one entry, Meath Transportation and Urban Regeneration SPC). Discover the committee's minutes PDFs from its page, ignoring agenda PDFs.
  - Download each PDF and keep word positions.
  - Parse the meeting header and the attendance table.
  - Resolve every attendee against a committed people register.
  - Render each meeting's minutes verbatim as Markdown suitable for mobile reading.
  - Extract official decisions and classify each agenda item's topics in one paid model call per meeting.
  - Export a published dataset.
- **Attendance of all attendees**: councillors, sectoral (PPN) representatives, officials and presenters. Each attendance record has a status (present, or listed under apologies/absent) and a mode (in person, remote, or not stated) only where the minutes print one. A name that cannot be matched to the register is an error, and that meeting's attendance is withheld until a human resolves it.
- **Verbatim rendering**: page furniture (running header, footer, page numbers) is stripped, lines broken by the PDF are rejoined, numbered agenda items become headings, and bullets become lists. A word-level check proves that no source word was added, lost or changed. A meeting that fails the check is not rendered.
- **Official decisions only**: approving the previous meeting's minutes is excluded. Every published decision is a verbatim quote from its agenda item, checked against the item's text, with a type from a closed set. Proposer and seconder are resolved to people where the minutes give them.
- **Topics on a common taxonomy**: each agenda item is classified to UN COFOG 1999 codes (for example `04.5.1` Road transport, `06.4.0` Street lighting), committed from the UN Statistics Division's published structure file. Items under `04.5` Transport also carry a transport-governance subdomain (for example `infra/active-travel`, `svc/pso-bus`). Codes outside either closed list are rejected with an error.
- New published dataset `spc-meetings` (versioned and `latest`): meetings, people, attendance, agenda items with topics, and decisions as JSON-LD and CSV with CSVW metadata, plus one verbatim Markdown file per meeting. It follows the existing dataset publishing contract: DCAT-AP catalogue entry, JSON Schema, README, changelog, and discovery links. The COFOG and transport-subdomain code lists are published as vocabularies.
- A model-sweep experiment over the six Meath meetings against a hand-labelled gold set, to choose a cheap model with acceptable decision and topic quality before any production run.
- A handoff prompt for an agent working in `publicinformation-web`, explaining how to consume the dataset and render meetings, attendance, decisions and topics.
- Repository rules updated: the new paid step is listed in `paid_steps`, and the `CLAUDE.md` explicit-permission cost rule is extended to cover it.

Explicitly out of scope:

- Councils other than Meath, and committees other than this SPC. The committee list and register are designed to take more entries later.
- Agenda PDFs.
- OCR. All six source PDFs have a text layer. A PDF without one is an error, not an OCR job.
- Changes to `minutes_pipeline` or the `motions` dataset. SPC decisions are not added to `motions`.
- Website changes. Those go in `publicinformation-web`, driven by the handoff prompt.

## Capabilities

### New Capabilities

- `spc-minutes-ingestion`: the committed committee list, discovery of minutes PDFs (excluding agendas), download with provenance, text-layer checks and meeting-date resolution.
- `spc-minutes-rendering`: verbatim Markdown rendering of a meeting's minutes, with page-furniture removal, line rejoining, agenda-item structure and the word-preservation check.
- `spc-attendance`: the committed people register, parsing of the attendance table by category, status and mode, and resolution of every printed name to a person, with fail-closed handling of unmatched or contradictory entries.
- `spc-decisions`: extraction of official decisions per agenda item, excluding approval of previous minutes, with verbatim-quote verification, a closed decision-type set and proposer/seconder resolution.
- `spc-topic-classification`: classification of each agenda item to COFOG 1999 codes, with a transport-governance subdomain refinement under `04.5`, both validated against committed closed lists.
- `spc-meetings-dataset`: the published dataset contract. It covers distributions, record identity, linkage to Public Bodies and to councillor IDs, the published vocabularies, catalogue metadata, schema and discovery.

### Modified Capabilities

None. `motions-dataset` and `minutes-ocr` are unchanged. `source-file-references` governs files declared by committed URL and checksum. SPC minutes are discovered by crawling, as in `minutes_pipeline`, so that capability's requirements do not apply. The downloaded file's sha256 is still recorded for provenance.

## Impact

- New code: `pipelines/spc_pipeline/`, containing `pipeline.json`, `process.py`, `status.py`, steps with `README.md` and `process.py`, tests, the committed committee list, people register and code lists. Also a new `scripts/transform_spc_meetings.py`.
- Reused code: `find_local_authorities` (cross-pipeline step reference), `src/lib/llm_extract.py`, `src/lib/http_utils.py`, and the councillor IDs in `pipelines/minutes_pipeline/reference/councillors.csv`.
- TLS: `www.meath.ie` serves an incomplete certificate chain (the DigiCert Global G2 TLS RSA SHA256 2020 CA1 intermediate is missing). On Linux and CI, downloads fail certificate verification unless that public intermediate is supplied. See design.md.
- Cost: one paid model call per meeting, listed in `paid_steps`. MVP volume is 6 meetings of about 1,200–2,000 words each.
- Public-facing files: `public/v1.0.0/spc-meetings/`, `public/latest/spc-meetings/`, `public/catalog/dataset-spc-meetings.ttl`, `public/schemas/`, `public/vocabularies/` (COFOG, transport subdomain, decision type, attendance status), `public/get-the-data.html`, `public/index.html`, `public/CHANGELOG.md`, `DATA_SOURCES.md`.
- Documentation: new pipeline `README.md`, regenerated `AGENTS.md` pipeline tables, `CLAUDE.md` cost rule.
- Personal data: names of officials, PPN representatives and guests, already published in the council's own minutes, are republished with their attendance. The user confirmed this is in scope.
