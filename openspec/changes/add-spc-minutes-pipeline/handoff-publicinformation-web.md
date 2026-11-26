# Handoff prompt: consume the SPC meetings dataset in publicinformation-web

> **Draft.** Written before the dataset exists. Task 10.1 of `add-spc-minutes-pipeline` finalises it against the real `public/latest/spc-meetings/` output: it replaces the illustrative values below, adds one real sample record per file, and confirms every URL and field name. Do not hand this to an agent until that task is done.

Paste everything below the line into an agent session on the `publicinformation-ie/publicinformation-web` repo.

---

You are working in the `publicinformation-ie/publicinformation-web` repo (Astro, static build). The data repo, `publicinformation-data`, now publishes a new dataset, **SPC meetings**: the minutes of council Strategic Policy Committees. It covers who attended, the official decisions, and the topic of each agenda item on a common taxonomy. The first committee is Meath County Council's Transportation and Urban Regeneration SPC (6 meetings, February 2025 to May 2026). More councils and committees will follow with no schema change. Read `AGENTS.md`, `PRODUCT.md`, `DESIGN.md` and the `motions` dataset integration before you start.

Use OpenSpec: propose the change with `/opsx:propose` before writing code.

## What the data repo publishes

Base: `https://data.publicinformation.ie/latest/spc-meetings/`. A versioned copy with identical bytes is at `/v1.0.0/spc-meetings/`. Each table is published as `.jsonld` (a `@context` + `@graph`), `.csv` and `.csv-metadata.json`. Fetch the JSON-LD through `src/lib/dataSource.ts` (`fetchDatasetJson`, `fetchDatasetFreshness`), as `src/lib/motions.ts` does for `latest/motions/motions.jsonld`.

| File | One record per | Key fields |
|---|---|---|
| `meetings.jsonld` | meeting | `meeting_id`, `committee_id`, `committee_name`, `public_body_id`, `public_body` (Public Bodies URI), `meeting_date`, `venue`, `start_time`, `end_time`, `source_file_url`, `source_sha256`, `minutes_path`, `attendance_published` |
| `people.jsonld` | person | `person_id`, `canonical_name`, `kind` (`councillor` \| `sectoral_representative` \| `official` \| `guest`), `councillor_id` (councillors only; same ID as the motions dataset uses), `public_body_id` |
| `attendance.jsonld` | person × meeting | `meeting_id`, `meeting_date`, `person_id`, `name_as_printed`, `category`, `role_as_printed`, `status` (`present` \| `apologies`), `mode` (`in_person` \| `remote` \| `not_stated`) |
| `items.jsonld` | agenda item | `item_id`, `meeting_id`, `item_number`, `title`, `cofog` (1–3 codes, first is primary), `transport_subdomains`, `procedural`, `anchor` |
| `decisions.jsonld` | official decision | `decision_id`, `meeting_id`, `item_number`, `decision_type` (`agreed` \| `adopted` \| `recommended_to_council` \| `referred` \| `deferred` \| `appointment`), `decision_text` (verbatim quote), `proposer_id`, `seconder_id` (nullable) |
| `minutes/<council>/<committee>/<YYYY-MM-DD>.md` | meeting | verbatim minutes as Markdown with front matter |

IDs look like `meath/transportation-urban-regeneration/2026-02-19` (meeting), `meath/sean-drew` (councillor) and `meath/person/dave-anderson` (non-councillor). They are stable, so use them in URLs. Vocabularies (COFOG 1999 codes with descriptions, transport subdomains with plain labels, decision type, attendance status and mode) are under `https://data.publicinformation.ie/vocabularies/`. Show the plain labels, not raw codes.

## Rules you must respect

1. **Approval of previous minutes is not a decision.** The data repo already excludes it. Do not reconstruct it from the Markdown.
2. **Counting attendance.** "Meetings attended by person X" means attendance rows with `status = present` and that `person_id`. The denominator is the meetings where `attendance_published` is `true`. A meeting with `attendance_published: false` has no attendance rows because its attendance is under review, not because nobody attended. Show it as "attendance not yet available", never as absence.
3. **Verbatim text.** The minutes Markdown reproduces the council's text exactly, including its typos and initials ("SD", "MM"). Do not correct or expand it. Each meeting's attendance block maps initials to names, so you may show that legend beside the text.
4. **Trust boundary.** The minutes Markdown has no raw HTML by contract, so it can be rendered like library documents (see the trust-boundary comment in `src/content.config.ts`). Still validate front matter with a zod schema and fail the build on a malformed file. Accept `source_file_url` only if it is http(s).
5. **Withheld parts.** Items whose topics failed validation have empty `cofog`. Decisions that failed validation are absent. Render what is there and don't invent placeholders.

## What to build

1. **Meeting page**, readable on a phone: `/bodies/<slug>/spc-meetings/<committee>/<date>/` or the route pattern that fits the existing per-body dataset pages. Show, in order:
   - a header with committee, date, venue and a link to the source PDF;
   - attendance grouped by category, with remote/in-person shown where stated and apologies listed separately;
   - the verbatim minutes, with each agenda item heading anchored (`#item-4-0`) and tagged with its topic labels;
   - decisions listed under their agenda item.
2. **Committee page**: the list of meetings, plus an attendance matrix (people × meetings) that becomes a per-person list on small screens.
3. **Person attendance**: on a councillor's existing pages, if any, and on a simple page for non-councillors, show meetings attended out of meetings with published attendance.
4. **Topics**: let a reader filter agenda items by COFOG group and, under Transport (`04.5`), by subdomain. Consider surfacing Transport items on `/subjects/transport/`.
5. Register the dataset in `src/lib/datasets/registry.ts` with a manifest like `motionsManifest` (`perBody: true`). Add it to `llms.txt` and the data index the way other datasets are added.

## Done when

- `npm test` and the Astro build pass, and the build fails on malformed minutes front matter (test it with a fixture).
- A meeting page at 375px width has no horizontal scroll and the minutes text is fully readable.
- Attendance counts for one councillor and one PPN representative, checked by hand against the six Meath meetings, match the page.
- No page shows minutes approval as a decision.

## Report back

Routes added, components and schemas, how attendance totals are computed, screenshots at phone and desktop width, and anything in the data contract that made the work harder. Send that last point back to `publicinformation-data`.
